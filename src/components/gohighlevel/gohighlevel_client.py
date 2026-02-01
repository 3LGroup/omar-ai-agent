import requests
import aiohttp
from src.logger import logger
from datetime import datetime, timedelta
from src.db.db import DB
import os
from dotenv import load_dotenv

db = DB()
load_dotenv()
IS_LOCAL = os.getenv("ENV") == "LOCAL"

class GoHighLevelClient:
    def __init__(self, call_id=None, user_id=None, access_token=None, refresh_token=None, token_expires_at=None):
        self.client_id = "68e90b4472b0aa5646baf268-mgkwbqjg"
        self.client_secret = "c827825d-0cb0-4e00-a06d-feab1c9a15cc"
        self.call_id = call_id
        self.base_url = "https://services.leadconnectorhq.com"
        self.oauth_url = "https://services.leadconnectorhq.com/oauth/token"
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.agent_id = user_id
        self.token_validator = self.ensure_valid_token()
        
        
    def get_access_token(self, authorization_code=None, refresh_token=None):
        """
        Get access token using authorization code or refresh token
        Based on: https://marketplace.gohighlevel.com/docs/ghl/oauth/get-access-token
        """
        logger.info("Getting GoHighLevel access token")
        
        if self.refresh_token:
            # Use refresh token to get new access token
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": "68e90b4472b0aa5646baf268-mgkwbqjg",
                "client_secret": "c827825d-0cb0-4e00-a06d-feab1c9a15cc"
            }
            
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        try:
            response = requests.post(self.oauth_url, data=payload, headers=headers)
            logger.info(f"OAuth response status: {response.status_code}")
            print(f"OAuth response:{response.text}")
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 86000)
                
                # Calculate expiration time
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("Successfully obtained access token")
                logger.info("Updating data in firestore")
                db.update_token_data_in_firestore(collection_name="users_auth", data={"access_token": self.access_token, "refresh_token": self.refresh_token, "token_expires_at": self.token_expires_at}, agent_id=self.agent_id)
                return data, response.status_code
            else:
                error_data = response.text
                logger.error(f"Failed to get access token: {response.status_code} - {error_data}")
                return None, response.status_code
                        
        except requests.RequestException as e:
            logger.error(f"Error getting GoHighLevel access token: {e}")
            return None, 500
    
    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            logger.error("No refresh token available")
            return None, 400
            
        return self.get_access_token(refresh_token=self.refresh_token)
    
    def is_token_valid(self):
        """Check if the current access token is still valid"""
        if not self.access_token or not self.token_expires_at:
            return False
            
        # Check if token expires in the next 5 minutes
        # Handle both naive and timezone-aware datetimes
        now = datetime.now()
        expires_at = self.token_expires_at
        
        # If expires_at is timezone-aware, make now timezone-aware too
        if expires_at.tzinfo is not None and now.tzinfo is None:
            # Make now timezone-aware (assuming UTC)
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        elif expires_at.tzinfo is None and now.tzinfo is not None:
            # Make expires_at timezone-aware
            from datetime import timezone
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        return now < (expires_at - timedelta(minutes=5))
    
    def ensure_valid_token(self):
        """Ensure we have a valid access token, refresh if needed"""
        if not self.is_token_valid():
            logger.info("Access token expired or invalid, refreshing...")
            result, status = self.refresh_access_token()
            if status != 200:
                logger.error("Failed to refresh access token")
                return False
        print("Access token is valid")
        return True
    
    def get_auth_headers(self):
        """Get headers with authorization token"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Version": "2021-07-28"
        }


    async def get_calender_events(self, location_id, params):
        logger.info ("fetching calender events for: ")

        # if not await self.ensure_valid_token():
        #     return None, 401

        #end time = start time + 1 hour
        end_time = datetime.fromisoformat(params["startTime"]) + timedelta(hours=1)
        end_time = end_time.isoformat()
        print("Start time: ", params["startTime"])
        print(f"End time: {end_time}")

        url = f"{self.base_url}/calendars/events"

        query_params = {
            "locationId" : location_id,
            "startTime" : self.convert_time_to_milliseconds(params["startTime"]),
            "endTime" : self.convert_time_to_milliseconds(end_time),
            "calendarId" : "9wmULkzhxjEfWEKhzT4s"
        }

        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_auth_headers(), params=query_params) as response:
                    logger.info(f"get events response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching contacts: {e}")
            return None, 500

    
    async def get_locations(self):
        """Get all locations for the authenticated user"""
        logger.info("Fetching GoHighLevel locations")
        
        if not await self.ensure_valid_token():
            return None, 401
            
        url = f"{self.base_url}/locations/"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_auth_headers()) as response:
                    logger.info(f"Locations response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching locations: {e}")
            return None, 500
    
    async def get_contacts(self, location_id, params=None):
        """Get contacts for a specific location"""
        logger.info(f"Fetching contacts for location {location_id}")
        
        # if not await self.ensure_valid_token():
        #     return None, 401
            
        url = f"{self.base_url}/contacts/"
        
        query_params = {
            "locationId": location_id
        }
        
        if params:
            query_params.update(params)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_auth_headers(), params=query_params) as response:
                    logger.info(f"Contacts response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching contacts: {e}")
            return None, 500
    
    async def create_contact(self, location_id, contact_data):
        """Create a new contact"""
        logger.info(f"Creating contact for location {location_id}")
        
        # if not await self.ensure_valid_token():
        #     return None, 401
            
        url = f"{self.base_url}/contacts/"
        
        payload = {
            "locationId": location_id,
            "firstName" : contact_data["firstName"],
            "lastName" : contact_data["lastName"],
            "phone" : contact_data["phone"]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.get_auth_headers()) as response:
                    logger.info(f"Create contact response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error creating contact: {e}")
            return None, 500
    
    async def update_contact(self, contact_id, contact_data):
        """Update an existing contact"""
        logger.info(f"Updating contact {contact_id}")
        
        if not await self.ensure_valid_token():
            return None, 401
            
        url = f"{self.base_url}/contacts/{contact_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=contact_data, headers=self.get_auth_headers()) as response:
                    logger.info(f"Update contact response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error updating contact: {e}")
            return None, 500
    
    async def get_appointments(self, location_id, params=None):
        """Get appointments for a specific location"""
        logger.info(f"Fetching appointments for location {location_id}")
        
        # if not await self.ensure_valid_token():
        #     return None, 401
            
        url = f"{self.base_url}/calendars/appointments"
        
        query_params = {
            "locationId": location_id
        }
        
        if params:
            query_params.update(params)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_auth_headers(), params=query_params) as response:
                    logger.info(f"Appointments response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching appointments: {e}")
            return None, 500
    
    async def create_appointment_new_customer(self, location_id, appointment_data):
        """Create a new appointment"""
        logger.info(f"Creating appointment for location {location_id}")
        
        # if not await self.ensure_valid_token():
        #     return None, 401

        contact_result, contact_status = await self.create_contact(location_id, appointment_data)
        print(f"Contact: {contact_result}")
        print(f"Contact status: {contact_status}")

        if contact_status == 201:
            contact_id = contact_result['contact']['id']
        else:
            return None, contact_status
            
        # end time = start time + 1 hour
        end_time = datetime.fromisoformat(appointment_data['startTime']) + timedelta(hours=1)
        end_time = end_time.isoformat()
        print("Start time: ", appointment_data['startTime'])
        print(f"End time: {end_time}")


        url = f"{self.base_url}/calendars/events/appointments"
        
        payload = {
            "locationId": location_id,
            "contactId": contact_id,
            "calendarId": "9wmULkzhxjEfWEKhzT4s",
            "startTime": appointment_data['startTime'],
            "endTime": end_time,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.get_auth_headers()) as response:
                    logger.info(f"Create appointment response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error creating appointment: {e}")
            return None, 500
    
    async def update_appointment(self, appointment_id, appointment_data):
        """Update an existing appointment"""
        logger.info(f"Updating appointment {appointment_id}")
        
        if not await self.ensure_valid_token():
            return None, 401
            
        url = f"{self.base_url}/calendars/appointments/{appointment_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=appointment_data, headers=self.get_auth_headers()) as response:
                    logger.info(f"Update appointment response status: {response.status}")
                    data = await response.json()
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error updating appointment: {e}")
            return None, 500
    
    async def cancel_appointment(self, location_id, cancellation_data=None):
        """Cancel an appointment"""
        logger.info(f"Cancelling appointment for location {location_id}")
        
        # if not await self.ensure_valid_token():
        #     return None, 401
            
        event_result, event_status = await self.get_calender_events(location_id, cancellation_data)
        print(f"Event: {event_result}")
        print(f"Event status: {event_status}")


        if event_status == 200:
            event_id = event_result['events'][0]['id']
        else:
            return None, event_status

        url = f"{self.base_url}/calendars/events/{event_id}"
        
        payload = {
            
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, data=payload, headers=self.get_auth_headers()) as response:
                    logger.info(f"Cancel appointment response status: {response.status}")
                    data = await response.json() if response.status != 204 else {}
                    return data, response.status
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error cancelling appointment: {e}")
            return None, 500
    
    async def get_phone_number(self):
        """Get phone number from call context (similar to cliniko_client)"""
        if IS_LOCAL:
            return self.local_number
        
        # This would need to be implemented based on your call system
        # Similar to how cliniko_client gets phone number from retell
        logger.info("Getting phone number from call context")
        return self.local_number  # Placeholder
    
    async def normalize_phone_number(self, phone_number):
        """Normalize phone number format"""
        logger.info(f"Normalizing phone number: {phone_number}")
        
        if phone_number.startswith("+1"):
            normalized_number = phone_number[2:]  # Remove +1 for US numbers
        elif phone_number.startswith("+61"):
            normalized_number = "0" + phone_number[3:]  # Australian format
        elif phone_number.startswith("+92"):
            normalized_number = "0" + phone_number[3:]  # Pakistani format
        else:
            normalized_number = phone_number
            
        return normalized_number
    
    def convert_time_to_milliseconds(self, time_input):
        """
        Convert time to milliseconds for GoHighLevel API
        Accepts datetime object, ISO string, or timestamp
        """
        import time
        
        if isinstance(time_input, str):
            # Parse ISO string to datetime
            try:
                # Handle different ISO formats
                if 'T' in time_input:
                    if time_input.endswith('Z'):
                        dt = datetime.fromisoformat(time_input.replace('Z', '+00:00'))
                    elif '+' in time_input or time_input.count('-') > 2:
                        dt = datetime.fromisoformat(time_input)
                    else:
                        dt = datetime.fromisoformat(time_input)
                else:
                    # Try parsing as date string
                    dt = datetime.strptime(time_input, '%Y-%m-%d %H:%M:%S')
            except ValueError as e:
                logger.error(f"Error parsing time string '{time_input}': {e}")
                return None
        elif isinstance(time_input, datetime):
            dt = time_input
        elif isinstance(time_input, (int, float)):
            # Already a timestamp
            return int(time_input * 1000) if time_input < 1e10 else int(time_input)
        else:
            logger.error(f"Unsupported time format: {type(time_input)}")
            return None
        
        # Convert to milliseconds
        milliseconds = int(dt.timestamp() * 1000)
        logger.info(f"Converted {time_input} to {milliseconds} milliseconds")
        return milliseconds
    
    def convert_milliseconds_to_datetime(self, milliseconds):
        """Convert milliseconds back to datetime object"""
        if isinstance(milliseconds, str):
            milliseconds = int(milliseconds)
        
        dt = datetime.fromtimestamp(milliseconds / 1000)
        logger.info(f"Converted {milliseconds} milliseconds to {dt}")
        return dt
