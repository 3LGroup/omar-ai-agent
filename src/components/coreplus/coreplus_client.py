from collections import defaultdict
import os
from urllib.parse import urlencode
import aiohttp
import jwt
import requests
from src.logger import logger
from datetime import datetime, timedelta , timezone
import pytz
from src.db.db import DB
from src.utils.session_vars import set_user_data
db = DB()

class CoreplusClient:
    def __init__(self):
        self.COREPLUS_CONSUMER_ID = os.environ.get("COREPLUS_CONSUMER_ID")
        self.COREPLUS_SECRET_KEY = os.environ.get("COREPLUS_SECRET_KEY")
        self.COREPLUS_ACCESS_TOKEN = os.environ.get("COREPLUS_ACCESS_TOKEN")
        self.COREPLUS_BASE_URL = os.environ.get("COREPLUS_BASE_URL")
        self.business_data = self.get_business_sync()
        
    ### -------------------------GENERATE JWT TOKEN---------------------###
    def generate_jwt(self , url , httpMethod , params = None):
        """
        Generate a JWT token for authenticating with the COREPLUS API.
        """
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
            
        claims = {
            "iss": "https://sandbox.coreplus.com.au",
            "aud": "https://sandbox.coreplus.com.au",
            "nbf": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(seconds=60),
            "consumerId": self.COREPLUS_CONSUMER_ID,
            "accessToken": self.COREPLUS_ACCESS_TOKEN,
            "url": url,
            "httpMethod": httpMethod
        }

        try:
            encoded_jwt = jwt.encode(claims, self.COREPLUS_SECRET_KEY, algorithm='HS256')
            return encoded_jwt if isinstance(encoded_jwt, str) else encoded_jwt.decode('utf-8')
        except Exception as e:
            logger.error(f"Error creating JWT: {e}")
            return None
        
    ###-------------------------GET BUSINESS DETAILS---------------------###
    def get_business_sync(self):
        """
        Synchronously fetch business data from the COREPLUS API.
        """
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/location/"
        jwt_token = self.generate_jwt(url, "GET")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500
        
        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
            data = response.json()
            return data, response.status_code
        except requests.RequestException as e:
            logger.error(f"Error in getting all business Coreplus API: {e}")
            return None, 500
        
    async def get_business_details(self , clinic_name):
        """
        Get Details of a clinic from all available business.
        """
        logger.info("Getting Location Details")
        response , status = self.business_data
        businesses = response["locations"]
        for business in businesses:
            if clinic_name == business["name"]:
                timezone = business["timeZone"]["tzName"]
                timezone_id= business["timeZone"]["timezoneId"]
                timezone = timezone.replace("\\", "/")
                gmt = await self.convert_timezone_to_gmt(timezone)
                business_details = {
                    "timezone" : timezone,  
                    "timezone_id" : timezone_id,
                    "id" : business["locationId"],
                    "clinic_name" : business["name"],
                    "GMT" : gmt
                }
                return business_details
        else:
            logger.error("No clinic with given name found")
            return None
        
    ### -------------------------GET APPOINTMENT TYPES---------------------### 
    async def get_all_appointment_types(self):
        """
        Fetch All appointment types from the COREPLUS API.
        """
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/appointmenttype/"
        jwt_token = self.generate_jwt(url, "GET")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500
        
        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers , timeout=10) as response:
                    data = await response.json()
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in getting all appointment types Coreplus API: {e}")
            return None, 500
    
    async def get_appointment_type_details(self , appointment_name):
        """
        Get the details of an appointment type, given its name.
        """
        response, status = await self.get_all_appointment_types()
        appointment_types = response["appointmentTypes"]
        for appointment_type in appointment_types:
            if appointment_name == appointment_type["description"]:
                appointment_id = appointment_type["appointmentTypeId"]
                appointment_type_duration = appointment_type["durationMinutes"]
                appointment_type_details = {
                    "id": appointment_id,
                    "duration_in_minutes": appointment_type_duration,
                    "name" : appointment_type["description"]
                }
                return appointment_type_details
        else:
            logger.error("No appointment types found")
            return None
        
    ###-------------------------GET PRACTITIONERS DETAILS---------------------###
    async def get_all_practitioners(self):
        """
        Fetch all practitioners data from the COREPLUS API.
        """
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/Practitioner/"
        jwt_token = self.generate_jwt(url, "GET")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500
        
        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    data = await response.json()
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in getting all practitioners details Coreplus API: {e}")
            return None, 500
        
    async def get_practitioner_id(self , practitioner_name):
        """
        Get the Id of a practitioner, given its name.
        """
        response , status = await self.get_all_practitioners()
        practitioners = response["practitioners"]
        for practitioner in practitioners:
            if practitioner_name == practitioner["firstName"] + " " + practitioner["lastName"]:
                return practitioner
        else:
            logger.error("No practitioners with given name found")
            return None
    
    ###-------------------------CONVERT TIMEZONE TO GMT---------------------###
    async def convert_timezone_to_gmt(self , timezone_identifier):
        """
        Converts Timezone Identifier to GMT
        """
        # Get the timezone object
        tz = pytz.timezone(timezone_identifier)

        # Get the current time in that timezone
        now = datetime.now(tz)

        # Format the offset as GMT
        gmt_offset = now.strftime("%z")
        gmt_formatted = f"{gmt_offset[:3]}:{gmt_offset[3:]}"

        return gmt_formatted
    
    ###-------------------------SUMMARIZE AVAILABLE TIMESLOTS---------------------###
    async def summarize_available_times(self, data, min_gap_hours=2):
        """
        Summarizes Available Time Slots
        """
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
    
    ###-------------------------CONVERT READABLE TIME SLOTS---------------------###
    async def convert_readable_doctor_slots_timing(self , iso_string , timezone):
        """
        Converts Available Time Slots to Readable Format
        """
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
        
        formatted_date = f"{day}{date_suffix} {dt.strftime('%B')}"
        
        # Format the time to a readable format with minutes
        formatted_time = dt.strftime("%I:%M %p").lower().strip()
        
        return f"{formatted_date} {formatted_time}"
        
    ###-------------------------LIST ALL PATIENTS---------------------###
    async def list_patients(self, params):
        """
        Lists all patients using the given parameters.
        Filters include name, mobile, email, and more as per CorePlus API.
        """
        logger.info(f"Params in list_patients function: {params}")
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/client/"
        jwt_token = self.generate_jwt(url, "GET", params)
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500

        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    logger.info(f"Response Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        return data, response.status
                    else:
                        print("Response" , response)
                        logger.error(f"Error response: {await response.text()}")
                        return None, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in list_patients Coreplus API: {e}")
            return None, 500    
        
    ###-------------------------ADD PATIENT---------------------###
    async def add_patient(self, params: dict, skip_patient_check=False):
        """
        Adds a new patient with given parameters
        """
        logger.info(f"Params in add_patient function Coreplus {params}")
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/client/"
        jwt_token = self.generate_jwt(url, "POST")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500

        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

        if not skip_patient_check:
            # Check if patient with same details
            patients, status = await self.list_patients(params={
            "name": params['first_name'],
            "dateOfBirth": params['date_of_birth'],
            "mobile": params['phone_number'],
        })
            print("Patients------", patients)
        
            if status == 200 and patients['paging']['totalRows'] > 0:
                logger.info(f"Patient with same data already exists" , patients)
                return "Patient with same data already exists", 409

        payload = {
            "firstName": params['first_name'],
            "lastName": params['last_name'],
            "dateOfBirth": params['date_of_birth'],
            "phoneNumberMobile": params['phone_number'],
        }

        logger.info(f"Payload in create_patient function {payload}")

        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Sending request to {url}")
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data, response.status
                    else:
                        print("Response" , response)
                        logger.error(f"Error response: {await response.text()}")
                        return None, response.status
                
            except Exception as e:
                logger.error(f"Error in create_patient Coreplus API: {e}")
                return None
            
    ###-------------------------GET DOCTOR SLOTS---------------------###
    async def get_availabilities_slots(self, params: dict, date):
        """
        Gets Availability Slots with given parameters
        """
        params['practitioner'] = await self.get_practitioner_id(params['doctor_name'])
        params['practitioner_id'] = params['practitioner']['practitionerId']
        
        appointment_details = await self.get_appointment_type_details(params['appointment_name'])
        params['appointment_type_id'] = appointment_details['id']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_business_details(params['clinic_name'])
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = await self.convert_timezone_to_gmt(business_details['timezone'])
                
        url = f"{self.COREPLUS_BASE_URL}/api/core/v2.1/AvailabilitySlot/"

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

        try:
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
    
    
    ###-------------------------GET DOCTOR TIMINGS---------------------###
    async def get_doctor_timings(self, starts_at, ends_at, practitioner_id, timezone_id):
        """
        Function to Get doctor timings
        """
        starts_at = datetime.strptime(starts_at, "%Y-%m-%dT%H:%M:%S%z").date()
        ends_at = datetime.strptime(ends_at, "%Y-%m-%dT%H:%M:%S%z").date()

        # Convert the date to string format
        starts_at_date_str = starts_at.strftime("%Y-%m-%d")
        ends_at_date_str = ends_at.strftime("%Y-%m-%d")

        query = {
            "startDate" : starts_at_date_str,
            "endDate" : ends_at_date_str,
            "timezoneId": timezone_id,
            "practitionerId": practitioner_id,
        }
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/availabilityslot/"
        query_string = urlencode(query)
        full_url = f"{url}?{query_string}"
        logger.info(f"Fetching doctor timings from {url}")
        jwt_token = self.generate_jwt(full_url, "GET")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500
        
        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

        logger.info(f"Query parameters: {query}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, headers=headers, timeout=10) as response:
                    logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        return data, response.status
                    else:
                        print("Response" , response)
                        logger.error(f"Error response: {await response.text()}")
                        return None, response.status
                    
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error in fetching doctor availability from Cliniko API: {e}")
            return None, 500
    
    ###-------------------------GET ALL DOCTOR SLOTS---------------------###
    async def get_doctor_slots(self, params):
        """
        Function to Get doctor timings
        """
        slots, status = await self.get_doctor_timings(params)
        print("Slots", slots)
        if not slots:
            logger.error("No slots found")
            return None, 500
        
        slots = slots.get('timeslots', [])
        available_slots = []
        for slot in slots:
            start_time = slot['startDateTime'].replace(params['GMT'], "Z")
            end_time = slot['endDateTime'].replace(params['GMT'], "Z")
        # check if the appointment duration is possible within the start and end time
            if datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ") >= timedelta(minutes=params["duration_in_minutes"]):
                available_slots.append({
                'startDateTime': start_time,
                'endDateTime': end_time
                })
                
        return available_slots, 200 

    ###-------------------------GET NEXT DOCTOR SLOT---------------------###
    async def get_next_available_slot(self, params):
        """
        Function to Get next available doctor slot
        """
        slots, status = await self.get_doctor_timings(params)
        print("Slots", slots)
        if not slots:
            logger.error("No slots found")
            return None, 500

        slots = slots.get('timeslots', [])
        available_next_slot = []
        for slot in slots:
            start_time = slot['startDateTime'].replace(params['GMT'], "Z")
            end_time = slot['endDateTime'].replace(params['GMT'], "Z")
        # check if the appointment duration is possible within the start and end time

            if datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ") >= timedelta(minutes=params["duration_in_minutes"]):
                available_next_slot.append({
                'startDateTime': start_time,
                'endDateTime': end_time
                })
                
        return available_next_slot[0], 200
    

    async def get_specific_available_slot(self, params):
        """
        Function to Get the available doctor slot for a specific date and time
        """
        business_details = await self.get_business_details(params['clinic_name'])
        print(business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = business_details['GMT']

        slots, status = await self.get_doctor_timings(params)
        print("Slots", slots)
        if not slots:
            logger.error("No slots found")
            return None, 500
        try:
            slots = slots.get('timeslots', [])
            specific_available_slot = []
            for slot in slots:
                start_time = slot['startDateTime'].replace(params['GMT'], "Z")
                end_time = slot['endDateTime'].replace(params['GMT'], "Z")

                # check if the appointment duration is possible within the start and end time
                if datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ") >= timedelta(minutes=params["duration_in_minutes"]):
                    specific_available_slot.append({
                    'startDateTime': start_time,
                    'endDateTime': end_time
                    })

                    filtered_slots = await self.filter_slots_by_preferred_time(specific_available_slot, params['starts_at'])
                    readable_times = []

                    for item in filtered_slots:
                        converted = await self.convert_readable_doctor_slots_timing(item, params['timezone'])
                        readable_times.append(converted)

                    logger.info(f"Readable Time: {readable_times}")
                    return readable_times, 200
                else:
                    logger.error(f"Error fetching available times")
                    return None, status
        except Exception as e:
            logger.error(f"Error fetching available times: {e}")
            return None, status


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


    ###-------------------------CHECK AVAILABLE TIME---------------------### 

    async def check_available_time(self, starts_at, ends_at, practitioner_id, timezone_id):
        response, status = await self.get_doctor_timings(starts_at, ends_at, practitioner_id, timezone_id)

        if not response:
            logger.error(f"No data found, status: {status}")
            return "Not Available"

        daily_availabilities = response.get('timeslots', [])
        logger.info(f"Daily availabilities: {daily_availabilities}")

        doctor_timings = {}

        daily_timings = []
        for availability in daily_availabilities:
            timing = {
                "start_at": f"{availability['startDateTime']}",
                "end_at": f"{availability['endDateTime']}"
            }
            daily_timings.append(timing)

        doctor_timings = daily_timings
        logger.info(f"Processed timings for today: {daily_timings}")

        logger.info(f"Doctor timings: {doctor_timings}")

        for timeslot in doctor_timings:
            logger.info(f"Checking timings for {timeslot}")

            # Parse the patient's chosen time (just the time portion)
            patient_chosen_starts_at = datetime.strptime(starts_at, "%Y-%m-%dT%H:%M:%S%z").time()
            patient_chosen_ends_at = datetime.strptime(ends_at, "%Y-%m-%dT%H:%M:%S%z").time()

            logger.info(f"Patient chosen time: starts_at={patient_chosen_starts_at}, ends_at={patient_chosen_ends_at}")

            
            doctor_available_starts_at = timeslot['start_at']
            doctor_available_ends_at = timeslot['end_at']

            logger.info(f"Doctor available time: starts_at={doctor_available_starts_at}, ends_at={doctor_available_ends_at}")

            # Compare using only the time portion
            if datetime.strptime(doctor_available_starts_at, "%Y-%m-%dT%H:%M:%S%z").time() <= patient_chosen_starts_at and datetime.strptime(doctor_available_ends_at, "%Y-%m-%dT%H:%M:%S%z").time() >= patient_chosen_ends_at:
                logger.info("Doctor is available at the chosen time.")
                return "Available"

        logger.info("No matching time slot found for the chosen time.")
        return "Not Available"
    
    ###-------------------------CREATE APPOINTMENT FOR NEW PATIENT---------------------###
    async def create_appointment_new_patient(self, params : dict):
        logger.info(f"Params in create_appointment_new_patient function {params}")   
        print("START_DATE", params['starts_at'])
        
        params['practitioner'] = await self.get_practitioner_id(params['doctor_name'])
        params['practitioner_id'] = params['practitioner']['practitionerId']
        
        appointment_details = await self.get_appointment_type_details(params['appointment_name'])
        params['appointment_type_id'] = appointment_details['id']
        params["duration_in_minutes"] = appointment_details['duration_in_minutes']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_business_details(params['clinic_name'])
        print(business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = business_details['GMT']

        try:
            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']), params['timezone'])
        
        ### Check If Booking Conflict Exists Or Not ###
            booking , booking_status = await self.list_bookings(starts_at=starts_at, timezone_id=params['timezone_id'])
            #check if appointment booking conflict exists or not in between starts_at and ends_at 
            for appointment in booking['appointments']:
                existing_start = appointment['startDateTime'].replace(" ", "")
                existing_end = appointment['endDateTime'].replace(" ", "")
                
                # Check if the new appointment overlaps with the existing one
                if (existing_start < ends_at and existing_end > starts_at):
                    return "Booking Conflict", 409

        ### Check If Doctor or Slot is available at that time ###
            doctor_available = await self.check_available_time(  
                starts_at,
                ends_at,
                params['practitioner_id'],
                params['timezone_id'],
            )
            if doctor_available == "Not Available":
                return "Doctor not available", 400
            
        ### Checking if the patient exists. ###
            patient_data, patient_status = await self.list_patients(params={"mobile": params['phone_number']})

            print(f"Patient status: {patient_status}")
            print(f"Patient data: {patient_data}")

            if patient_status == 200 and patient_data['paging']['totalRows'] == 0:
                logger.info(f"Creating new patient")
                patient_data, status = await self.add_patient(params=params, skip_patient_check=True)
                print(f"Patient data for new patient: {patient_data}")
                patient_data = patient_data['client']

                patient_id = patient_data['clientId']  
                    
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

            else:
                patient_data = patient_data['clients'][0]
                print(f"Patient data for existing patient: {patient_data}")
                patient_id = patient_data['clientId']                            
                set_user_data({
                    "id": patient_id,
                    'first_name': params['first_name'],
                    'last_name': params['last_name'],
                    'date_of_birth': params['date_of_birth'],
                    'call_type': 'INBOUND_NEW_APPOINTMENT_FOR_NEW_PATIENT',
                    'phone_number': params['phone_number']
                })
                return "Patient already exists", 409
            print("Start Time:",params['starts_at'])

            url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/Appointment/"
            logger.info(f"Params in Create function {params}")
            jwt_token = self.generate_jwt(url, "POST")
            if not jwt_token:
                logger.error("Failed to generate JWT token.")
                return None, 500
            
            payload = {
                "appointmentTypeId": params["appointment_type_id"],
                "locationId": params['business_id'],
                "startDateTime": starts_at,
                "endDateTime": ends_at,
                "clients": [patient_data],
                "practitioner": {"practitionerId": params['practitioner']['practitionerId']}
            }
            
            logger.info(f"Payload in Create appointment function {payload}")

            headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                        data = await response.json()
                        return data, response.status
                except aiohttp.ClientError as e:
                    logger.error(f"Error in create_individual_appointment coreplus API: {e}")
                    return None, 500
                
        except Exception as e:
            logger.error(f"Error in create_appointment_new_patient: {e}")
            return f"Error: {e}", 500
        
    ###-------------------------CREATE APPOINTMENT FOR EXISTING PATIENT---------------------###
    async def create_appointment_existing_patient(self, params: dict):
        logger.info(f"Params in create_appointment_existing_patient function {params}")   
        print("START_DATE", params['starts_at'])
        
        params['practitioner'] = await self.get_practitioner_id(params['doctor_name'])
        params['practitioner_id'] = params['practitioner']['practitionerId']
        
        appointment_details = await self.get_appointment_type_details(params['appointment_name'])
        params['appointment_type_id'] = appointment_details['id']
        params["duration_in_minutes"] = appointment_details['duration_in_minutes']
        params['appointment_type'] = appointment_details
        
        business_details = await self.get_business_details(params['clinic_name'])
        print(business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = business_details['GMT']

        try:
            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['starts_at'], params['appointment_type']['duration_in_minutes']), params['timezone'])
            print("Returned value from convert_timezone: ", starts_at)

            booking , booking_status = await self.list_bookings(starts_at=starts_at, timezone_id=params['timezone_id'])
        ### Check if appointment booking conflict exists or not in between starts_at and ends_at 
            for appointment in booking['appointments']:
                existing_start = appointment['startDateTime'].replace(" ", "")
                existing_end = appointment['endDateTime'].replace(" ", "")
                
                # Check if the new appointment overlaps with the existing one
                if (existing_start < ends_at and existing_end > starts_at):
                    return "Booking Conflict", 409
        
        ### Check if doctor is available in between starts_at and ends_at   
            doctor_available = await self.check_available_time(  
                starts_at,
                ends_at,
                params['practitioner_id'],
                params['timezone_id'],
            )

            if doctor_available == "Not Available":
                return "Doctor not available", 400
            
            patients, patient_status = await self.get_patient_data_from_coreplus(params)
            print(f"Patient status: {patient_status}")
            print(f"Patient data: {patient_data}")

            if patient_status == 200 and patients['paging']['totalRows'] == 0:
                return "Patient not found", 404
            elif patient_status == 200 and patients['paging']['totalRows'] > 1:
                logger.info(f"Multiple patients found with same phone number")
                patient_data = patients['clients']
                return patient_data, 409 
            else:
                patient_data = patients['clients'][0]
                print(f"Patient data for existing patient: {patient_data}")
                print("Patient found")

            url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/Appointment/"
            logger.info(f"Params in Create function {params}")
            jwt_token = self.generate_jwt(url, "POST")
            if not jwt_token:
                logger.error("Failed to generate JWT token.")
                return None, 500
            
            payload = {
                "appointmentTypeId": params["appointment_type_id"],
                "locationId": params['business_id'],
                "startDateTime": starts_at,
                "endDateTime": ends_at,
                "clients": [patient_data],
                "practitioner": {"practitionerId": params['practitioner']['practitionerId']}
            }

            logger.info(f"Payload in Create appointment function {payload}")

            headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                        data = await response.json()
                        return data, response.status
                except aiohttp.ClientError as e:
                    logger.error(f"Error in create_individual_appointment coreplus API: {e}")
                    return None, 500

        except Exception as e:
            logger.error(f"Error in create_appointment_existing_patient: {e}")
            return f"Error: {e}", 500

    ###-------------------------UPDATE APPOINTMENT FOR PATIENT---------------------###
    async def update_individual_appointment(self, params: dict):
        logger.info(f"Params in update_individual_appointment function {params}")

        business_details = await self.get_business_details(params['clinic_name'])
        print(business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = business_details['GMT']
        starts_at = self.convert_timezone(params['old_start_date'], params['timezone'])

        ### Check if patient exists or not
        patients, patient_status = await self.get_patient_data_from_coreplus(params)
        print(f"Patient status: {patient_status}")
        print(f"Patient data: {patients}")
        
        if patient_status == 200 and patients['paging']['totalRows'] == 0:
            return "Patient not found", 404
        elif patient_status == 200 and patients['paging']['totalRows'] > 1:
            logger.info(f"Multiple patients found with same phone number")
            patient_data = patients['clients']
            return patient_data, 409 
        else:
            patient_data = patients['clients'][0]
            patient_id = patient_data['clientId']
            params['patient_id']= patient_id
            params['first_name'] = patient_data['firstName']
            params['last_name'] = patient_data['lastName']
            params['date_of_birth'] = patient_data['dateOfBirth']
            print(f"Patient data for existing patient: {patient_data}")
            print("Patient found")

        
        bookings, bookings_status = await self.list_bookings(starts_at, params['timezone_id'] , params['patient_id'])
        print(bookings)
        for booking in bookings['appointments']:
            if booking['startDateTime'].replace(" ", "") == starts_at:
                params['appointment_id'] = booking['appointmentId']
                params['practitioner_id'] = booking['practitioner']['practitionerId']
                # Parse start and end times as datetime objects
                start_time = datetime.fromisoformat(booking['startDateTime'].replace(" ", ""))
                end_time = datetime.fromisoformat(booking['endDateTime'].replace(" ", ""))
                
                # Calculate duration in minutes
                params['duration_in_minutes'] = int((end_time - start_time).total_seconds() / 60)
                break
        else:
            return "Appointment not found", 404
                                
        try:
            new_starts_at = self.convert_timezone(params['new_starts_date'], params['timezone'])
            new_ends_at = self.convert_timezone(self.fix_end_time_for_appointment(params['new_starts_date'], params['duration_in_minutes']), params['timezone'])

            booking , booking_status = await self.list_bookings(starts_at=new_starts_at, timezone_id=params['timezone_id'])
            #check if appointment booking conflict exists or not in between starts_at and ends_at 
            for appointment in booking['appointments']:
                existing_start = appointment['startDateTime'].replace(" ", "")
                existing_end = appointment['endDateTime'].replace(" ", "")
                
                # Check if the new appointment overlaps with the existing one
                if (existing_start < new_ends_at and existing_end > new_starts_at):
                    return "Booking Conflict", 409
                
            doctor_available = await self.check_available_time(
                new_starts_at,
                new_ends_at,
                params['practitioner_id'],
                params['timezone_id'],
            )

            if doctor_available == "Not Available":
                return "Doctor not available", 400
        
        except Exception as e:
            logger.error(f"Error in update appointment Coreplus API: {e}")
            return None, 500

        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/Appointment/{params['appointment_id']}"
        jwt_token = self.generate_jwt(url, "POST")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500
            
        logger.info(f"Params in update_individual_appointment function {params}")
        payload = {
            "startDateTime": new_starts_at,
            "endDateTime": new_ends_at,
            "practitionerId": params['practitioner_id'],
        }
        
        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:  
            try:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    data = await response.json()
                    print("data", data)
                    return data, response.status
            except Exception as e:
                logger.error(f"Error in update appointment Cliniko API: {e}")
                return None, 500    

    ###-------------------------CANCEL APPOINTMENT FOR PATIENT---------------------###
    async def cancel_individual_appointment(self, params: dict):
        logger.info(f"In cancel_individual_appointment function {params}")

        business_details = await self.get_business_details(params['clinic_name'])
        print(business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = business_details['GMT']
      
        try:
            starts_at = self.convert_timezone(params['starts_at'], params['timezone'])
            ### Check if patient exists or not
            patients, patient_status = await self.get_patient_data_from_coreplus(params)
            print(f"Patient status: {patient_status}")
            print(f"Patient data: {patients}")
            
            if patient_status == 200 and patients['paging']['totalRows'] == 0:
                return "Patient not found", 404
            elif patient_status == 200 and patients['paging']['totalRows'] > 1:
                logger.info(f"Multiple patients found with same phone number")
                patient_data = patients['clients']
                return patient_data, 409 
            else:
                patient_data = patients['clients'][0]
                patient_id = patient_data['clientId']
                params['patient_id']= patient_id
                params['first_name'] = patient_data['firstName']
                params['last_name'] = patient_data['lastName']
                params['date_of_birth'] = patient_data['dateOfBirth']
                print(f"Patient data for existing patient: {patient_data}")
                print("Patient found")

            bookings, bookings_status = await self.list_bookings(starts_at , params['timezone_id'] , params['patient_id'])
            print(bookings)
            for booking in bookings['appointments']:
                if booking['startDateTime'].replace(" ", "") == starts_at:
                    params['appointment_id'] = booking['appointmentId']
                    break
            else:
                return "Appointment not found", 404

            url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/Appointment/{params['appointment_id']}"
            jwt_token = self.generate_jwt(url, "POST")
            if not jwt_token:
                logger.error("Failed to generate JWT token.")
                return None, 500

            payload = {
                "deleted":  True,
            }   

            headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }
            
            logger.info(f"Payload in cancel_individual_appointment function {payload}")
            async with aiohttp.ClientSession() as session:
                try:
                    logger.info(f"Making call to {url}")
                    async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                        print(f"Cancel function response: {response}")
                        if response.status == 200:
                            print('Appointment cancelled')
                            return response, response.status
                        else:
                            print('Failed to cancel')
                            return response, response.status
                except Exception as e:
                    logger.error(f"Error in Coreplus API: {e}")
                    return None, 500

        except Exception as e:
            logger.error(f"Error in Coreplus API: {e}")
            return None, 500
        
    async def get_patient_appointment(self, params: dict):
        logger.info(f"Params in get_patient_appointment function {params}")

        business_details = await self.get_business_details(params['clinic_name'])
        print(business_details)
        params['business_id'] = business_details['id']
        params['timezone'] = business_details['timezone']
        params['timezone_id'] = business_details['timezone_id']
        params['GMT'] = business_details['GMT']
        starts_at = self.convert_timezone(params['old_start_date'], params['timezone'])

        patients, patient_status = await self.get_patient_data_from_coreplus(params)
        print("Patient Data", patients)

        if patient_status == 200 and patients['paging']['totalRows'] == 0:
                return "Patient not found", 404
        elif patient_status == 200 and patients['paging']['totalRows'] > 1:
            logger.info(f"Multiple patients found with same phone number")
            patient_data = patients['clients']
            return patient_data, 409 
        else:
            patient_data = patients['clients'][0]
            patient_id = patient_data['clientId']
            params['patient_id']= patient_id
            params['first_name'] = patient_data['firstName']
            params['last_name'] = patient_data['lastName']
            params['date_of_birth'] = patient_data['dateOfBirth']
            print(f"Patient data for existing patient: {patient_data}")
            print("Patient found")

        current_date = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        check_date = self.convert_timezone(current_date, params['timezone'])
        appointments, appointments_status = await self.list_bookings(starts_at=current_date, timezone_id=params['timezone_id'], clientId= params['patient_id'])
        appointment_found=False
        appointment_data=[]
        for booking in appointments['appointments'][0:3]:
            booking_time = datetime.strptime(booking['startDateTime'], '%Y-%m-%dT%H:%M:%S%z')
            if booking_time >= check_date:
                if booking['status'] == "Booked":
                    appointment_data.append(booking)
                appointment_found=True

        if not appointment_found:
            return "Appointment not found", 404
        return appointment_data, 200
    

    ###-------------------------LIST BOOKINGS FOR A PATIENT---------------------###
    async def list_bookings(self, starts_at='', timezone_id='' , clientId=''):
                
        # Convert the starts_at to Date Format
        starts_at = datetime.strptime(starts_at, "%Y-%m-%dT%H:%M:%S%z").date()

        # Convert the date to string format
        starts_at_date_str = starts_at.strftime("%Y-%m-%d")
        ends_at_date_str = starts_at.strftime("%Y-%m-%d")

        query = {
            "startDate" : starts_at_date_str,
            "endDate" : ends_at_date_str,
            "timezoneId": timezone_id,
            "clienId": clientId,
        }
        url = f"{self.COREPLUS_BASE_URL}/API/Core/v2.1/Appointment/"
        query_string = urlencode(query)
        full_url = f"{url}?{query_string}"
        logger.info(f"In list_bookings function")

        jwt_token = self.generate_jwt(full_url, "GET")
        if not jwt_token:
            logger.error("Failed to generate JWT token.")
            return None, 500
        
        headers = {
            "Authorization": f"JwToken {jwt_token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=query, headers=headers, timeout=10) as response:
                    data = await response.json()
                    print("data", data)
                    return data, response.status
        except aiohttp.ClientError as e:
            logger.error(f"Error in list_bookings coreplus API: {e}")
            return None, 500
    
    ###-------------------------CONVERT TIMEZONE---------------------###
    def convert_timezone(self, time, timezone):
        print('Converting timezone', time, timezone)
        current_time = datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ')

        timezone = pytz.timezone(timezone)
        time = timezone.localize(current_time)
        print('Time: ', time)
    
        return time.isoformat()

    ###-------------------------FIX END TIME FOR APPOINTMENT---------------------###
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
    
    ###-------------------------FIX GMT TIME---------------------###
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
    
    async def get_phone_number(self):
        from src import retell
        call= retell.call.retrieve(self.call_id)
        print("Call in get_phone_number: ", call)
        return call.from_number

    async def get_patient_data_from_coreplus(self, params):
        print("Params in get_patient_data_from_dynamo:", params)
        found_patient = None
    
        if params.get("first_name") != "None" and params.get("last_name") != "None" and params.get("date_of_birth") != "None":
            patients, patient_status = await self.list_patients({
                "q": [
                    f"firstName:={params['first_name']}",
                    f"lastName:={params['last_name']}", 
                    f"dateOfBirth:={params['date_of_birth']}"
                ]
            })

            if patient_status == 200 and patients['paging']['totalRows'] == 0:
                return "Patient not found", 404
            else:
                return patients, patient_status
            
        else:
            if params.get("phone_number") != "None":
                call_number = params["phone_number"]
            else:
                call_number = await self.get_phone_number()
                print("Call Info:", call_number)
                # call_number = "+923336659684"  # For testing purposes

            normalized_number = await self.normalize_phone_number(call_number)
            # params["phone_number"] = normalized_number
            print("After Normalized numbers")
            patients, patient_status = await self.list_patients(params={"mobile": params['phone_number']})
            
            return patients, patient_status
