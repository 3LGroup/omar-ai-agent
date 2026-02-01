import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import os
from urllib import parse
import aiohttp
import pytz
import requests
import json
from src.logger import logger
from src.utils.session_vars import set_user_data
from src.utils.utils import func_name
# DynamoDB is commented out - import conditionally
try:
    from src.db.dynamodb import dynamo_client
except ImportError:
    dynamo_client = None
from dotenv import load_dotenv

load_dotenv()
print("ENV:", os.getenv("ENV"))
IS_LOCAL = os.getenv("ENV") == "LOCAL"
print("IS_LOCAL: ", IS_LOCAL)
class NookalClient:
    def __init__(self, url, api_key , clinicData, call_id, timezone):
        self.api_key = api_key
        self.NOOKAL_BASE_URL = url
        self.clinicData = clinicData
        self.timezone= timezone
        self.call_id = call_id
        self.local_number= "+923105172728"

#__________________TIMEZONE + TIME FIXING FUNCTIONS_______________________
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
    
    async def convert_timezone_to_gmt(self , timezone_identifier):
        # Get the timezone object
        tz = pytz.timezone(timezone_identifier)

        # Get the current time in that timezone
        now = datetime.now(tz)

        # Format the offset as GMT
        gmt_offset = now.strftime("%z")
        gmt_formatted = f"{gmt_offset[:3]}:{gmt_offset[3:]}"

        return gmt_formatted
    

    def get_week_day(self, date_str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

        day_of_week = date_obj.weekday()
        WEEK_DAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

        return WEEK_DAYS[day_of_week]
    
#__________________CREATE APPOINTMENT NEW PATIENT_______________________
    async def create_appointment_new_patient(self, params : dict):
        logger.info(f"Params in create_appointment_new_patient function {params}")   
        print("START_DATE", params['starts_at'])
        
        params['practitioner_id'] = await self.get_practitioner_id(params={"doctor_name": params['doctor_name']})
        
        appointment_details = await self.get_appointment_details(params={"appointment_name": params['appointment_name']})
        params['appointment_type_id'] = appointment_details['ID']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_location_details(params= {"location": params['clinic_name']})
        print(business_details)
        params['business_id'] = business_details['ID']
        params['timezone'] = self.timezone
        params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])

        # Fetching phone number from the user's call
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

        try:
            # Convert and Extract date and Start time 
            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            starts_at_dt = datetime.fromisoformat(starts_at)
            start_date = starts_at_dt.date().isoformat()  # 'YYYY-MM-DD'
            start_time = starts_at_dt.time().isoformat()  # 'HH:MM:SS'
            
            # Convert and Extract date and End time 
            ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['Duration']), params['timezone'])
            end_time = self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['Duration'])
            end_at_dt = datetime.fromisoformat(end_time)
            end_time = end_at_dt.time().isoformat()  # 'HH:MM:SS'
            
            # Checking booking conflict
            list_bookings = await self.get_appointments(params={"practitioner_id": params['practitioner_id'], "location_id": params['business_id'], "date_from": start_date, "date_to": start_date, "time_from": start_time, "time_to": end_time})
            for appointment in list_bookings['data']['results']['appointments']:
                if appointment['status'] == "Pending":
                    return "Booking Conflict", 409
            
            # Cheking Doctor Availability
            doctor_available = await self.check_appointment_availability(
                params['business_id'], 
                params['practitioner_id'],
                starts_at,
                ends_at
                )
            
            availability = doctor_available['data']['results']['availabilities'].get(start_date, {})
            requested_time = datetime.fromisoformat(starts_at).strftime("%H:%M")

            if not availability:
                return "Doctor not available", 400

            if requested_time not in availability or availability[requested_time] == "unavailable":
                return "Doctor not available", 400
            
            # Checking if the patient exists.
            # If not, create a new patient
            patient_id = None
            patient_data= await self.search_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth']})
            for patient in patient_data['data']['results']['patients']:
                if patient['FirstName'] == params['first_name'] and patient['LastName'] == params['last_name'] and patient['DOB'] == params['date_of_birth'] and patient['Mobile'] == params['phone_number']:
                    patient_id = patient['ID']
                    print(f"Patient already exists: {patient}")
                    break
            print(f"Patient data: {patient_data}")

            if patient_id is None:
                logger.info(f"Creating new patient")
                patient_data= await self.add_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth'], "phone": params['phone_number']})

                if patient_data.get('data').get('results').get('patient_id') is not None:
                    patient_id = patient_data['data']['results']['patient_id']
                    
                    # Session Variable
                    set_user_data({
                        "id": patient_id,
                        'first_name': params['first_name'],
                        'last_name': params['last_name'],
                        'date_of_birth': params['date_of_birth'],
                        'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_NEW_PATIENT',
                        'phone_number': params['phone_number']
                    })
                    print(f"Created new patient: {patient_data}")
                print(f"Patient data: {patient_data}")

                # Adding patient to dynamodb
                new_patient_data = {
                    "patient_id": str(patient_id),
                    "first_name": params['first_name'],
                    "last_name": params['last_name'],
                    "date_of_birth": params['date_of_birth'],
                    "phone_number": params['phone_number'],
                    "clinic_name": self.clinicData["name"],
                }
                add_patient_to_dynamo = await dynamo_client.add_patient("nookal-client", new_patient_data)
                print("Patient added to dynamo: ",add_patient_to_dynamo)
            
            else:
                patient_data = patient                                
                set_user_data({
                    "id": patient_id,
                    'first_name': patient_data['FirstName'],
                    'last_name': patient_data['LastName'],
                    'date_of_birth': patient_data['DOB'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_NEW_PATIENT',
                    'phone_number': patient_data['Mobile']
                })
                return "Patient already exists", 409

            appointment_attributes= {
                "location_id": params['business_id'],
                "appointment_date": start_date,
                "start_time": start_time,
                "patient_id": patient_id,
                "practitioner_id": params['practitioner_id'],
                "appointment_type_id": params['appointment_type_id'],
                "allow_overlap_bookings": False,
                "api_key": self.api_key,
            }

            appointment_attributes = parse.urlencode(appointment_attributes)
            url = f"{self.NOOKAL_BASE_URL}addAppointmentBooking?{appointment_attributes}"
            logger.info(f"Params in Create function {params}")

            try:
                logger.info(f"Making call to {url}")
                response = requests.get(url)
                return response.json(), 201
            except Exception as err:
                logger.error(f"Error in Nookal API create_appointment_new_patient: {err}")
                return None   
            
        except Exception as e:
            logger.error(f"Error in create_appointment_new_patient Nookal API: {e}")
            return f"Error: {e}", 500

#__________________CREATE APPOINTMENT EXISTING PATIENT_______________________
    async def create_appointment_existing_patient(self, params: dict):
        logger.info(f"Params in create_appointment_existing_patient function {params}")
        print("START_DATE", params['starts_at'])
        
        params['practitioner_id'] = await self.get_practitioner_id(params={"doctor_name": params['doctor_name']})
        
        appointment_details = await self.get_appointment_details(params={"appointment_name": params['appointment_name']})
        params['appointment_type_id'] = appointment_details['ID']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_location_details(params= {"location": params['clinic_name']})
        print(business_details)
        params['business_id'] = business_details['ID']
        params['timezone'] = self.timezone
        params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])
        
        try:
            # Convert and Extract date and Start time 
            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            starts_at_dt = datetime.fromisoformat(starts_at)
            start_date = starts_at_dt.date().isoformat()  # 'YYYY-MM-DD'
            start_time = starts_at_dt.time().isoformat()  # 'HH:MM:SS'

            # Convert and Extract date and End time 
            ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['Duration']), params['timezone'])
            end_time = self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['Duration'])
            end_at_dt = datetime.fromisoformat(end_time)
            end_time = end_at_dt.time().isoformat()  # 'HH:MM:SS'
            
            # Checking booking conflict
            list_bookings = await self.get_appointments(params={"practitioner_id": params['practitioner_id'], "location_id": params['business_id'], "date_from": start_date, "date_to": start_date, "time_from": start_time, "time_to": end_time})
            for appointment in list_bookings['data']['results']['appointments']:
                if appointment['status'] == "Pending":
                    return "Booking Conflict", 409

            # Cheking Doctor Availability
            doctor_available = await self.check_appointment_availability(
                params['business_id'], 
                params['practitioner_id'],
                starts_at,
                ends_at
                )

            availability = doctor_available['data']['results']['availabilities'].get(start_date, {})
            requested_time = datetime.fromisoformat(starts_at).strftime("%H:%M")

            if not availability:
                return "Doctor not available", 400
            
            if requested_time not in availability or availability[requested_time] == "unavailable":
                return "Doctor not available", 400
            
            #get phone number from retell call
            if IS_LOCAL:
                call_number = self.local_number  # Local testing number
                print("Running locally. Using test number:", call_number)
                normalized_number = await self.normalize_phone_number(call_number)
                params['phone_number'] = normalized_number
                print("Normalized Number inside existing patient function:", params['phone_number'])

            elif params.get('phone_number') is None or params.get('phone_number') == "None":
                call_number = await self.get_phone_number()
                print("Call Info:", call_number)
                normalized_number = await self.normalize_phone_number(call_number)
                params['phone_number'] = normalized_number
                print("Normalized Number inside existing patient function:", params['phone_number'])


            # Checking if the patient exists.
            patient_id = None
            patient_data= await self.search_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth']})
            for patient in patient_data['data']['results']['patients']:
                print("Patient data", patient)
                if patient['FirstName'] == params['first_name'] and patient['LastName'] == params['last_name'] and patient['DOB'] == params['date_of_birth'] and patient['Mobile'] == params['phone_number']:
                    patient_id = patient['ID']
                    print(f"Patient already exists: {patient}")
                    break
            
            # Setting user data
            if patient_id is None:
                set_user_data({
                    "id": None,
                    'first_name': params['first_name'],
                    'last_name': params['last_name'],
                    'date_of_birth': params['date_of_birth'],
                    'phone_number': params['phone_number'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_EXISTING_PATIENT',
                })
                return "Patient not found", 404
            else:
                patient_data = patient                                
                set_user_data({
                    "id": patient_id,
                    'first_name': patient_data['FirstName'],
                    'last_name': patient_data['LastName'],
                    'date_of_birth': patient_data['DOB'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_EXISTING_PATIENT',
                    'phone_number': patient_data['Mobile']
                })

            appointment_attributes= {
                "location_id": params['business_id'],
                "appointment_date": start_date,
                "start_time": start_time,
                "patient_id": patient_id,
                "practitioner_id": params['practitioner_id'],
                "appointment_type_id": params['appointment_type_id'],
                "allow_overlap_bookings": False,
                "api_key": self.api_key,
            }

            appointment_attributes = parse.urlencode(appointment_attributes)
            url = f"{self.NOOKAL_BASE_URL}addAppointmentBooking?{appointment_attributes}"
            logger.info(f"Params in Create function {params}")
            
            try:
                logger.info(f"Making call to {url}")
                response = requests.get(url)
                return response.json(), 201
            except Exception as err:
                logger.error(f"Error in Nookal API create_appointment_existing_patient: {err}")
                return None
            
        except Exception as e:
            logger.error(f"Error in create_appointment_existing_patient: {e}")
            return f"Error: {e}", 500
        
#__________________UPDATE INDIVIDUAL APPOINTMENT_______________________
    async def update_individual_appointment(self, params: dict):
        logger.info(f"Params in update_individual_appointment function {params}")

        #get phone number from retell call
        if IS_LOCAL:
            call_number = self.local_number  # Local testing number
            print("Running locally. Using test number:", call_number)
            normalized_number = await self.normalize_phone_number(call_number)
            params['phone_number'] = normalized_number
            print("Normalized Number inside update patient function:", params['phone_number'])

        elif params.get('phone_number') is None or params.get('phone_number') == "None":
            call_number = await self.get_phone_number()
            print("Call Info:", call_number)
            normalized_number = await self.normalize_phone_number(call_number)
            params['phone_number'] = normalized_number
            print("Normalized Number inside update patient function:", params['phone_number'])

        # Check if the patient exists
        patient_id = None
        patient_data= await self.search_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth']})
        for patient in patient_data['data']['results']['patients']:
            if patient['FirstName'] == params['first_name'] and patient['LastName'] == params['last_name'] and patient['DOB'] == params['date_of_birth'] and patient['Mobile'] == params['phone_number']:
                patient_id = patient['ID']
                break
                
        # Set user data
        if patient_id is not None:
            patient_data = patient
            set_user_data({
                "id": patient_id,
                'first_name': patient_data['FirstName'],
                'last_name': patient_data['LastName'],
                'date_of_birth': patient_data['DOB'],
                'call_type': 'INBOUND_CANCEL',
                'phone_number': patient_data['Mobile']
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

        # Get appointments for the patient
        appointments = await self.get_appointments(params={"patient_id": patient_id})
        appointment_found = False

        # Filter appointments to update
        for appointment in appointments['data']['results']['appointments']:
            params['timezone'] = appointment['TimeZone']
            params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])
            datetime_obj = datetime.strptime(f"{appointment['appointmentDate']} {appointment['appointmentStartTime']}", "%Y-%m-%d %H:%M:%S")
            datetime_str = datetime_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

            if datetime_str == params['old_start_date'] and appointment['status'] == "Pending":
                params['practitioner_id'] = appointment['practitionerID']
                params['business_id'] = appointment['locationID']
                params['appointment_type_id'] = appointment['appointmentTypeID']
                params['appointment_id'] = appointment['ID']

                appointment_type = await self.get_appointment_details_by_id(params={"appointment_type_id": params['appointment_type_id']})
                params['duration_in_minutes'] = appointment_type['Duration']
                params['appointment_name'] = appointment_type['Name']
                appointment_found = True
                break

        if not appointment_found:
            return 'Appointment not found', 404
                                
        try:
            # Convert and Extract date and Start time 
            new_starts_at = self.convert_timezone(params['new_starts_date'], params['timezone'])
            starts_at_dt = datetime.fromisoformat(new_starts_at)
            new_start_date = starts_at_dt.date().isoformat()  # 'YYYY-MM-DD'
            new_start_time = starts_at_dt.time().isoformat()  # 'HH:MM:SS'

            # Convert and Extract date and End time
            new_ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['new_starts_date'], params['duration_in_minutes']), params['timezone'])
            new_end_time = self.fix_end_time_for_appointment(params['new_starts_date'], params['duration_in_minutes'])
            end_at_dt = datetime.fromisoformat(new_end_time)
            new_end_time = end_at_dt.time().isoformat()  # 'HH:MM:SS'

            # Checking booking conflict
            list_bookings = await self.get_appointments(params={"practitioner_id": params['practitioner_id'], "location_id": params['business_id'], "date_from": new_start_date, "date_to": new_start_date, "time_from": new_start_time, "time_to": new_end_time})
            for appointment in list_bookings['data']['results']['appointments']:
                if appointment['status'] == "Pending":
                    return "Booking Conflict", 409

            # Cheking Doctor Availability
            doctor_available = await self.check_appointment_availability(
                params['business_id'], 
                params['practitioner_id'],
                new_starts_at,
                new_ends_at
                )

            availability = doctor_available['data']['results']['availabilities'].get(new_start_date, {})
            requested_time = datetime.fromisoformat(new_starts_at).strftime("%H:%M")
            
            if not availability:
                return "Doctor not available", 400

            if requested_time not in availability or availability[requested_time] == "unavailable":
                return "Doctor not available", 400
            
        except Exception as e:
            logger.error(f"Error in update appointment Nookal API: {e}")
            return None, 500

        # Update individual appointment
        appointment_attributes= {
                "appointment_id": params['appointment_id'],
                "location_id": params['business_id'],
                "appointment_date": new_start_date,
                "start_time": new_start_time,
                "patient_id": patient_id,
                "practitioner_id": params['practitioner_id'],
                "appointment_type_id": params['appointment_type_id'],
                "allow_overlap_bookings": False,
                "api_key": self.api_key,
            }
        
        appointment_attributes = parse.urlencode(appointment_attributes)
        url = f"{self.NOOKAL_BASE_URL}updateAppointmentBooking?{appointment_attributes}"
        logger.info(f"Params in update_individual_appointment function {params}")

        try:
            logger.info(f"Making call to {url}")
            response = requests.get(url)
            return response.json(), 200
        except Exception as err:
            logger.error(f"Error in Nookal API update_individual_appointment: {err}")
            return None
        
#__________________CANCEL INDIVIDUAL APPOINTMENT_______________________
    async def cancel_individual_appointment(self, params: dict,):
        logger.info(f"In cancel_individual_appointment function {params}")

        #get phone number from retell call
        if IS_LOCAL:
            call_number = self.local_number  # Local testing number
            print("Running locally. Using test number:", call_number)
            normalized_number = await self.normalize_phone_number(call_number)
            params['phone_number'] = normalized_number
            print("Normalized Number inside cancel function:", params['phone_number'])

        elif params.get('phone_number') is None or params.get('phone_number') == "None":
            call_number = await self.get_phone_number()
            print("Call Info:", call_number)
            normalized_number = await self.normalize_phone_number(call_number)
            params['phone_number'] = normalized_number
            print("Normalized Number inside cancel function:", params['phone_number'])

        try:
            # Check if the patient exists
            patient_id = None
            patient_data= await self.search_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth']})
            for patient in patient_data['data']['results']['patients']:
                if patient['FirstName'] == params['first_name'] and patient['LastName'] == params['last_name'] and patient['DOB'] == params['date_of_birth'] and patient['Mobile'] == params['phone_number']:
                    patient_id = patient['ID']
                    break

            # Set user data
            if patient_id is not None:
                patient_data = patient
                set_user_data({
                    "id": patient_id,
                    'first_name': patient_data['FirstName'],
                    'last_name': patient_data['LastName'],
                    'date_of_birth': patient_data['DOB'],
                    'call_type': 'INBOUND_CANCEL',
                    'phone_number': patient_data['Mobile']
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

            # Get appointments for the patient
            appointments = await self.get_appointments(params={"patient_id": patient_id})
            appointment_found = False
            for appointment in appointments['data']['results']['appointments']:
                print("-----------Appointment-------", appointment)
                params['timezone'] = appointment['TimeZone']
                params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])
                datetime_obj = datetime.strptime(f"{appointment['appointmentDate']} {appointment['appointmentStartTime']}", "%Y-%m-%d %H:%M:%S")
                datetime_str = datetime_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

                # Check if the appointment date and time match
                if datetime_str == params['starts_at'] and appointment['status'] == "Pending":                    
                    appointment_found = True

                    # Cancel individual appointment
                    appointment_attributes= {
                        "appointment_id": appointment['ID'],
                        "patient_id": appointment['patientID'],
                        "api_key": self.api_key,
                    }

                    appointment_attributes = parse.urlencode(appointment_attributes)
                    url = f"{self.NOOKAL_BASE_URL}cancelAppointment?{appointment_attributes}"

                    try:
                        response = requests.get(url)
                        return response.json(), 204
                    except Exception as err:
                        logger.error(f"Error Cancelling Appointment: {err}")
                        return None
                
            if appointment_found == False:
                return "Appointment not found", 404
            
        except Exception as e:
            logger.error(f"Error in {func_name} Nookal API: {e}")
            return None, 500
    
#__________________GET FREE AVAILABLE SLOT_______________________

    async def get_free_available_slot(self, params: dict, date):
        try:
            print("params in get free available slot", params)
            if params.get('practitioner_id') is None:
                params['practitioner_id'] = await self.get_practitioner_id(
                    params={"doctor_name": params['doctor_name']}
                )

            appointment_details = await self.get_appointment_details(
                params={"appointment_name": params['appointment_name']}
            )
            params['appointment_type_id'] = appointment_details['ID']
            params['appointment_type'] = appointment_details

            if params.get('business_id') is None:
                business_details = await self.get_location_details(
                    params={"location": params['clinic_name']}
                )
                params['business_id'] = business_details['ID']

            params['timezone'] = self.timezone
            params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])

            # Convert and Extract date and Start time
            starts_at = self.convert_timezone(date, params['timezone'])
            starts_at_dt = datetime.fromisoformat(starts_at)
            start_date = starts_at_dt.date().isoformat()
            user_time = starts_at_dt.time()  # used for filtering
            user_time_dt = datetime.strptime(user_time.isoformat(), "%H:%M:%S")

            # Determine preference type from params
            time_preference = params.get("time_preference", "closest")  # e.g., "after", "before", "exact", "closest"

            check_available_slot = await self.check_appointment_availability(
                params['business_id'],
                params['practitioner_id'],
                start_date,
                start_date
            )

            availability = check_available_slot['data']['results']['availabilities'][start_date]

            readable_times = []
            availability_slots = []
            time_slot_durations = {}
            first_available_slot = None

            sorted_slots = sorted(availability.keys(), key=lambda x: datetime.strptime(x, "%H:%M"))

            for i, time_slot in enumerate(sorted_slots):
                if availability[time_slot] == "available":
                    if first_available_slot is None:
                        first_available_slot = time_slot
                elif availability[time_slot] == "unavailable" and first_available_slot:
                    # Calculate duration between available and next unavailable slot
                    start_time = datetime.strptime(first_available_slot, "%H:%M")
                    end_time = datetime.strptime(time_slot, "%H:%M")
                    duration = (end_time - start_time).seconds // 60
                    appointment_duration = int(params['appointment_type']['Duration'])

                    if duration >= appointment_duration:
                        # Divide the slot into appointment-sized chunks
                        num_chunks = duration // appointment_duration
                        for j in range(num_chunks):
                            slot_time = start_time + timedelta(minutes=j * appointment_duration)
                            availability_slots.append(slot_time.strftime("%H:%M"))

                    first_available_slot = None

            print ("Availability Slots: ", availability_slots)

            filtered_slots = []
            available_datetimes = [datetime.strptime(slot, "%H:%M") for slot in availability_slots]
            print ("Available Datetimes: ", available_datetimes)

            if not available_datetimes:
                return [], 400, "no preferred time"

            if date.endswith("00:00:00Z"):
                print("time_preference == any")
                # Just return 2 earliest available slots
                for slot in availability_slots[:2]:
                    readable = await self.convert_readable_doctor_slots_timing_new(slot)
                    if readable:
                        readable_times.append(readable)
                return readable_times, 200, "no preferred time"
            
            if time_preference == "before":
                print("time_preference == before")
                filtered_slots = [dt for dt in available_datetimes if dt < user_time_dt]
                if filtered_slots:
                    closest_before = max(filtered_slots)
                    readable = await self.convert_readable_doctor_slots_timing_new(closest_before.strftime("%H:%M"))
                    return [readable], 200, "before"
                else:
                    return [], 404, "before"

            elif time_preference == "after":
                print("time_preference == after")
                filtered_slots = [dt for dt in available_datetimes if dt > user_time_dt]
                if filtered_slots:
                    closest_after = min(filtered_slots)
                    readable = await self.convert_readable_doctor_slots_timing_new(closest_after.strftime("%H:%M"))
                    return [readable], 200, "after"
                else:
                    return [], 404, "after"

            elif time_preference == "exact":
                print("time_preference == exact")
                target_time = user_time_dt.replace(second=0, microsecond=0)
                exact_matches = []
                for dt in available_datetimes:
                    print("dt: ", dt)
                    if dt.replace(second=0, microsecond=0) == target_time:
                        exact_matches.append(dt)
                if exact_matches:
                    readable = await self.convert_readable_doctor_slots_timing_new(exact_matches[0].strftime("%H:%M"))
                    return [readable], 200, "exact"
                else:
                    logger.warning(f"The exact slot at {target_time.strftime('%I:%M %p')} is already booked.")
                    closest = min(available_datetimes, key=lambda dt: abs(dt - target_time))
                    readable = await self.convert_readable_doctor_slots_timing_new(closest.strftime("%H:%M"))
                    return [readable], 200, "slot already booked"

            elif time_preference == "closest":
                print("time_preference == closest")
                closest = min(available_datetimes, key=lambda dt: abs(dt - user_time_dt))
                readable = await self.convert_readable_doctor_slots_timing_new(closest.strftime("%H:%M"))
                print("Closest readable time: ", readable)
                return [readable], 200, "closest"
            else:
                print("Unknown time preference, returning empty list")
                return [], 400, "no preferred time"

        except Exception as e:
            logger.error(f"Error in get_free_available_slot Nookal API: {e}")
            return f"Error: {e}", 500, "no preferred time"
    

    def format_human_readable_date(self, date_obj):
        import calendar
        day = date_obj.day
        suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return f"{day}{suffix} {calendar.month_name[date_obj.month]}"

    async def get_next_available_slot(self, params: dict, date):
        try:
            print("params in get free available slot", params)

            if params.get('practitioner_id') is None:
                params['practitioner_id'] = await self.get_practitioner_id(params={"doctor_name": params['doctor_name']})

            appointment_details = await self.get_appointment_details(params={"appointment_name": params['appointment_name']})
            params['appointment_type_id'] = appointment_details['ID']
            params['appointment_type'] = appointment_details

            if params.get('business_id') is None:
                business_details = await self.get_location_details(params={"location": params['clinic_name']})
                print(business_details)
                params['business_id'] = business_details['ID']

            params['timezone'] = self.timezone
            params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])

            # Iterate up to 30 days in future to find the next available slot
            max_days_to_check = 30
            for day_offset in range(max_days_to_check):
                check_date = datetime.fromisoformat(date) + timedelta(days=day_offset)
                start_date = check_date.date().isoformat()
                readable_date = self.format_human_readable_date(check_date)

                check_available_slot = await self.check_appointment_availability(
                    params['business_id'],
                    params['practitioner_id'],
                    start_date,
                    start_date
                )

                availabilities = check_available_slot['data']['results']['availabilities']
                if start_date not in availabilities:
                    continue

                availability = availabilities[start_date]
                readable_times = []
                availability_slots = []
                time_slot_durations = {}
                first_available_slot = None

                sorted_slots = sorted(availability.keys(), key=lambda x: datetime.strptime(x, "%H:%M"))

                # If checking today's date, skip past time slots
                clinic_tz = pytz.timezone(params['timezone'])
                now = datetime.now(clinic_tz)
                is_today = check_date.date() == now.date()

                for i, time_slot in enumerate(sorted_slots):
                    slot_time_obj = datetime.strptime(time_slot, "%H:%M").time()

                    if is_today and slot_time_obj <= now.time():
                        print("Condition hit, INSIDE IF")
                        continue

                    if availability[time_slot] == "available":
                        if first_available_slot is None:
                            first_available_slot = time_slot
                    elif availability[time_slot] == "unavailable" and first_available_slot:
                        start_time = datetime.strptime(first_available_slot, "%H:%M")
                        end_time = datetime.strptime(time_slot, "%H:%M")
                        duration = (end_time - start_time).seconds // 60
                        time_slot_durations[first_available_slot] = duration
                        first_available_slot = None

                appointment_duration = int(params['appointment_type']['Duration'])
                availability_slots = [slot for slot, dur in time_slot_durations.items() if dur >= appointment_duration]

                for slot in availability_slots:
                    converted_time = await self.convert_readable_doctor_slots_timing_new(slot)
                    if converted_time:
                        full_readable_time = f"{readable_date}, {converted_time}"
                        readable_times.append(full_readable_time)

                if readable_times:
                    return readable_times[0:1], 200  # Return top 2 results

            return "No available slots in the next 30 days.", 404

        except Exception as e:
            logger.error(f"Error in get_free_available_slot Nookal API: {e}")
            return f"Error: {e}", 500    
        
#__________________GET PATIENT APPOINTMENTS_______________________
    async def get_patient_pending_appointments(self, params: dict):
        # Check if the patient exists
        print("params in get_patient_pending_appointment", params)

        #get phone number from retell call
        if IS_LOCAL:
            call_number = self.local_number  # Local testing number
            print("Running locally. Using test number:", call_number)
            normalized_number = await self.normalize_phone_number(call_number)
            params['phone_number'] = normalized_number
            print("Normalized Number inside get patient appointment function:", params['phone_number'])

        elif params.get('phone_number') is None or params.get('phone_number') == "None":
            call_number = await self.get_phone_number()
            print("Call Info:", call_number)
            normalized_number = await self.normalize_phone_number(call_number)
            params['phone_number'] = normalized_number
            print("Normalized Number inside get patient appointment function:", params['phone_number'])

            
        patient_id = None
        patient_data= await self.search_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth']})
        for patient in patient_data['data']['results']['patients']:
            if patient['FirstName'] == params['first_name'] and patient['LastName'] == params['last_name'] and patient['DOB'] == params['date_of_birth'] and patient['Mobile'] == params['phone_number']:
                patient_id = patient['ID']
                break

        # Set user data
        if patient_id is not None:
            patient_data = patient
            set_user_data({
                "id": patient_id,
                'first_name': patient_data['FirstName'],
                'last_name': patient_data['LastName'],
                'date_of_birth': patient_data['DOB'],
                'call_type': 'INBOUND_CANCEL',
                'phone_number': patient_data['Mobile']
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
        
        appointment_found=False
        # Get appointments for the patient
        appointments = await self.get_appointments(params={"patient_id": patient_id})
        print("all appointments", appointments)
        data=[]
        practitioner_name = []
        location_name = []
        for appointment in appointments['data']['results']['appointments']:
            print("single appointment", appointment)
            params['timezone'] = appointment['TimeZone']
            practitioner_id = appointment['practitionerID']
            location_id = appointment['locationID']
            params['GMT'] = await self.convert_timezone_to_gmt(params['timezone'])
            datetime_obj = datetime.strptime(f"{appointment['appointmentDate']} {appointment['appointmentStartTime']}", "%Y-%m-%d %H:%M:%S")
            datetime_str = datetime_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
            print("datetime_str", datetime_str)
            test= datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            print("test_time", test)
            # Check if the appointment time is in the future and the status is pending
            if datetime_str > datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ") and appointment['status'] == "Pending":
                print("Inside final if")
                appointment_found=True
                converted = await self.convert_pending_appointments_to_readable(datetime_str)
                print("Converted", converted)
                data.append(converted)

                doctor_name = await self.get_practitioner_name_from_id(params={"practitioner_id": practitioner_id})
                practitioner_name.append(doctor_name)
                
                location_name_= await self.get_location_name_from_id(params={"location_id": location_id})
                location_name.append(location_name_)

        if appointment_found is False:
            return "Appointment not found", "No practitioner found", "location not found", 404  
                      
        return data, practitioner_name, location_name, 200
        
#__________________CONVERT READABLE DOCTOR SLOT_______________________
    async def convert_readable_doctor_slots_timing_new(self, time_str):
        try:
            if isinstance(time_str, list):
                time_str = time_str[0]  # Extract the first element if it's a list

            # Ensure time_str is a valid string
            if not isinstance(time_str, str):
                raise ValueError(f"Invalid time format received: {time_str}")

            # Convert time string (assuming `HH:MM`)
            dt = datetime.strptime(time_str, "%H:%M")

            # Format time to readable format
            formatted_time = dt.strftime("%I:%M %p").lower().strip()

            return formatted_time

        except Exception as e:
            logger.error(f"Error converting doctor slot timing: {e}")
            return None

    async def convert_pending_appointments_to_readable(self , iso_string):
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

#__________________SUMMARIZE AVAILABLE TIMES_______________________
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
    
#__________________FUNCTIONS FOR REQUIRED ENDPOINTS_______________________
    async def check_appointment_availability(
        self, location_id, practitioner_id, date_from, date_to
    ):
        params = {
            "location_id": location_id,
            "practitioner_id": practitioner_id,
            "date_from": date_from,
            "date_to": date_to,
            "api_key": self.api_key,
        }
        params = parse.urlencode(params)
        url = f"{self.NOOKAL_BASE_URL}getAppointmentAvailabilities?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error fetching appointment availability: {err}")
            return None

    async def search_patient(
        self,
      params,
    ):
        # NEEDED PARAMS
        # first_name , last_name , date_of_birth
        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        print(params)
        try:
            response = requests.get(
                f"{self.NOOKAL_BASE_URL}searchPatients?{params}"
            )
            return response.json()
        except Exception as err:
            logger.error(f"Error searching patient: {err}")
            return None

    async def add_patient(self, params):
        # NEEDED PARAMS
        # first_name , last_name , date_of_birth , email , phone_number

        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        print(params)
       
        url = f"{self.NOOKAL_BASE_URL}addPatient?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error adding patient: {err}")
            return None
       
    async def get_appointments(self , params):
        # NEEDED PARAMS
        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        
        url = f"{self.NOOKAL_BASE_URL}getAppointments?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error Cancelling Appointment: {err}")
            return None
        
    async def get_appointment_id(self, params):
        response = await self.get_appointments(params=params)
        appointments = response.get("data", {}).get("results", {}).get("appointments", [])
        print("APPOINTMENTS----", appointments)
        if appointments:
            for appointment in appointments:
                if appointment["cancelled"] == '1':
                    continue
                appointment_id = appointment.get("ID")  # Extract the ID of the first appointment
                return appointment_id
        else:
            logger.error("No appointments found")
            return None
        
    async def get_patient_id(self, params):
        response = await self.search_patient(params=params)
        patients = response.get("data", {}).get("results", {}).get("patients", [])
        print("PATIENTS----", patients)
        if patients:
            patient_id = patients[0].get("ID")  # Extract the ID of the first patient
            return patient_id
        else:
            logger.error("No patients with given name found")
            return None
        
    async def get_practitioner_id(self, params):
        response = await self.get_practitioners(params=params)
        practitioners = response.get("data", {}).get("results", {}).get("practitioners", [])
        for practitioner in practitioners:
            if params["doctor_name"] == practitioner["FirstName"] + " " + practitioner["LastName"]:
                print("PRACTITIONER FOUND----", practitioner) 
                practitioner_id = practitioner.get("ID")  # Extract the ID of the first practitioner
                return practitioner_id
        else:
            logger.error("No practitioners with given name found")
            return None
        
    async def get_practitioner_name_from_id(self, params):
        response = await self.get_practitioners(params=params)
        practitioners = response.get("data", {}).get("results", {}).get("practitioners", [])
        for practitioner in practitioners:
            print("PRACTITIONER----", practitioner)
            if params["practitioner_id"] == practitioner["ID"]:
                print("PRACTITIONER FOUND----", practitioner)
                practitioner_name = practitioner["FirstName"] + " " + practitioner["LastName"]  # Extract the ID of the first practitioner
                return practitioner_name
        else:
            logger.error("No practitioners with given ID found")
            return None
    
    async def get_location_name_from_id(self, params):
        response = await self.get_locations(params=params)
        locations = response.get("data", {}).get("results", {}).get("locations", [])
        for location in locations:
            print("locations----", location)
            if params["location_id"] == location["ID"]:
                print("location FOUND----", location)
                location_name = location["Name"]  # Extract the ID of the first location
                return location_name
        else:
            logger.error("No locations with given ID found")
            return None
        
    async def get_practitioners(self, params):
        logger.info(f"Getting All Practitioners")
        # Ensure params is not overwritten, just add the API key
        if not isinstance(params, dict):
            logger.error("params should be a dictionary")
            return None

        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        print(params)
        
        url = f"{self.NOOKAL_BASE_URL}getPractitioners?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error Cancelling Appointment: {err}")
            return None
        
    async def get_all_appointment_type(self, params):
        logger.info("Getting All Appointment Types")
        params["api_key"] = self.api_key
        params["page_length"] = "200"
        all_appointments = []
        page = 1

        async with aiohttp.ClientSession() as session:
            while True:
                params["page"] = str(page)
                encoded_params = parse.urlencode(params)
                url = f"{self.NOOKAL_BASE_URL}getAppointmentTypes?{encoded_params}"
                
                try:
                    async with session.get(url) as response:
                        data = await response.json()

                        # Handle case where response is a list instead of expected dict
                        if isinstance(data, list):
                            logger.error(f"Unexpected list response from API at page {page}: {data}")
                            return all_appointments

                        # Ensure 'data' is a dictionary
                        if not isinstance(data, dict):
                            logger.error(f"Unexpected response format at page {page}: {type(data)} - {data}")
                            return all_appointments
                        
                        # Ensure 'data' contains a dictionary
                        nested_data = data.get("data", {})
                        if not isinstance(nested_data, dict):
                            logger.error(f"Unexpected 'data' structure at page {page}: {nested_data}")
                            return all_appointments
                        
                        # Ensure 'results' is a dictionary
                        results = nested_data.get("results", {})
                        if not isinstance(results, dict):
                            logger.error(f"Unexpected 'results' structure at page {page}: {results}")
                            return all_appointments
                        
                        # Ensure 'services' is a list
                        appointment_types = results.get("services", [])
                        if not isinstance(appointment_types, list):
                            logger.error(f"Unexpected 'services' structure at page {page}: {appointment_types}")
                            return all_appointments
                        
                        if not appointment_types:
                            logger.info(f"No more services available at page {page}, stopping pagination.")
                            break  # No more appointments, exit loop
                        
                        all_appointments.extend(appointment_types)
                        page += 1  # Move to next page

                except aiohttp.ClientError as client_err:
                    logger.error(f"HTTP request error at page {page}: {client_err}")
                    return all_appointments
                except Exception as err:
                    logger.error(f"Unexpected error at page {page}: {err}")
                    return all_appointments
        
        return all_appointments

    async def get_locations(self , params):
        logger.info(f"Getting Locations")
        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        print(params)
        
        url = f"{self.NOOKAL_BASE_URL}getLocations?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error Getting Location: {err}")
            return None
        
    async def get_location_details(self , params):
        logger.info("Getting Location Details")
        response = await self.get_locations(params=params)
        locations = response.get("data", {}).get("results", {}).get("locations", [])
        for location in locations:
            if params["location"] == location["Name"]:
                print("LOCATION FOUND----", location) 
                return location
        else:
            logger.error("No location with given name found")
            return None

    async def get_location_id(self , params):
        logger.info("Getting Location Details")
        response = await self.get_locations(params=params)
        locations = response.get("data", {}).get("results", {}).get("locations", [])
        for location in locations:
            if params["location"] == location["Name"]:
                print("LOCATION FOUND----", location) 
                return location['ID']
        else:
            logger.error("No practitioners with given name found")
            return None
        
    async def get_appointment_details(self, params):
        appointment_types = await self.get_all_appointment_type(params=params)
        if not appointment_types:
            logger.error("No appointment types found")
            return None

        for appointment_type in appointment_types:
            if params["appointment_name"] == appointment_type["Name"]:
                print("Appointment Type Found----", appointment_type)
                return appointment_type
        
        logger.error("No matching appointment type found")
        return None
        
    async def get_appointment_details_by_id(self , params):
        appointment_types = await self.get_all_appointment_type(params=params)
        if not appointment_types:
            logger.error("No appointment types found")
            return None
        
        for appointment_type in appointment_types:
            if params["appointment_type_id"] == appointment_type["ID"]:
                print("Appointment Type Found----", appointment_type) 
                return appointment_type
            
        logger.error("No matching appointment type found")
        return None
    
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
        print("Params in get_patient_data_from_dynamo:", params)

        try:
            #initialize important variables
            found_patient = None
            matching_patients=[]
            patient_id = None

            if ( params.get("first_name") not in [None, "None"] and params.get("last_name") not in [None, "None"] and params.get("date_of_birth") not in [None, "None"]):
                patient_data= await self.search_patient(params={"first_name": params['first_name'], "last_name": params['last_name'], "date_of_birth": params['date_of_birth']})
                for patient in patient_data['data']['results']['patients']:
                    if patient['FirstName'] == params['first_name'] and patient['LastName'] == params['last_name'] and patient['DOB'] == params['date_of_birth']:
                        patient_id = patient['ID']
                        print(f"Patient already exists: {patient}")
                        break
                print(f"Patient data: {patient_data}")

                if patient_id is None:
                    return "Patient not found", 404
                else:
                    print("Patient found")
                    found_patient = {
                        "first_name": params["first_name"],
                        "last_name": params["last_name"],
                        "date_of_birth": params["date_of_birth"],
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
            logger.error(f"Error in get_patient_data_from_dynamo: {e}")
            return f"Error: {e}", 500
