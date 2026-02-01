from collections import defaultdict
import aiohttp
import requests
from src.logger import logger
from src.utils.utils import func_name
from datetime import datetime, timedelta
import pytz
from src.utils.session_vars import set_user_data
from src.db.db import DB
# DynamoDB is commented out - import conditionally
try:
    from src.db.dynamodb import dynamo_client
except ImportError:
    dynamo_client = None
import os
from dotenv import load_dotenv
db = DB()

load_dotenv()
IS_LOCAL = os.getenv("ENV") == "LOCAL"

class ClinikoClient:
    def __init__(self, url, api_key , clinicData, call_id):
        self.api_key = api_key
        self.CLINIKO_BASE_URL = url
        self.auth = aiohttp.BasicAuth(self.api_key, '')
        self.clinicData = clinicData
        self.call_id = call_id
        self.business_data = self.get_business_sync()
        print("BUSINESS DATA FROM INIT CLASS" , self.business_data)
        self.local_number= "+923332033086"

            
    def convert_timezone(self, time, timezone):
        print('Converting timezone', time, timezone)
        current_time = datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ')

        timezone = pytz.timezone(timezone)
        time = timezone.localize(current_time)
        print('Time: ', time)
    
        return time.isoformat()
    
    def fix_gmt_time(self, time_str, hours):
        original_time = datetime.fromisoformat(time_str)
        
        # Separate hours and minutes from the offset
        sign = hours[0]
        hour_minute_split = hours[1:].split(':')
        time_hours = int(hour_minute_split[0])
        time_minutes = int(hour_minute_split[1]) if len(hour_minute_split) > 1 else 0

        # Apply the offset based on the sign
        if sign == '+':
            print('Subtracting hours: ', time_hours, 'and minutes:', time_minutes)
            new_time = original_time - timedelta(hours=time_hours, minutes=time_minutes)
        else:
            print('Adding hours: ', time_hours, 'and minutes:', time_minutes)
            new_time = original_time + timedelta(hours=time_hours, minutes=time_minutes)

        # Convert to UTC string format
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        print('ORIGINAL_TIME: ', original_time)
        print('FIX_GMT_TIME: ', utc_time_str)
        return utc_time_str 

    def subtract_hours_from_time(self, time_str, hours_to_subtract):
        # Parse the string to a datetime object
        original_time = datetime.fromisoformat(time_str)
        
        # Subtract the specified hours
        new_time = original_time - timedelta(hours=hours_to_subtract)
        
        # Format the new time as UTC
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return utc_time_str
    
    def add_hours_to_time(self, time_str, hours_to_subtract):
        # Parse the string to a datetime object
        original_time = datetime.fromisoformat(time_str)
        
        # Subtract the specified hours
        new_time = original_time + timedelta(hours=hours_to_subtract)
        
        # Format the new time as UTC
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return utc_time_str
    
    def fix_end_time_for_appointment(self, time_str, duration_in_minutes):
        # Parse the string to a datetime object
        original_time = datetime.fromisoformat(time_str)

        # Subtract the specified hours
        new_time = original_time + timedelta(minutes=int(duration_in_minutes))
        
        # Format the new time as UTC
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        print("Original time", original_time)
        print(f"Added {duration_in_minutes} minutes: ", utc_time_str)

        return utc_time_str
    
    def add_minutes(self, time_str, mins_to_add):
        # Parse the string to a datetime object
        original_time = datetime.fromisoformat(time_str)
        
        # Subtract the specified hours
        new_time = original_time + timedelta(minutes=int(mins_to_add))
        
        # Format the new time as UTC
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        print(f"Added {mins_to_add} minutes: ", utc_time_str)

        return utc_time_str

    def get_week_day(self, date_str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

        day_of_week = date_obj.weekday()
        WEEK_DAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

        return WEEK_DAYS[day_of_week]

    async def get_doctor_timings(self, params):
        url = f"{self.CLINIKO_BASE_URL}/daily_availabilities"
        logger.info(f"Fetching doctor timings from {url}")

        query = {
            "order": params.get('order', 'asc'),
            "page": params.get('page', 1),
            "per_page": params.get('per_page', 50),
            "sort": params.get('sort', 'created_at:desc')
        }

        if params['q']:
            if isinstance(params['q'], list):
                for filter_param in params['q']:
                    query.setdefault("q[]", []).append(filter_param)
            else:
                query.setdefault("q[]", []).append(params['q'])

        logger.info(f"Query parameters: {query}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    logger.info(f"Response status: {response.status}")
                    data = await response.json()
                    logger.info(f"Received data: {data}")
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in fetching doctor availability from Cliniko API: {e}")
            return None, 500

    async def check_available_time(self, patient_chosen_day, starts_at, ends_at, doctor_id, business_id):
        logger.info(f"Checking available time for doctor_id: {doctor_id}, business_id: {business_id}")
        logger.info(f"Patient chosen day: {patient_chosen_day}, starts_at: {starts_at}, ends_at: {ends_at}")

        try: 
            response, status = await self.get_doctor_timings({
                "q": [
                    f"business_id:={business_id}",
                    f"practitioner_id:={doctor_id}",
                ]
            })

            if not response:
                logger.error(f"No data found, status: {status}")
                return "Not Available"

            daily_availabilities = response.get('daily_availabilities', [])
            logger.info(f"Daily availabilities: {daily_availabilities}")

            WEEK_DAYS = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
            doctor_timings = {}

            for daily_availability in daily_availabilities:
                day = daily_availability['day_of_week']
                availabilities = daily_availability['availabilities']

                daily_timings = []
                for availability in availabilities:
                    timing = {
                        "start_at": f"{availability['starts_at']}:00",
                        "end_at": f"{availability['ends_at']}:00"
                    }
                    daily_timings.append(timing)

                doctor_timings[WEEK_DAYS[day]] = daily_timings
                logger.info(f"Processed timings for {WEEK_DAYS[day]}: {daily_timings}")

            logger.info(f"Doctor timings: {doctor_timings}")

            for key, value in doctor_timings.items():
                logger.info(f"Checking timings for {key}")
                if key == patient_chosen_day:
                    logger.info(f"Matching day found: {key}")

                    # Parse the patient's chosen time (just the time portion)
                    patient_chosen_starts_at = datetime.strptime(starts_at, "%Y-%m-%dT%H:%M:%SZ").time()
                    patient_chosen_ends_at = datetime.strptime(ends_at, "%Y-%m-%dT%H:%M:%SZ").time()

                    logger.info(f"Patient chosen time: starts_at={patient_chosen_starts_at}, ends_at={patient_chosen_ends_at}")

                    for time_slot in value:
                        doctor_available_starts_at = time_slot['start_at']
                        doctor_available_ends_at = time_slot['end_at']

                        logger.info(f"Doctor available time: starts_at={doctor_available_starts_at}, ends_at={doctor_available_ends_at}")

                        # Compare using only the time portion
                        if datetime.strptime(doctor_available_starts_at, "%H:%M:%S").time() <= patient_chosen_starts_at and datetime.strptime(doctor_available_ends_at, "%H:%M:%S").time() >= patient_chosen_ends_at:
                            logger.info("Doctor is available at the chosen time.")
                            return "Available"

                    logger.info("No matching time slot found for the chosen time.")
                    return "Not Available"

            logger.info("No available timings for the chosen day.")
            return "Not Available"
        
        except Exception as e:
            logger.error(f"Error in check_available_time: {e}")
            return None, 500
    
    async def get_doctor_slots(self, params: dict, date):
        print("params in get doctor slots_______",params)

        try:
            params['practitioner_id'] = await self.get_practitioner_details(params['doctor_name'])
            print("Pract_id_____", params['practitioner_id'])
            
            appointment_details = await self.get_appointment_type_id(params['appointment_name'])
            print("appointment_deeets____", appointment_details)
            params['appointment_type_id'] = appointment_details['id']
            params['appointment_type'] = appointment_details
            
            business_details = await self.get_business_details(params['clinic_name'])
            print("busineessssssssss_deeets____", business_details)
            params['business_id'] = business_details['id']
            params['timezone'] = business_details['timezone']
            params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])
                    
            url = f"{self.CLINIKO_BASE_URL}/businesses/{params['business_id']}/practitioners/{params['practitioner_id']}/appointment_types/{params['appointment_type_id']}/available_times"

            starting_date = datetime.fromisoformat(date)
            to_date = starting_date + timedelta(days=6)

            # Query parameters for the request
            query = {
                "from": starting_date.date().isoformat(),
                "to": to_date.date().isoformat(),
                "page": 1,
                "per_page": 10,
            }

            logger.info(f"Fetching available times from {url} for dates {query['from']} to {query['to']}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        # Getting Available Summarized and Readable Time Slots
                        logger.info(f"Received available times data: {data}")
                        summarized_times = await self.summarize_available_times(data, min_gap_hours=2)
                        print("Summerized times in get doctor slots: ",summarized_times)
                        readable_times = []

                        for item in summarized_times:
                            converted = await self.convert_readable_doctor_slots_timing(item , params['timezone'])
                            readable_times.append(converted)
                        
                        logger.info(f"Readable Time: {readable_times}")
                        return readable_times, response.status
                    else:
                        error_message = await response.text()
                        logger.error(f"Error fetching available times: {response.status} - {error_message}")
                        return None, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in fetching available times from Cliniko API: {e}")
            return None, 500
        

    async def create_appointment_new_patient(self, params : dict):
        logger.info(f"Params in create_appointment_new_patient function {params}")   
        print("START_DATE", params['starts_at'])

        try:
            params['practitioner_id'] = await self.get_practitioner_details(params['doctor_name'])
            
            appointment_details = await self.get_appointment_type_id(params['appointment_name'])
            params['appointment_type_id'] = appointment_details['id']
            params['appointment_type'] = appointment_details
            
            business_details = await self.get_business_details(params['clinic_name'])
            print(business_details)
            params['business_id'] = business_details['id']
            params['timezone'] = business_details['timezone']
            params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])


            if IS_LOCAL:
                call_number = self.local_number  # Local testing number
                print("Running locally. Using test number:", call_number)
                normalized_number = await self.normalize_phone_number(call_number)
                params['phone_number'] = normalized_number
                print("Normalized Number inside new patient function:", params['phone_number'])

            else:
                call_number = await self.get_phone_number()
                print("Call Info:", call_number)
                normalized_number = await self.normalize_phone_number(call_number)
                params['phone_number'] = normalized_number
                print("Normalized Number inside new patient function:", params['phone_number'])

            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']), params['timezone'])
            
            patient_chosen_day = self.get_week_day(params['starts_at'])

            print(f"Patient chosen day: {patient_chosen_day}")

            doctor_available = await self.check_available_time(
                patient_chosen_day, 
                params['starts_at'],
                self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']),
                params['practitioner_id'],
                params['business_id']
            )

            if doctor_available == "Not Available":
                return "Doctor not available", 400
            
            #Special Appointment Type Check
            if self.clinicData["specialAppointmentsCheck"]:
                for specialAppointment in self.clinicData["specialAppointments"]:
                    if params["appointment_name"] == specialAppointment:
                        availability = await self.check_special_appointments_availablity(params)
                        if availability is False:
                            return "Special Appointments not available", 400
            
            # # Used to check if there is a conflict with an existing booking
            bookings, bookings_status = await self.list_bookings({
                "q": [
                    f"practitioner_id:={params['practitioner_id']}",
                    f"starts_at:<{self.fix_gmt_time(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']), params['GMT'])}",
                    f"ends_at:>{self.fix_gmt_time(params['starts_at'], params['GMT'])}",
                    f"business_id:={params['business_id']}",
                ]
            })

            print(f"Booking status: {bookings_status}")
            print(f"Bookings: {bookings}")

            if bookings_status == 200 and bookings.get('total_entries', 0) > 0:
                return "Booking Conflict", 409

            # Checking if the patient exists.
            # If not, create a new patient
            patient_data, patient_status = await self.list_patients({
                "q": [
                    f"first_name:={params['first_name']}", 
                    f"last_name:={params['last_name']}", 
                    f"date_of_birth:={params['date_of_birth']}"
                ]
            })

            print(f"Patient status: {patient_status}")
            print(f"Patient data: {patient_data}")

            if patient_status == 200 and patient_data.get('total_entries', 0) == 0:
                logger.info("Creating new patient")
                patient_data, status = await self.add_patient(params=params, skip_patient_check=True)

                if patient_data.get('id', None) is not None:
                    patient_id = patient_data['id']
                    
                    # Session Variable
                    set_user_data({
                        "id": patient_id,
                        'first_name': patient_data['first_name'],
                        'last_name': patient_data['last_name'],
                        'date_of_birth': patient_data['date_of_birth'],
                        'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_NEW_PATIENT',
                        'phone_number': patient_data['patient_phone_numbers'][0]['number']
                    })

                    print(f"Created new patient: {patient_data}")
                
                print(f"Patient data: {patient_data}")

                # Adding patient to dynamodb
                new_patient_data = {
                    "patient_id": patient_data['id'],
                    "first_name": patient_data['first_name'],
                    "last_name": patient_data['last_name'],
                    "date_of_birth": patient_data['date_of_birth'],
                    "phone_number": patient_data['patient_phone_numbers'][0]['number'],
                    "clinic_name": self.clinicData["name"],
                }
                add_patient_to_dynamo = await dynamo_client.add_patient(self.clinicData['db_tablename'], new_patient_data)
                print("Patient added to dynamo: ",add_patient_to_dynamo)
            
            else:
                patient_data = patient_data['patients'][0]                                 
                set_user_data({
                    "id": patient_data['id'],
                    'first_name': patient_data['first_name'],
                    'last_name': patient_data['last_name'],
                    'date_of_birth': patient_data['date_of_birth'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_NEW_PATIENT',
                    'phone_number': patient_data['patient_phone_numbers'][0]['number']
                })
                return "Patient already exists", 409
            print("Start Time:",params['starts_at'])
            

            url = f"{self.CLINIKO_BASE_URL}/individual_appointments"
            logger.info(f"Params in Create function {params}")
            
            payload = {
                "appointment_type_id": params["appointment_type_id"],
                "business_id": params['business_id'],
                "starts_at": starts_at,
                "ends_at": ends_at,
                "patient_id": patient_id,
                "practitioner_id": params['practitioner_id'],
                "notes": params['notes']
            }

            logger.info(f"Payload in Create appointment function {payload}")

            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, json=payload, headers=headers, auth=self.auth) as response:
                        data = await response.json()
                        return data, response.status
                except aiohttp.ClientError as e:
                    logger.error(f"Error in create_individual_appointment Cliniko API: {e}")
                    return None, 500
                
        except Exception as e:
            logger.error(f"Error in create_appointment_new_patient: {e}")
            return f"Error: {e}", 500

    async def create_appointment_existing_patient(self, params: dict):
        logger.info(f"Params in create_appointment_existing_patient function {params}")
        
        try:
            params['practitioner_id'] = await self.get_practitioner_details(params['doctor_name'])
            
            appointment_details = await self.get_appointment_type_id(params['appointment_name'])
            params['appointment_type_id'] = appointment_details['id']
            params['appointment_type'] = appointment_details
            
            business_details = await self.get_business_details(params['clinic_name'])
            params['business_id'] = business_details['id']
            params['timezone'] = business_details['timezone']
            params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])


            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']), params['timezone'])
            print("Returned value from convert_timezone: ", starts_at)

            patient_chosen_day = self.get_week_day(params['starts_at'])

            print(f"Patient chosen day: {patient_chosen_day}")

            doctor_available = await self.check_available_time(
                patient_chosen_day, 
                params['starts_at'],
                self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']),
                params['practitioner_id'],
                params['business_id']
            )

            if doctor_available == "Not Available":
                return "Doctor not available", 400

            patient_data, patient_status = await self.list_patients({
                "q": [
                    f"first_name:={params['first_name']}", 
                    f"last_name:={params['last_name']}", 
                    f"date_of_birth:={params['date_of_birth']}"
                ]
            })

            if patient_status == 200 and patient_data.get('total_entries', 0) == 0:
                set_user_data({
                    "id": None,
                    'first_name': params['first_name'],
                    'last_name': params['last_name'],
                    'date_of_birth': params['date_of_birth'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_EXISTING_PATIENT',
                })
                return "Patient not found", 404
            else:
                patient_id = patient_data['patients'][0]['id']
                patient = patient_data['patients'][0]
                print("Patient found")
                set_user_data({
                    "id": patient['id'],
                    'first_name': patient['first_name'],
                    'last_name': patient['last_name'],
                    'date_of_birth': patient['date_of_birth'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_EXISTING_PATIENT',
                    'phone_number': patient['patient_phone_numbers'][0]['number']
                })

            #Special Appointment Type Check
            if self.clinicData["specialAppointmentsCheck"]:
                for specialAppointment in self.clinicData["specialAppointments"]:
                    if params["appointment_name"] == specialAppointment:
                        availability = await self.check_special_appointments_availablity(params)
                        if availability is False:
                            return "Special Appointments not available", 400

            # Used to check if there is a conflict with an existing booking
            bookings, bookings_status = await self.list_bookings({
                "q": [
                    f"practitioner_id:={params['practitioner_id']}",
                    f"starts_at:<{self.fix_gmt_time(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']), params['GMT'])}",
                    f"ends_at:>{self.fix_gmt_time(params['starts_at'], params['GMT'])}",
                    f"business_id:={params['business_id']}",
                ]
            })
            print(f"Booking status: {bookings_status}")
            print(f"Bookings: {bookings}")

            if bookings_status == 200 and bookings.get('total_entries', 0) > 0:
                return "Booking Conflict", 409

            url = f"{self.CLINIKO_BASE_URL}/individual_appointments"
            logger.info(f"Params in Create function {params}")
            
            payload = {
                "appointment_type_id": params["appointment_type_id"],
                "business_id": params['business_id'],
                "starts_at": starts_at,
                "ends_at": ends_at,
                "patient_id": patient_id,
                "practitioner_id": params['practitioner_id'],
                "notes": params['notes']
            }

            logger.info(f"Payload in Create appointment function {payload}")

            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, json=payload, headers=headers, auth=self.auth) as response:
                        data = await response.json()
                        return data, response.status
                except aiohttp.ClientError as e:
                    logger.error(f"Error in create_individual_appointment Cliniko API: {e}")
                    return None, 500

        except Exception as e:
            logger.error(f"Error in create_appointment_existing_patient: {e}")
            return f"Error: {e}", 500

    async def update_individual_appointment(self, params: dict, data):
        try:
            logger.info(f"Params in update_individual_appointment function {params}")

            patients, patient_status = await self.list_patients({
            "q": [
                f"first_name:={params['first_name']}", 
                f"last_name:={params['last_name']}", 
                f"date_of_birth:={params['date_of_birth']}"
            ]})

            if patient_status == 200 and patients['total_entries'] > 0:
                params['patient_id'] = patients['patients'][0]['id']
                patient = patients['patients'][0]
                set_user_data({
                    "id": patient['id'],
                    'first_name': patient['first_name'],
                    'last_name': patient['last_name'],
                    'date_of_birth': patient['date_of_birth'],
                    'call_type': 'INBOUND_RESCHEDULE',
                    'phone_number': patient['patient_phone_numbers'][0]['number']
                })
            else:
                set_user_data({
                    "id": None,
                    'first_name': params.get('first_name', ''),
                    'last_name': params.get('last_name', ''),
                    'date_of_birth': params.get('date_of_birth', ''),
                    'call_type': 'INBOUND_RESCHEDULE',
                    'phone_number': params.get('phone_number', '')
                })
                return "Patient not found", 404
            
            params['phone_number'] = patient['patient_phone_numbers'][0]['number']

            current_date = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            appointments, appointments_status = await self.list_individual_appointments({
            "q": [
                f"patient_id:={params['patient_id']}",
                f"starts_at:>={current_date}",
            ]
            })
            print("data before loop", data)
            for d in data:
                print("data_______", data)            
                print("old_date", params['old_start_date'])
                params['GMT']= await self.convert_timezone_to_gmt(d['timezone'])
                fixed_time= self.fix_gmt_time(params['old_start_date'],params['GMT'])
                print("Fixed_time____",fixed_time)
                if fixed_time== d['starts_at']:
                    print("d_____",d)
                    params['doctor_name']= d['doctor_name']
                    params['clinic_name']= d['clinic_name']
                    params['appointment_name']= d['appointment_name']

            params['practitioner_id'] = await self.get_practitioner_details(params['doctor_name'])
            
            business_details = await self.get_business_details(params['clinic_name'])
            params['business_id'] = business_details['id']
            params['timezone'] = business_details['timezone']
            params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])
            
            print("Businesss Details--------" , business_details)
            
            for appointment in appointments['individual_appointments']:
                print('appointment start date', appointment['starts_at'])
                if appointment['starts_at'] == self.fix_gmt_time(params['old_start_date'], params['GMT']):
                    appointment_type_url = appointment['appointment_type']['links']['self']

                    appointment_type = await self.get_appointment_type_by_url(appointment_type_url)

                    params['duration_in_minutes'] = appointment_type['duration_in_minutes']
                    params['appointment_type_id'] = appointment_type['id']
                    params['appointment_id'] = appointment['id']
                    params['appointment_name'] = appointment_type['name']
                    appointment_found = True
                    break

            if not appointment_found:
                return 'Appointment not found', 404
                                    
            try:
                new_starts_at = self.convert_timezone(params['new_starts_date'], params['timezone'])
                new_ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['new_starts_date'], params['duration_in_minutes']), params['timezone'])

                patient_chosen_day = self.get_week_day(params['new_starts_date'])

                print(f"Patient chosen day: {patient_chosen_day}")

                doctor_available = await self.check_available_time(
                    patient_chosen_day, 
                    params['new_starts_date'],
                    self.fix_end_time_for_appointment(params['new_starts_date'], params['duration_in_minutes']),
                    params['practitioner_id'],
                    params['business_id']
                )

                if doctor_available == "Not Available":
                    return "Doctor not available", 400
                
                #Special Appointment Type Check
                if self.clinicData["specialAppointmentsCheck"]:
                    for specialAppointment in self.clinicData["specialAppointments"]:
                        if params["appointment_name"] == specialAppointment:
                            availability = await self.check_special_appointments_availablity(params)
                            if availability is False:
                                return "Special Appointments not available", 400
                
                bookings, bookings_status = await self.list_bookings({
                    "q": [
                        f"practitioner_id:={params['practitioner_id']}",
                        f"starts_at:<{self.fix_gmt_time(self.fix_end_time_for_appointment(params['new_starts_date'], params['duration_in_minutes']), params['GMT'])}",
                        f"ends_at:>{self.fix_gmt_time(params['new_starts_date'], params['GMT'])}",
                        f"business_id:={params['business_id']}",
                    ]
                })
            
                if bookings_status != 200 or bookings['total_entries'] > 0:
                    return 'Booking Conflict', 409
            
            except Exception as e:
                logger.error(f"Error in update appointment Cliniko API: {e}")
                return None, 500

            url = f"{self.CLINIKO_BASE_URL}/individual_appointments/{params['appointment_id']}"
            logger.info(f"Params in update_individual_appointment function {params}")
            payload = {
                "appointment_type_id": params['appointment_type_id'],
                "business_id": params['business_id'],
                "ends_at": new_ends_at,
                "patient_id": params['patient_id'],
                "practitioner_id": params['practitioner_id'],
                "starts_at": new_starts_at,
            }
            
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession() as session:  
                try:
                    async with session.patch(url, json=payload, headers=headers, auth=self.auth) as response:
                        data = await response.json()
                        
                        return data, response.status
                except Exception as e:
                    logger.error(f"Error in update appointment Cliniko API: {e}")
                    return None, 500    

        except Exception as e:
            logger.error(f"Error in update_individual_appointment Cliniko API: {e}")
            return None, 500

    async def cancel_individual_appointment(self, params: dict,):
        logger.info(f"In cancel_individual_appointment function {params}")

        try:
            patients, patient_status = await self.list_patients({
            "q":[
                f"first_name:={params['first_name']}", 
                f"last_name:={params['last_name']}", 
                f"date_of_birth:={params['date_of_birth']}"
            ]})
            
            print("________patient_______", patients)

            if patient_status == 200 and patients['total_entries'] > 0:
                patient_id = patients['patients'][0]['id']
                patient = patients['patients'][0]
                set_user_data({
                    "id": patient['id'],
                    'first_name': patient['first_name'],
                    'last_name': patient['last_name'],
                    'date_of_birth': patient['date_of_birth'],
                    'call_type': 'INBOUND_CANCEL',
                    'phone_number': patient['patient_phone_numbers'][0]['number']
                })
            else:
                set_user_data({
                    "id": None,
                    'first_name': params.get('first_name', ''),
                    'last_name': params.get('last_name', ''),
                    'date_of_birth': params.get('date_of_birth', ''),
                    'call_type': 'INBOUND_CANCEL',
                    'phone_number': params.get('phone_number', '')
                    
                })
                return "Patient not found", 404

            params['phone_number'] = patient['patient_phone_numbers'][0]['number']
        
            current_date = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            appointments, appointments_status = await self.list_individual_appointments({
            "q": [
                f"patient_id:={patient_id}",
                f"starts_at:>={current_date}",
            ]
            })

            appointment_found = False
            for appointment in appointments['individual_appointments']:
                print("-----------Appointment-------", appointment)
                print("INSIDE FOR______________")
                business_id_url = appointment['business']['links']['self']
                business_details = await self.get_business_by_url(business_id_url)
                params['business_id'] = business_details['id']
                params['timezone'] = business_details['time_zone_identifier']
                params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])
                params['clinic_name'] = business_details['display_name']
                
                if appointment['starts_at'] == self.fix_gmt_time(params['starts_at'], params['GMT']):
                    print("INSIDE IF___________")
                    appointment_found = True
                    appointment_id = appointment['id']
                    url = f"{self.CLINIKO_BASE_URL}/individual_appointments/{appointment_id}/cancel"
                    payload = {
                        "cancellation_note": '',
                        "apply_to_repeats":  False,
                        "cancellation_reason": '10'
                    }   
                    headers = {"Content-Type": "application/json"}
                    logger.info(f"Payload in cancel_individual_appointment function {payload}")
                    async with aiohttp.ClientSession() as session:
                        try:
                            logger.info(f"Making call to {url}")
                            async with session.patch(url, json=payload, headers=headers, auth=self.auth) as response:
                                print(f"Cancel function response: {response}")
                                if response.status == 204:
                                    print('Appointment cancelled')
                                    return response, response.status
                                else:
                                    print('Failed to cancel')
                                    return response, response.status
                        except Exception as e:
                            logger.error(f"Error in {func_name} Cliniko API: {e}")
                            return None, 500
                            
                
            if appointment_found is False:
                return "Appointment not found", 404
            

        except Exception as e:
            logger.error(f"Error in {func_name} Cliniko API: {e}")
            return None, 500
        
    async def get_patient_appointment(self, params: dict):
        logger.info(f"Params in get_patient_appointment function {params}")
        patients, patient_status = await self.list_patients({
        "q": [
            f"first_name:={params['first_name']}", 
            f"last_name:={params['last_name']}", 
            f"date_of_birth:={params['date_of_birth']}"
        ]})

        if patient_status == 200 and patients['total_entries'] > 0:
            params['patient_id'] = patients['patients'][0]['id']
            patient = patients['patients'][0]
            set_user_data({
                "id": patient['id'],
                'first_name': patient['first_name'],
                'last_name': patient['last_name'],
                'date_of_birth': patient['date_of_birth'],
                'call_type': 'INBOUND_RESCHEDULE',
                'phone_number': patient['patient_phone_numbers'][0]['number']
            })
        else:
            set_user_data({
                "id": None,
                'first_name': params.get('first_name', ''),
                'last_name': params.get('last_name', ''),
                'date_of_birth': params.get('date_of_birth', ''),
                'call_type': 'INBOUND_RESCHEDULE',
                'phone_number': params.get('phone_number', '')
            })
            return "Patient not found", 404
        
        current_date = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        appointments, appointments_status = await self.list_individual_appointments({
        "q": [
            f"patient_id:={params['patient_id']}",
            f"starts_at:>={current_date}",
        ]
        })
        
        appointment_found=False

        data=[]

        for appointment in appointments['individual_appointments'][0:3]:
            print('appointment start date', appointment['starts_at'])
            if appointment['starts_at'] > datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"):
                practitioner= await self.get_practitioner_by_url(appointment['practitioner']['links']['self'])
                print("Practitioner PRINT______",practitioner)

                doctor_name = practitioner["first_name"] + " " + practitioner["last_name"]

                business= await self.get_business_by_url(appointment['business']['links']['self'])
                print("Business PRINT______",business)
                clinic_name = business['label']
                timezone= business['time_zone_identifier']

                appointment_type_data = await self.get_appointment_type_by_url(appointment['appointment_type']['links']['self'])
                print("appointment_type_id PRINT______",appointment_type_data)
                appointment_type_id= appointment_type_data['id']
                appointment_name= appointment_type_data['name']

                appointment_data= {
                "starts_at" : appointment["starts_at"],
                "doctor_name" : doctor_name,
                "clinic_name" : clinic_name,
                "timezone": timezone,
                "appointment_name": appointment_name,
                "appointment_type_id": appointment_type_id,
                }
                data.append(appointment_data)
            appointment_found=True
        if not appointment_found:
            return "Appointment not found", 404   
        print("Data in get_patient_appointment function: ", data)             
        return data, 200    
    
    
    async def list_individual_appointments(self, params: dict):
        url = f"{self.CLINIKO_BASE_URL}/individual_appointments"
        logger.info(f"Params in list_individual_appointments function {params}")
        
        query = {
            "order": params.get('order', 'asc'),
            "page": params.get('page', 1),
            "per_page": params.get('per_page', 100),
            "sort": params.get('sort', 'starts_at'),
        }

        if params['q']:
            if isinstance(params['q'], list):
                for filter_param in params['q']:
                    query.setdefault("q[]", []).append(filter_param)
            else:
                query.setdefault("q[]", []).append(params['q'])

        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:            
            try:
                async with session.get(url, headers=headers ,params=query, auth=self.auth) as response:
                    logger.info(f"Making call to {url}")
                    data = await response.json()
                    return data, 200

            except Exception as e:
                logger.error(f"Error in list_individual_appointments Cliniko API: {e}")
                return None

    def get_individual_appointments(self, params: dict):
        url = f"{self.CLINIKO_BASE_URL}/individual_appointments/{params['appointment_id']}"
        logger.info(f"Params in get_individual_appointments function {params}")

        query = {
            "q[]": params['query']
        }

        headers = {"Content-Type": "application/json"}

        try:
            logger.info(f"Making call to {url}")
            response = requests.get(url, headers=headers, params=query, auth=(self.api_key, ''))
            data = response.json()

            return data

        except Exception as e:
            logger.error(f"Error in {func_name} Cliniko API: {e}")
            return None
    
    async def add_patient(self, params: dict, skip_patient_check=False):
        # Name, number and DOB

        url = f"{self.CLINIKO_BASE_URL}/patients"
        logger.info(f"Params in add_patient function {params}")

        if not skip_patient_check:
            # Check if patient with same details
            patients, status = await self.list_patients({
                "q": [
                    f"first_name:={params['first_name']}", 
                    f"last_name:={params['last_name']}",
                    f"date_of_birth:={params['date_of_birth']}",
                ]    
            })
        
            if status == 200 and patients.get('total_entries', 0) > 0:
                logger.info("Patient with same data already exists")
                return "Patient with same data already exists", 409


        payload = {
            "first_name": params['first_name'],
            "last_name": params['last_name'],
            "date_of_birth": params['date_of_birth'],
            "patient_phone_numbers": [
                {
                    "phone_type": "Mobile",
                    "number": params['phone_number'],
                }
            ],
        }

        logger.info(f"Payload in add_patient function {payload}")

        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Sending request to {url}")
                async with session.post(url, json=payload, headers=headers, auth=self.auth) as response:
                    data = await response.json()
                    return data, response.status
                
            except Exception as e:
                logger.error(f"Error in add_patient Cliniko API: {e}")
                return None
        
    async def get_patient(self, params: dict):
        # url = f"{self.CLINIKO_BASE_URL}/patients/{params['patient_id']}"
        params['email'] = self.prepare_email(params['email'])
        logger.info(f"Params in get_patient function {params}")

        if params.get('patient_id', '') == '':
            logger.info('Got Empty Patient ID')
            # Used to get the ID of the patient
            patient_data, patients_status = await self.list_patients({
                "q":[
                    f"first_name:={params['first_name']}", 
                    f"last_name:={params['last_name']}", 
                    f"email:={params['email']}", 
                    f"date_of_birth:={params['date_of_birth']}"
                ]})
        else:
            patient_data, patients_status = await self.list_patients({
                "q": [f"id:={params['patient_id']}"]
            })

        return patient_data, patients_status

    async def get_patient_by_url(self, url):
        logger.info(f"Params in get_patient_by_url function {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=self.auth) as response:
                    data = await response.json()
                    return data

        except Exception as e:
            logger.error(f"Error in get_patient_by_url Cliniko API: {e}")
            return None
        
    async def get_practitioner_by_url(self, url):
        logger.info(f"Params in get_practitioner_by_url function {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=self.auth) as response:
                    data = await response.json()
                    return data

        except Exception as e:
            logger.error(f"Error in get_practitioner_by_url Cliniko API: {e}")
            return None
    

    async def get_appointment_by_url(self,url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self.auth) as response:
                data = await response.json()
                return data
    
    async def get_business_by_url(self,url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self.auth) as response:
                data = await response.json()
                return data
            
    async def get_appointment_type_by_url(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=self.auth) as response:
                data = await response.json()
                return data
    async def list_patients(self, params: dict):
        url = f"{self.CLINIKO_BASE_URL}/patients"
        logger.info(f"Params in list_patients function {params}")
        
        query = {
            "order": params.get('order', 'asc'),
            "page": params.get('page', 1),
            "per_page": params.get('per_page', 5),
            "sort": params.get('sort', 'created_at:desc')
        }

        if params['q']:
            if isinstance(params['q'], list):
                for filter_param in params['q']:
                    query.setdefault("q[]", []).append(filter_param)
            else:
                query.setdefault("q[]", []).append(params['q'])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    data = await response.json()
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in list_patients Cliniko API: {e}")
            return None, 500

    async def list_bookings(self, params: dict):
        url = f"{self.CLINIKO_BASE_URL}/bookings"
        logger.info(f"Params in list_bookings function {params}")
        
        query = {
            "order": params.get('order', 'asc'),
            "page": params.get('page', 1),
            "per_page": params.get('per_page', 5),
            "sort": params.get('sort', 'created_at:desc')
        }

        if params['q']:
            if isinstance(params['q'], list):
                for filter_param in params['q']:
                    query.setdefault("q[]", []).append(filter_param)
            else:
                query.setdefault("q[]", []).append(params['q'])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    data = await response.json()
                    # print("data", data)
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in list_bookings Cliniko API: {e}")
            return None, 500
        
    async def convert_readable_doctor_slots_timing(self , iso_string , timezone):
        # Normalize the ISO string, ensuring only one timezone indication
        if iso_string.endswith('Z'):
            iso_string = iso_string.replace('Z', '+00:00')
        
        # Parse the datetime
        try:
            dt = datetime.fromisoformat(iso_string)
        except ValueError:
            dt = datetime.strptime(iso_string[:19], '%Y-%m-%dT%H:%M:%S')
            if '+' in iso_string or '-' in iso_string:
                dt = dt.replace(tzinfo=pytz.timezone('UTC'))

        # Convert to the clinic's timezone
        clinic_timezone = pytz.timezone(timezone)
        dt = dt.astimezone(clinic_timezone)
        
        # Format the day with suffix
        day = dt.day
        date_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day if day < 20 else day % 10, 'th')
        if 11 <= day <= 13:
            date_suffix = 'th'
        
        # Get the day of the week
        day_of_week = dt.strftime('%A')
        
        formatted_date = f"{day_of_week}, {day}{date_suffix} {dt.strftime('%B')}"
        
        # Format the time to a readable format with minutes
        formatted_time = dt.strftime("%I:%M %p").lower().strip()
        
        return f"{formatted_date} {formatted_time}"

    async def summarize_available_times(self, data, min_gap_hours=2):
        # Calculate the time gap in minutes
        
        summarized_times = defaultdict(list)
        print("Summarized Times", summarized_times)

        # Group times by date
        for entry in data['available_times']:
            appointment_start = entry['appointment_start']
            dt = datetime.fromisoformat(appointment_start.replace("Z", "+00:00"))
            date = dt.date()
            summarized_times[date].append(dt)
        
        # Store the selected times with a gap between them
        selected_times = []

        # Sort times for each date and select two with the specified gap
        for date in sorted(summarized_times):
            sorted_times = sorted(summarized_times[date])
            
            # Initialize the list of selected times for this date
            date_times = []
            
            # Iterate through sorted times and select times with the specified gap
            for i, time in enumerate(sorted_times):
                # Add the first time
                if len(date_times) == 0:
                    date_times.append(time)
                # Add the next time only if it has the required gap from the last selected time
                elif len(date_times) == 1 and (time - date_times[0]) >= timedelta(minutes=min_gap_hours*60):
                    date_times.append(time)
                    break # Only need two times per date, so break after adding the second
                
            # Add the selected times for the date to the final list
            selected_times.extend(date_times)

        # Convert the selected times to ISO format strings and add 'Z' for UTC
        summarized_list = [dt.isoformat() + 'Z' for dt in sorted(selected_times)]

        two_slots = summarized_list[0:2] 
        print("Two Slots", two_slots)

        return two_slots
    
    async def get_next_available_slot(self, params: dict):
        params['practitioner_id'] = await self.get_practitioner_details(params['doctor_name'])
        
        appointment_details = await self.get_appointment_type_id(params['appointment_name'])
        params['appointment_type_id'] = appointment_details['id']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_business_details(params['clinic_name'])
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])

        url = f"{self.CLINIKO_BASE_URL}/businesses/{params['business_id']}/practitioners/{params['practitioner_id']}/appointment_types/{params['appointment_type_id']}/next_available_time"

        starting_date = datetime.now()
        to_date = starting_date + timedelta(days=6)

        # Query parameters for the request
        query = {
            "from": starting_date.date().isoformat(),
            "to": to_date.date().isoformat(),
        }

        logger.info(f"Fetching available times from {url} for dates {query['from']} to {query['to']}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        # Getting Available Summarized and Readable Time Slots
                        logger.info(f"Received available times data from cliniko--------: {data}")
                        
                        slot = data['appointment_start']
                        
                        converted = await self.convert_readable_doctor_slots_timing(slot , params['timezone'])
                        readable_times = converted
                                            
                        logger.info(f"Readable Time: {readable_times}")
                        return readable_times, response.status
                    else:
                        error_message = await response.text()
                        logger.error(f"Error fetching available times: {response.status} - {error_message}")
                        return None, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in fetching available times from Cliniko API: {e}")
            return None, 500
        

    ##-------------------------FILTER AVAILABLE SLOTS---------------------###
    async def filter_slots_by_preferred_time(self, available_slots, preferred_time, timezone, user_preference="closest", min_gap_hours=2):
        """
        Filters available slots based on the preferred time and user preference.

        :param available_slots: List of available slot timestamps in ISO format (UTC).
        :param preferred_time: Preferred time as a string in ISO format.
        :param timezone: The local timezone to convert the slots to.
        :param user_preference: 'after_10', 'before_10', 'exact', or 'closest' (default).
        :param min_gap_hours: Minimum required gap between two slots when fetching two slots.
        :return: A list of one or more ISO 8601-formatted UTC time slots.
        """
        local_tz = pytz.timezone(timezone)

        # Convert available slots from UTC to local timezone
        available_times = sorted([
            datetime.fromisoformat(slot.replace("Z", "+00:00")).astimezone(local_tz)
            for slot in available_slots
        ])

        if not available_times:
            return []

        print(f"Available Slots: {[dt.strftime('%Y-%m-%d %I:%M %p') for dt in available_times]}")

        # Handle '00:00:00Z' case (no preferred time)
        if preferred_time.endswith("00:00:00Z"):
            print("No preferred time specified")
            for i in range(len(available_times) - 1):
                print(f"Checking gap between {available_times[i]} and {available_times[i + 1]}")
                if (available_times[i + 1] - available_times[i]) >= timedelta(hours=min_gap_hours):
                    print(f"Gap found: {available_times[i]} and {available_times[i + 1]}")
                    return [
                        available_times[i].astimezone(pytz.UTC).isoformat().replace("+00:00", "Z"),
                        available_times[i + 1].astimezone(pytz.UTC).isoformat().replace("+00:00", "Z"),
                    ], "no preferred time"
            return [available_times[0].astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")], "no preferred time"

        # Convert preferred time to local datetime
        tz = pytz.timezone(timezone)
        naive_local = datetime.fromisoformat(preferred_time.replace("Z", ""))
        preferred_dt_local = tz.localize(naive_local)
        print(f"Preferred Time (Local): {preferred_dt_local.strftime('%Y-%m-%d %I:%M %p')}")

        target_time = preferred_dt_local.replace(second=0, microsecond=0)
        print(f"Target Time: ", target_time)

        if user_preference == "after":
            for slot in available_times:
                if slot > target_time:
                    return [slot.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")], "after"
            return [], "after"

        elif user_preference == "before":
            before_slots = [slot for slot in available_times if slot < target_time]
            if before_slots:
                return [before_slots[-1].astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")], "before"
            return [], "before"

        elif user_preference == "exact":
            for slot in available_times:
                exact_slot = slot.replace(second=0, microsecond=0)
                if exact_slot == target_time:
                    return [exact_slot.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")], "exact"
            else:
                logger.warning(f"The exact slot at {target_time.strftime('%I:%M %p')} is already booked.")
                # Default behavior: find the closest slot
                closest_slot = min(available_times, key=lambda slot: abs(slot - preferred_dt_local))
                # print(f"Closest Slot Selected: {closest_slot.strftime('%Y-%m-%d %I:%M %p')}")
                return [closest_slot.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")], "slot already booked"
        else:
            # Default behavior: find the closest slot
            closest_slot = min(available_times, key=lambda slot: abs(slot - preferred_dt_local))
            # print(f"Closest Slot Selected: {closest_slot.strftime('%Y-%m-%d %I:%M %p')}")
            return [closest_slot.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")], "closest"

        
    #-------------------------GET SPECIFIC DAY AVAILABLE SLOT---------------------###
    async def get_specific_day_slots(self, params: dict):
        print("params in get spefic day slots_______", params)
        params['practitioner_id'] = await self.get_practitioner_details(params['doctor_name'])
        print("Pract_id_____", params['practitioner_id'])
        
        appointment_details = await self.get_appointment_type_id(params['appointment_name'])
        print("appointment_deeets____", appointment_details)
        params['appointment_type_id'] = appointment_details['id']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_business_details(params['clinic_name'])
        print("busineessssssssss_deeets____", business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])
                
        url = f"{self.CLINIKO_BASE_URL}/businesses/{params['business_id']}/practitioners/{params['practitioner_id']}/appointment_types/{params['appointment_type_id']}/available_times"

        starting_date = datetime.fromisoformat(params['starts_at'])
        to_date = starting_date

        query = {
            "from": starting_date.date().isoformat(),
            "to": to_date.date().isoformat(),
            "page": 1,
            "per_page": 100,  # Fetch all slots first
        }

        logger.info(f"Fetching available times from {url} for dates {query['from']} to {query['to']}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Received available times data: {data}")
                        
                        available_slots = [entry['appointment_start'] for entry in data['available_times']]
                        
                        if available_slots == []:
                            return "No slots available", 400, "no preferred time"
                        
                        filtered_slots, slot_type = await self.filter_slots_by_preferred_time(available_slots, params['starts_at'], params['timezone'], params['user_preference'])
                        readable_times = []

                        if filtered_slots == []:
                            return "No free time", 404, slot_type
                        
                        for item in filtered_slots:
                            converted = await self.convert_readable_doctor_slots_timing(item, params['timezone'])   
                            readable_times.append(converted)
                        
                        logger.info(f"Readable Time: {readable_times}")
                        return readable_times, response.status, slot_type
                    else:
                        error_message = await response.text()
                        logger.error(f"Error fetching available times: {response.status} - {error_message}")
                        return None, response.status, "no preferred time"
        except aiohttp.ClientError as e:
            logger.error(f"Error in fetching available times from Cliniko API: {e}")
            return None, 500, "no preferred time"
      
    async def convert_timezone_to_gmt(self , timezone_identifier):
        # Get the timezone object
        tz = pytz.timezone(timezone_identifier)

        # Get the current time in that timezone
        now = datetime.now(tz)

        # Format the offset as GMT
        gmt_offset = now.strftime("%z")
        gmt_formatted = f"{gmt_offset[:3]}:{gmt_offset[3:]}"

        return gmt_formatted
    
    ###-------------------------GET PRACTITIONERS DETAILS---------------------###
    async def get_all_practitioners(self):
        url = f"{self.CLINIKO_BASE_URL}/practitioners"
        query = {
            "page":  1,
            "per_page": 100,
            "sort": 'created_at:desc'
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    data = await response.json()
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in getting all practitioners Cliniko API: {e}")
            return None, 500
        
    async def get_practitioner_details(self, doctor_name):
        response , status = await self.get_all_practitioners()
        practitioners = response["practitioners"]
        for practitioner in practitioners:
            if doctor_name == practitioner["first_name"] + " " + practitioner["last_name"]:
                return practitioner["id"] 
        else:
            logger.error("No practitioners with given name found")
            return None
        
    ###-------------------------GET BUSINESS DETAILS---------------------###
    async def get_business(self):
        """
        Asynchronously fetch business data from the Cliniko API.
        """
        url = f"{self.CLINIKO_BASE_URL}/businesses"
        query = {
            "page": 1,
            "per_page": 100,
            "sort": 'created_at:desc'
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, auth=self.auth) as response:
                    data = await response.json()
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in getting all business Cliniko API: {e}")
            return None, 500
        
    def get_business_sync(self):
        """
        Synchronously fetch business data from the Cliniko API.
        """
        url = f"{self.CLINIKO_BASE_URL}/businesses"
        query = {
            "page": 1,
            "per_page": 100,
            "sort": "created_at:desc"
        }
        try:
            response = requests.get(url, params=query, auth=(self.api_key, ''))
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
            data = response.json()
            return data, response.status_code
        except requests.RequestException as e:
            logger.error(f"Error in getting all business Cliniko API: {e}")
            return None, 500
    
    async def get_business_details(self , clinic_name):
        logger.info("Getting Location Details")
        response , status = self.business_data
        businesses = response["businesses"]
        for business in businesses:
            if clinic_name == business["label"]:
                gmt = await self.convert_timezone_to_gmt(business["time_zone_identifier"])
                business_details = {
                    "timezone" : business["time_zone_identifier"],  
                    "id" : business["id"],
                    "clinic_name" : business["label"],
                    "GMT" : gmt
                }
                return business_details
        else:
            logger.error("No clinic with given name found")
            return None
        
    ###-------------------------GET APPOINTMENT TYPES---------------------###
    async def get_all_appointment_types(self):
        url = f"{self.CLINIKO_BASE_URL}/appointment_types"
        query = {
            "page": 1,
            "per_page": 100,
            "sort": 'created_at:desc'
        }
        all_appointment_types = []

        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    async with session.get(url, params=query, auth=self.auth) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch page {query['page']}: {response.status}")
                            return None, response.status

                        data = await response.json()
                        items = data.get("appointment_types", [])
                        all_appointment_types.extend(items)

                        # Stop if there are no more pages
                        if not data.get("links", {}).get("next"):
                            break

                        # Increment page for next iteration
                        query["page"] += 1

            return all_appointment_types, 200

        except aiohttp.ClientError as e:
            logger.error(f"Error in getting all appointment types Cliniko API: {e}")
            return None, 500

    async def get_appointment_type_id(self , appointment_name):
        response, status = await self.get_all_appointment_types()
        appointment_types = response
        for appointment_type in appointment_types:
            if appointment_name == appointment_type["name"]:
                appointment_id = appointment_type["id"]
                appointment_type_duration = appointment_type["duration_in_minutes"]
                appointment_type_details = {
                    "id": appointment_id,
                    "duration_in_minutes": appointment_type_duration,
                    "name" : appointment_type["name"]
                }
                return appointment_type_details
        else:
            logger.error("No appointment types found")
            return None
        
    async def check_special_appointments_availablity(self, params:dict):
        """
        Checks for special appointments to be alloted to one doctor/patient at a time 
        """
        bookings, bookings_status = await self.list_bookings({
            "q": [
                f"starts_at:<{self.fix_gmt_time(self.fix_end_time_for_appointment(params['starts_at'], params['duration_in_minutes']), params['GMT'])}",
                f"ends_at:>{self.fix_gmt_time(params['starts_at'], params['GMT'])}",
                f"business_id:={params['business_id']}",
                f"appointment_type_id:={params['appointment_type_id']}",
            ]
        })
        print("bookings", bookings)
        if bookings["total_entries"] > 0:
            return False
        else:
            return True
        

    async def get_phone_number(self):
        from src import retell
        call= retell.call.retrieve(self.call_id)
        print("Call in get_phone_number: ", call)
        return call.from_number
    
    async def normalize_phone_number(self , phone_number):
        print("phone_number", phone_number)
        if phone_number.startswith("+61"):
            normalized_number = "0" + phone_number[3:]
        elif phone_number.startswith("+92"):
            normalized_number = "0" + phone_number[3:]
        else:
            normalized_number = phone_number
        result = normalized_number
        return result
    
    async def get_patient_data_from_dynamo(self, params):
        try:
            print("Params in get_patient_data_from_dynamo:", params)
            found_patient = None
        
            matching_patients=[]
            if ( params.get("first_name") not in [None, "None"] and params.get("last_name") not in [None, "None"] and params.get("date_of_birth") not in [None, "None"]):
                patient_data, patient_status = await self.list_patients({
                    "q": [
                        f"first_name:={params['first_name']}",
                        f"last_name:={params['last_name']}", 
                        f"date_of_birth:={params['date_of_birth']}"
                    ]
                })

                if patient_status == 200 and patient_data.get('total_entries', 0) == 0:
                    return "Patient not found", 404
                else:
                    patient = patient_data['patients'][0]
                    print("Patient found")
                    found_patient = {
                        "first_name": patient["first_name"],
                        "last_name": patient["last_name"],
                        "date_of_birth": patient["date_of_birth"],
                    }            

                matching_patients.append(found_patient)
            
            else:
                if IS_LOCAL:
                    call_number = self.local_number
                    print("Running locally. Using test number:", call_number)
                else:
                    if params.get("phone_number") != "None":
                        call_number = params["phone_number"]
                    else:
                        call_number = await self.get_phone_number()
                        print("Call Info:", call_number)

                normalized_number = await self.normalize_phone_number(call_number)
                # params["phone_number"] = normalized_number
                print("After Normalized numbers")
                patients = await dynamo_client.search_patient(table_name=self.clinicData['db_tablename'], phone_number = normalized_number , clinic_name=self.clinicData['name'])
            
                for patient in patients:
                    found_patient = {
                        "patient_id": patient["patient_id"],
                        "first_name": patient["first_name"],
                        "last_name": patient["last_name"],
                        "date_of_birth": patient["date_of_birth"],
                    }
                    print("Patient found", found_patient)
                    matching_patients.append(found_patient)

            # Return the patient data if found; otherwise, return an error message with a 404 status code.
            if matching_patients:
                return matching_patients, 200
            else:
                return "Patient not found", 404
        except Exception as e:
            logger.error(f"Error in getting patient data from dynamo: {e}")
            return "Patient not found", 404
