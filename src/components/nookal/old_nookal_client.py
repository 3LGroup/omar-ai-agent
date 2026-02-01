import os
from urllib import parse
import requests
import json
from src.logger import logger


class NookalClient:
    def __init__(self):
        self.api_key = os.environ.get("NOOKAL_API_KEY")
        self.NOOKAL_BASE_URL = "https://api.nookal.com/production/v2/"

    async def add_appointment_booking(self, params):
        # NEEDED PARAMS
        # patient_id , location_id , appointment_date , start_time , practitioner_id , appointment_type_id
        logger.info(f"Params in Booking function {params}")
        params["api_key"] = self.api_key
        params["allow_overlap_bookings"] = True
        params = parse.urlencode(params)
        url = f"{self.NOOKAL_BASE_URL}addAppointmentBooking?{params}"
        try:
            logger.info(f"Making call to {url}")
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error in Nookal API: {err}")
            return None

    async def update_appointment_booking(self, params):
        # NEEDED PARAMS
        # appointment_id, old_appointment_date, old_start_time , appointment_date , start_time , patient_id, date_from , time_from
            
        logger.info(f"Params in Update function {params}")
        params["api_key"] = self.api_key
        params["allow_overlap_bookings"] = True
        params = parse.urlencode(params)
        url = f"{self.NOOKAL_BASE_URL}updateAppointmentBooking?{params}"
        try:
            logger.info(f"Making call to {url}")
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error in Nookal API: {err}")
            return None

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

    async def cancel_appointment(self, params):
        # NEEDED PARAMS
        # patient_id , appointment_id        
        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        print(params)
       
        url = f"{self.NOOKAL_BASE_URL}cancelAppointment?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error Cancelling Appointment: {err}")
            return None
       
    async def get_appointment(self , params):
        # NEEDED PARAMS
        # date_from , patient_id , time_from
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
        response = await self.get_appointment(params=params)
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
        
    async def get_practitioners(self, params):
        logger.info(f"Getting All Practitioners")
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
        logger.info(f"Getting All Practitioners")
        params["api_key"] = self.api_key
        params = parse.urlencode(params)
        print(params)
        
        url = f"{self.NOOKAL_BASE_URL}getAppointmentTypes?{params}"
        try:
            response = requests.get(url)
            return response.json()
        except Exception as err:
            logger.error(f"Error Getting All Appointment: {err}")
            return None
        
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
            logger.error("No practitioners with given name found")
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
        
    async def get_appointment_type_details(self , params):
        response = await self.get_all_appointment_type(params=params)
        appointment_types = response.get("data", {}).get("results", {}).get("services", [])
        for appointment_type in appointment_types:
            if params["appointment_name"] == appointment_type["Name"]:
                print("Appointment Type Found----", appointment_type) 
                return appointment_type
        else:
            logger.error("No appointment types found")
            return None
        
    async def get_appointment_type_id(self , params):
        response = await self.get_all_appointment_type(params=params)
        appointment_types = response.get("data", {}).get("results", {}).get("services", [])
        for appointment_type in appointment_types:
            if params["appointment_name"] == appointment_type["Name"]:
                print("Appointment Type Found----", appointment_type) 
                return appointment_type
        else:
            logger.error("No appointment types found")
            return None