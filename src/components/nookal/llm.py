import json
from typing import List
from openai import OpenAI
import os
from src.components import nookal
from src.logger import logger
from src.utils.custom_types import (
    Utterance,
    CustomLlmRequest,
    CustomLlmResponse,
    FunctionCall,
)
from src.components.nookal import nookal_function_calls_schema
from src.components.nookal.nookal_client import NookalClient
from datetime import datetime
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import smtplib
from src import db, retell
from typing import List
from openai import AsyncOpenAI
import os
from src.logger import logger
from src.utils.custom_types import (
    Utterance,
    CustomLlmResponse,
    FunctionCall,
)
from src.components.nookal.nookal_client import NookalClient
from src.components.nookal import nookal_function_calls_schema
from datetime import datetime, timezone
from src.components.prompts.main_prompts import PROMPTS
from src.utils.session_vars import user_data
import pytz
from datetime import timedelta
from src.db.db import DB
db = DB()
from src import twilio_client


class InboundLLMClient:
    def __init__(self, call_id, agent_type="BOOKING"):
        self.client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.metadata = {}
        self.agent_type = agent_type
        self.user_id = self.get_user_id(call_id)
        self.call_id = call_id
        self.clinic_data = db.get_clinic_data_sync(self.user_id)
        print(f"self.user_id: {self.user_id}")
        self.prompts= PROMPTS[self.clinic_data['inboundPrompt']] + PROMPTS[self.clinic_data['inboundPromptBooking']]
        self.clinicName= self.clinic_data['clinicName']
        self.agentName= self.clinic_data['agentName']
        self.nookal_api = os.environ.get(self.clinic_data['nookal_api'])
        self.nookal_url = self.clinic_data['nookal_url']
        self.nookal = NookalClient(url=self.nookal_url, api_key=self.nookal_api ,call_id=call_id, clinicData=self.clinic_data, timezone=self.clinic_data['timezone_identifier'])
        self.BEGIN_SENTENCE_DYNAMIC= self.clinic_data['beginSentence']
        self.END_SENTENCE_DYNAMIC= self.clinic_data['endSentence']
        self.GMT = self.clinic_data['GMT']
        self.timezone= self.clinic_data['timezone_identifier']
        self.function_calls = {}
    
    async def create_appointment_new_patient_nookal(self, params: dict, func_call, request):
        logger.info(f"Params in create_appointment_new_patient_nookal function {params}")
        logger.info(f"Booking an appointment with nookal")
        
        function_called = await self.check_function_already_called('create_appointment_new_patient_nookal' , params)
        print(f'function called: {function_called}')
        print(f'function finished?: {self.function_calls["create_appointment_new_patient_nookal"]["finished"]}')
        print('Request id 1 ->', request.response_id)
        
        if function_called and self.function_calls['create_appointment_new_patient_nookal']['finished']:
            logger.info("Function already called")

            func_call.result = "The function is already called"
            print("Function that was already called", self.function_calls['create_appointment_new_patient_nookal'])

            print('Request id 2 ->', request.response_id)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['create_appointment_new_patient_nookal']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )

            user_data['success'] = True
            return response, func_call

        print("Function called", self.function_calls['create_appointment_new_patient_nookal'])
        self.function_calls['create_appointment_new_patient_nookal']['params'] = params
        
        #Checking if starts_at is in the future
        if datetime.fromisoformat(self.nookal.fix_gmt_time((params['starts_at']), self.GMT)) <= datetime.now(timezone.utc):
            responset_text = f"""Sorry but the date you have chosen is in the past. Can you please give me a date from today?"""

            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content=responset_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True,
            )
            user_data['success'] = True
            self.function_calls['create_appointment_new_patient_nookal']['response'] = responset_text
            self.function_calls['create_appointment_new_patient_nookal']['finished'] = True
            return response, func_call
        
        else:
            response, status = await self.nookal.create_appointment_new_patient(params)
            if status == 201:
                logger.info(f"Appointment booked successfully")
                doctor_name = params['doctor_name']
                starts_at = self.convert_readable_datetime(params['starts_at'])
                responset_text = f"""Your appointment on {starts_at} with {doctor_name} has been booked at our {params['clinic_name']}. Was there anything else I could help you with?"""

                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content=responset_text,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True,
                )
                user_data['success'] = True
                self.function_calls['create_appointment_new_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_new_patient_nookal']['finished'] = True
                return response, func_call

            # Handle booking conflict
            elif status == 409 and response == "Booking Conflict":
                logger.error(f"Appointment conflict")
                response, status, slot_type = await self.nookal.get_free_available_slot(params, date=params['starts_at'])
                print("response of Function get doctor slots: ", response ,status)
                if len(response) > 0:
                    responset_text = f"""Unfortunately that appointment slot has already been taken. However, the closest slot to your time is on {', '.join(response)} on the same day"""
                    func_call.result = responset_text
                else:
                    responset_text = "Unfortunately the apointment slot has already been taken, and our clinic is extremely busy and we do not have any available slots for the day, would you like to choose another date for your appointment?"
                    func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                self.function_calls['create_appointment_new_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_new_patient_nookal']['finished'] = False
                user_data['success'] = False
                return response, func_call
            
            elif status == 400 and response == "Doctor not available":
                logger.error(f"Doctor not available at this time")
                responset_text = f"Sorry but {params['doctor_name']} isn't available at that time. You could see another doctor at that time or perhaps you can choose another time?"
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                self.function_calls['create_appointment_new_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_new_patient_nookal']['finished'] = False 
                user_data['success'] = False
                return response, func_call

            elif status == 409 and response == "Patient already exists":
                logger.error(f"Error booking appointment. Patient already exists")
                responset_text = f"Thanks {params['first_name']} {params['last_name']}.It looks like you already have a file with us. I will use that profile and proceed with the booking. Is that alright?"
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= responset_text,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                self.function_calls['create_appointment_new_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_new_patient_nookal']['finished'] = False
                user_data['success'] = False
                return response, func_call
            elif status == 401 and response == None:
                logger.error(f"Appointment type is not accessible")
                responset_text = "The appointment you chose for booking is not available through AI booking. Please contact the clinic for the booking of this appointment."
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=True,
                    no_interruption_allowed=True
                )
                self.function_calls['update_appointment_nookal']['response'] = responset_text
                self.function_calls['update_appointment_nookal']['finished'] = False
                user_data['success'] = False
                return response, func_call

            else:
                logger.error(f"Error booking appointment. {response}")
                responset_text = "Sorry but there seems to be an error with booking the appointment. I will have to pass on your information onto our team and a team member will get in contact with you."
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= responset_text,
                    content_complete=True,
                    end_call=True,
                    no_interruption_allowed=True
                )
                self.function_calls['create_appointment_new_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_new_patient_nookal']['finished'] = True
                user_data['success'] = False
                return response, func_call
            
    async def create_appointment_existing_patient_nookal(self, params: dict, func_call, request):
        logger.info(f"Booking an appointment with nookal")
        logger.info(f"Params in create_appointment_existing_patient_nookal function {params}")
        
        function_called = await self.check_function_already_called('create_appointment_existing_patient_nookal' , params)
        print(f'function called: {function_called}')
        print(f'function finished?: {self.function_calls["create_appointment_existing_patient_nookal"]["finished"]}')
        print('Request id 1 ->', request.response_id)
        
        if function_called and self.function_calls['create_appointment_existing_patient_nookal']['finished']:
            logger.info("Function already called")

            func_call.result = self.function_calls['create_appointment_existing_patient_nookal']['response']
            print("Function that was already called", self.function_calls['create_appointment_existing_patient_nookal'])

            print('Request id 2 ->', request.response_id)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['create_appointment_existing_patient_nookal']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )

            user_data['success'] = True
            return response, func_call

        print("Function called", self.function_calls['create_appointment_existing_patient_nookal'])
        self.function_calls['create_appointment_existing_patient_nookal']['params'] = params

        #Checking if starts_at is in the future
        if datetime.fromisoformat(self.nookal.fix_gmt_time((params['starts_at']) , self.GMT)) <= datetime.now(timezone.utc):
            responset_text = f"""Sorry but the date you have chosen is in the past. Can you please give me a date from today?"""

            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content=responset_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True,
            )
            user_data['success'] = True
            self.function_calls['create_appointment_existing_patient_nookal']['response'] = responset_text
            self.function_calls['create_appointment_existing_patient_nookal']['finished'] = True
            return response, func_call
        
        else:
            response, status = await self.nookal.create_appointment_existing_patient(params)

            if status == 201:
                logger.info(f"Appointment booked successfully")
                doctor_name = params['doctor_name']
                starts_at= params['starts_at']
                print("starts_at_before_converting: ", starts_at)

                starts_at = self.convert_readable_datetime(params['starts_at'])
                print("starts_at_after_converting: ", starts_at)
                responset_text = f"""Your appointment on {starts_at} with {doctor_name} has been booked at our {params['clinic_name']}. Was there anything else I could help you with?"""

                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )

                self.function_calls['create_appointment_existing_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_existing_patient_nookal']['finished'] = True
                user_data['success'] = True
                return response, func_call
            
            elif status == 404 and response == "Patient not found":
                logger.error(f"Error booking appointment. Patient not found")

                responset_text = f"""Sorry but I can’t seem to find your data on our database. I’ll go ahead and quickly create a new profile for you now. Is that alright? """
                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )

                self.function_calls['create_appointment_existing_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_existing_patient_nookal']['finished'] = False

                user_data['success'] = False
                return response, func_call
            
            elif status == 400 and response == "Doctor not available":
                logger.error(f"Doctor not available at this time")

                responset_text = f"""Sorry but {params['doctor_name']} isn't available at that time. You could see another doctor at that time or perhaps you can choose another time?"""
                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= responset_text,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                
                self.function_calls['create_appointment_existing_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_existing_patient_nookal']['finished'] = False

                user_data['success'] = False
                return response, func_call

            # Handle booking conflict
            elif status == 409 and response == "Booking Conflict":
                logger.error(f"Appointment conflict")
                response, status, slot_type = await self.nookal.get_free_available_slot(params, date= params['starts_at'])
                if len(response) > 0:
                    responset_text = f"""Unfortunately that appointment slot has already been taken. However, the closest slot to your time is on {', '.join(response)} on the same day"""
                    func_call.result = responset_text
                else:
                    responset_text = "Unfortunately the apointment slot has already been taken, and our clinic is extremely busy and we do not have any available slots for the day, would you like to choose another date for your appointment?"
                    func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                
                self.function_calls['create_appointment_existing_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_existing_patient_nookal']['finished'] = False

                user_data['success'] = False
                return response, func_call
            elif status == 401 and response == None:
                logger.error(f"Appointment type is not accessible")
                responset_text = "The appointment you chose for booking is not available through AI booking. Please contact the clinic for the booking of this appointment."
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=True,
                    no_interruption_allowed=True
                )
                self.function_calls['update_appointment_nookal']['response'] = responset_text
                self.function_calls['update_appointment_nookal']['finished'] = False
                user_data['success'] = False
                return response, func_call
            
            else:
                logger.error(f"Error booking appointment. {response}")

                responset_text = "Sorry but there seems to be an error with booking the appointment. I will have to pass on your information onto our team and a team member will get in contact with you."
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=True,
                    no_interruption_allowed=True
                )

                self.function_calls['create_appointment_existing_patient_nookal']['response'] = responset_text
                self.function_calls['create_appointment_existing_patient_nookal']['finished'] = True
                
                user_data['success'] = False
                
                return response, func_call

    async def update_appointment_nookal(self, params: dict, func_call, request):
        logger.info("Updating Appointment")
        function_called = await self.check_function_already_called('update_appointment_nookal' , params)
        print(f'function called: {function_called}')
        print(f'function finished?: {self.function_calls["update_appointment_nookal"]["finished"]}')
        print('Request id 1 ->', request.response_id)
        
        if function_called and self.function_calls['update_appointment_nookal']['finished']:
            logger.info("Function already called")

            func_call.result = self.function_calls['update_appointment_nookal']['response']
            print("Function that was already called", self.function_calls['update_appointment_nookal'])

            print('Request id 2 ->', request.response_id)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['update_appointment_nookal']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )

            user_data['success'] = True
            return response, func_call

        print("Function called", self.function_calls['update_appointment_nookal'])
        self.function_calls['update_appointment_nookal']['params'] = params
        
        #Checking if starts_at is in the future
        response, status = await self.nookal.update_individual_appointment(params)
        logger.info(f"Response from nookal {response}")

        if status == 200:
            logger.info("Success")
            new_starts_date = self.convert_readable_datetime(params["new_starts_date"])

            responset_text = f"""I have gone ahead and updated your appointment on {new_starts_date}. Was there anything else you would like help with today?"""
            
            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = True
            user_data['success'] = True
            return response, func_call
        
        elif status == 404 and response == "Patient not found":
            logger.error(f"Error booking appointment. Patient not found")
            responset_text = f"Sorry but I can’t seem to find your data on our database. Your name is {params['first_name']} {params['last_name']} and your date of birth is {params['date_of_birth']}. Could you double check you have the right name and date of birth?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call

        elif status == 400 and response == "Doctor not available":
            logger.error(f"Doctor not available at this time")
            responset_text = f"Sorry but the practitioner isn't available at that time. You could see another doctor at that time or perhaps you can choose another time?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call

        elif status == 404 and response == "Appointment not found":
            logger.error(f"Error booking appointment. Appointment not found")
            old_date = self.convert_readable_datetime(params['old_start_date'])
            responset_text = f"Sorry but I cant seems to find your appointment on our system. Can you please repeat it to me? Your appointment is on {old_date}?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call

        elif status == 409 and response == "Booking Conflict":
            logger.error(f"Appointment conflict")
            response, status, slot_type = await self.nookal.get_free_available_slot(params, date=params['new_starts_date'])
            if len(response) > 0:
                responset_text = f"""Unfortunately that appointment slot has already been taken. However, the closest slot to your time is on {', '.join(response)} on the same day"""
                func_call.result = responset_text
            else:
                responset_text = "Unfortunately the apointment slot has already been taken, and our clinic is extremely busy and we do not have any available slots for the day, would you like to choose another date for your appointment?"
                func_call.result = responset_text
                
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call
        
        elif status == 401 and response == None:
            logger.error(f"Appointment type is not accessible")
            responset_text = "The appointment you chose for booking is not available through AI booking. Please contact the clinic for the booking of this appointment."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call
        else:
            logger.error("Error")
            responset_text = "Sorry but there seems to be an error. I will have to pass on your information onto our team and a team member will get in contact with you"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            self.function_calls['update_appointment_nookal']['response'] = responset_text
            self.function_calls['update_appointment_nookal']['finished'] = True
            user_data['success'] = False
            return response, func_call
        
    async def cancel_appointment_nookal(self, params: dict, func_call, request,):
        logger.info("Cancelling Appointment")
        logger.info(f"In cancel_individual_appointment function {params}")

        function_called = await self.check_function_already_called('cancel_appointment_nookal' , params)
        print(f'function called: {function_called}')
        print(f'function finished?: {self.function_calls["cancel_appointment_nookal"]["finished"]}')
        print('Request id 1 ->', request.response_id)
        
        if function_called and self.function_calls['cancel_appointment_nookal']['finished']:
            logger.info("Function already called")

            func_call.result = self.function_calls['cancel_appointment_nookal']['response']
            print("Function that was already called", self.function_calls['cancel_appointment_nookal'])

            print('Request id 2 ->', request.response_id)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['cancel_appointment_nookal']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )

            user_data['success'] = True
            return response, func_call

        print("Function called", self.function_calls['cancel_appointment_nookal'])
        self.function_calls['cancel_appointment_nookal']['params'] = params
        
        response, status = await self.nookal.cancel_individual_appointment(params)
        logger.info(f"Response from nookal {response}")

        if status == 204: # 204 means updated -> cancelled
            logger.info("Success")
            cancellation_reason = params['cancellation_flag']

            if cancellation_reason == "No":
                responset_text = f"""Thank you {params['first_name']} {params['last_name']}. I have gone ahead and cancelled your appointment. Was there anything else I could help you with? """
            else: 
                responset_text = f"""Thank you {params['first_name']} {params['last_name']}. I have gone ahead and cancelled your appointment. Can you kindly state the reason for cancellation? So, I can send it to the clinic through email. """


            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content=responset_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            user_data['success'] = True
            self.function_calls['cancel_appointment_nookal']['response'] = responset_text
            self.function_calls['cancel_appointment_nookal']['finished'] = True
            return response, func_call
        
        elif status == 404 and response == "Appointment not found":
            logger.error(f"Error canceling appointment. Appointment not found")
            
            appointment_date = self.convert_readable_datetime(params['starts_at'])
            responset_text = f"Sorry but I cant seems to find your appointment on our system. Can you please repeat it to me? Your appointment is on {appointment_date}?"
            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )

            self.function_calls['cancel_appointment_nookal']['response'] = responset_text
            self.function_calls['cancel_appointment_nookal']['finished'] = False

            user_data['success'] = False

            return response, func_call
        
        elif status == 404 and response == "Patient not found":
            logger.error(f"Error canceling appointment. Patient not found")

            response_text = f"Sorry but I can’t seem to find your data on our database. Your name is {params['first_name']} {params['last_name']} and your date of birth is {params['date_of_birth']}. Could you double check you have the right name and date of birth?"
            func_call.result = response_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )

            self.function_calls['cancel_appointment_nookal']['response'] = response_text
            self.function_calls['cancel_appointment_nookal']['finished'] = False

            user_data['success'] = False
            return response, func_call

        else:
            logger.error("Error")

            responset_text = "Sorry but there seems to be an error when cancelling your appointment. I will have to pass on your information onto our team and a team member will get in contact with you"

            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )

            self.function_calls['cancel_appointment_nookal']['response'] = responset_text
            self.function_calls['cancel_appointment_nookal']['finished'] = True

            user_data['success'] = False
            return response, func_call

    async def transfer_call_nookal(self, params: dict, func_call, request):
        
        timezone_identifier = self.clinic_data["timezone_identifier"]
        current_datetime = datetime.now(pytz.timezone(timezone_identifier))
        
        # Get the current day of the week
        day_of_week = current_datetime.strftime("%A").lower()

        # Extract the working hours for the current day from clinic data
        working_hours = self.clinic_data["workingHours"].get(day_of_week)
        print("Working hours______: ", working_hours)

        if working_hours:
            current_time = current_datetime.strftime("%H:%M:%S")
            print("Current time: ", current_time)
            print("INSIDE IF WORKING HOURS")
            
            # Check if current time is within the opening and closing hours
            if working_hours['opening'] <= current_time <= working_hours['closing']: 
                logger.info("Transferring Call")
                call= retell.call.retrieve(self.call_id)
                print("Call in side call transfer: ", call)
                callSid= call.metadata['twilio_call_sid']
                await asyncio.sleep(10)
                response= twilio_client.transfer_call(params['to_number'], callSid)

                logger.info("Success")
                responset_text = "Call transferred successfully"
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=False,
                    end_call=False,
                    no_interruption_allowed=True
                )
                return response, func_call
            else:
                logger.info("Call cannot be transferred at this time")
                logger.info("Success")
                responset_text = "The clinic is closed at the moment, would you like me to send an email to the clinic instead?"
                func_call.result = responset_text
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                return response, func_call
        
    
    async def get_patient_appointment_nookal(self, params: dict, func_call, request):
        logger.info("getting patient appointment")
        function_called = await self.check_function_already_called('get_patient_appointment_nookal' , params)
        print(f'function called: {function_called}')
        print(f'function finished?: {self.function_calls["get_patient_appointment_nookal"]["finished"]}')
        print('Request id 1 ->', request.response_id)
        
        if function_called and self.function_calls['get_patient_appointment_nookal']['finished']:
            logger.info("Function already called")

            func_call.result = self.function_calls['get_patient_appointment_nookal']['response']
            print("Function that was already called", self.function_calls['get_patient_appointment_nookal'])

            print('Request id 2 ->', request.response_id)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['get_patient_appointment_nookal']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )

            user_data['success'] = True
            return response, func_call

        print("Function called", self.function_calls['get_patient_appointment_nookal'])
        self.function_calls['get_patient_appointment_nookal']['params'] = params
        
        #Checking if starts_at is in the future
        response, practitioner, location, status = await self.nookal.get_patient_pending_appointments(params)
        logger.info(f"Response from nookal {response}")

        if status == 200:
            logger.info("Success")
            print("Get PATIENT APPOINTMENT NOOKAL RESPONE", response)
            appointments = []
            for res, doctor_name, location_name in zip(response, practitioner, location):
                appointments.append({
                    "datetime": res,
                    "doctor": doctor_name,
                    "location": location_name
                })
            flag = params['flag']
            print("(________FLAG________)",flag)

            # Check if the user wants to update their appointment
            if flag == "update":
                if len(appointments) > 1:
                    appointment_list = "\n".join([
                        f"{i+1}. Appointment on {appt['datetime']} with {appt['doctor']} at {appt['location']}" 
                        for i, appt in enumerate(appointments)
                    ])
                    responset_text = f"""You have the following appointments:\n{appointment_list}\nKindly choose the appointment you want to update?"""
                else:
                    appt = appointments[0]
                    responset_text = f"""You have an appointment on {appt['datetime']} with {appt['doctor']} at {appt['location']} . Do you want to update it?"""
                
                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                self.function_calls['get_patient_appointment_nookal']['response'] = responset_text
                self.function_calls['get_patient_appointment_nookal']['finished'] = True
                user_data['success'] = True
                return response, func_call
            
            # Check if the user wants to Cancel their appointment
            elif flag == "cancel":
                if len(appointments) > 1:
                    appointment_list = "\n".join([
                        f"{i+1}. Appointment on {appt['datetime']} with {appt['doctor']}" 
                        for i, appt in enumerate(appointments)
                    ])
                    responset_text = f"""You have the following appointments:\n{appointment_list}\nKindly choose the appointment you want to cancel?"""
                else:
                    appt = appointments[0]
                    responset_text = f"""You have an appointment on {appt['datetime']} with {appt['doctor']}. Do you want to cancel it?"""
                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                self.function_calls['get_patient_appointment_nookal']['response'] = responset_text
                self.function_calls['get_patient_appointment_nookal']['finished'] = True
                user_data['success'] = True
                return response, func_call
            
            # If the user wants to check their appointment
            elif flag == "check":
                if len(appointments) > 1:
                    appointment_list = "\n".join([
                        f"{i+1}. Appointment on {appt['datetime']} with {appt['doctor']}" 
                        for i, appt in enumerate(appointments)
                    ])
                    responset_text = f"""You have the following appointments:\n{appointment_list}"""
                else:
                    appt = appointments[0]
                    responset_text = f"""You have an appointment on {appt['datetime']} with {appt['doctor']}."""
                func_call.result = responset_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= func_call.result,
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=True
                )
                self.function_calls['get_patient_appointment_nookal']['response'] = responset_text
                self.function_calls['get_patient_appointment_nookal']['finished'] = True
                user_data['success'] = True
                return response, func_call
        
        elif status == 404 and response == "Patient not found":
            logger.error(f"Error booking appointment. Patient not found")
            responset_text = f"Sorry but I can’t seem to find your data on our database. Your name is {params['first_name']} {params['last_name']} and your date of birth is {params['date_of_birth']}. Could you double check you have the right name and date of birth?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['get_patient_appointment_nookal']['response'] = responset_text
            self.function_calls['get_patient_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call

        elif status == 404 and response == "Appointment not found":
            logger.error(f"Error booking appointment. Appointment not found")
            responset_text = f"Sorry but, currently you don't have any appointment scheduled with us, Would you like me to help you with something else?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['get_patient_appointment_nookal']['response'] = responset_text
            self.function_calls['get_patient_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call
        
        else:
            logger.error(f"Unknown error")
            responset_text = f"Sorry but it seems an unknown error has occurred within our system. Kindly try contacting directly to our clinic."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            self.function_calls['get_patient_appointment_nookal']['response'] = responset_text
            self.function_calls['get_patient_appointment_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call
        
    async def get_patient_data_from_dynamo_nookal(self, params: dict, func_call, request):
        logger.info("getting patient")
        function_called = await self.check_function_already_called('get_patient_data_from_dynamo_nookal' , params)
        print(f'function called: {function_called}')
        print(f'function finished?: {self.function_calls["get_patient_data_from_dynamo_nookal"]["finished"]}')
        print('Request id 1 ->', request.response_id)
        
        if function_called and self.function_calls['get_patient_data_from_dynamo_nookal']['finished']:
            logger.info("Function already called")

            func_call.result = self.function_calls['get_patient_data_from_dynamo_nookal']['response']
            print("Function that was already called", self.function_calls['get_patient_data_from_dynamo_nookal'])

            print('Request id 2 ->', request.response_id)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['get_patient_data_from_dynamo_nookal']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )

            user_data['success'] = True
            return response, func_call

        print("Function called", self.function_calls['get_patient_data_from_dynamo_nookal'])
        self.function_calls['get_patient_data_from_dynamo_nookal']['params'] = params
        
        #Checking if starts_at is in the future
        print("Params in get patient data: ", params)
        response, status = await self.nookal.get_patient_data_from_dynamo(params)
        logger.info(f"Response from nookal {response}")
        print("len of Response from nookal: ", len(response))

        if status == 200:
            logger.info("Success")
            # Handle different response types: a dictionary (single profile) or a list (multiple profiles)
            if isinstance(response, list):
                if len(response) > 1:
                    profiles_info = "\n".join(
                    [
                        f"{idx + 1}. {p['first_name']} {p['last_name']} (Date of Birth: {p['date_of_birth']})"
                        for idx, p in enumerate(response)
                    ]
                )
                    responset_text = (
                        f"Linked to this number, we have {len(response)} profiles: {profiles_info}. "
                        "Kindly choose the profile you wish to continue with."
                    )
                elif len(response) == 1:
                    patient = response[0]
                    first_name = patient["first_name"]
                    last_name = patient["last_name"]
                    date_of_birth = patient["date_of_birth"]
                    responset_text = f"You have a profile named {first_name} {last_name} and your date of birth is {date_of_birth}. Is this the profile you wish to continue with?."
            
            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['get_patient_data_from_dynamo_nookal']['response'] = responset_text
            self.function_calls['get_patient_data_from_dynamo_nookal']['finished'] = True
            user_data['success'] = True
            return response, func_call

        elif status == 404 and response == "Patient not found":
            logger.error("Patient not found")
            if params.get("phone_number") == 'None':
                responset_text = "Sorry but I can’t seem to find your data on our database. Could you please provide your phone number on which you have registered your profile with us?."
            elif params.get("first_name") == 'None' and params.get("last_name") == 'None' and params.get("date_of_birth") == 'None': 
                responset_text = "Sorry but I can’t seem to find your data on our database. Could you please provide your first name, last name and Date of Birth?."
            else:
                responset_text = "Sorry but I can’t seem to find your data on our database. Kindly try contacting directly to our clinic."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            self.function_calls['get_patient_data_from_dynamo_nookal']['response'] = responset_text
            self.function_calls['get_patient_data_from_dynamo_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call
          
        else:
            logger.error("Unknown error")
            responset_text = "Sorry but it seems an unknown error has occurred within our system. Kindly try contacting directly to our clinic."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            self.function_calls['get_patient_data_from_dynamo_nookal']['response'] = responset_text
            self.function_calls['get_patient_data_from_dynamo_nookal']['finished'] = False
            user_data['success'] = False
            return response, func_call


    
    async def get_next_available_slot_nookal(self, params: dict, func_call, request):
        logger.info("Getting Next Available Slot")
        print("Params in get next available slot: ", params)
        response, status = await self.nookal.get_next_available_slot(params, date=params["starts_at"])
        logger.info(f"Response from nookal {response}")

        if status == 200:
            logger.info("Success")
            print("response of Function get next available slots: ", response ,status)
            if len(response) > 0:
                responset_text = f"""We have availability on {', '.join(response)} with {params['doctor_name']} at our {params['clinic_name']}. Does this time works for you?"""
                func_call.result = responset_text

            else:
                responset_text = "Unfortunately there aren’t any available appointments for the next seven days. Would you like to choose a date for your appointment next week?"
                func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            user_data['success'] = False
            return response, func_call
        
        else:
            logger.error("Error While Getting Next Available Slot")
            responset_text = "Sorry but there seems to be an error when getting new available appointment slot. I will have to pass on your information onto our team and a team member will get in contact with you."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            user_data['success'] = False
            return response, func_call
        
    async def get_specific_day_slots_nookal(self, params: dict, func_call, request):
        logger.info("Getting Specific Day Slots" , params)
        response, status, slot_type = await self.nookal.get_free_available_slot(params , params['starts_at'])
        logger.info(f"Response from nookal {response}")

        if status == 200:
            logger.info("Success")
            print("response of Function get specific day slots: ", response ,status)
            if len(response) > 0:
                # Check if the response is a list of slots
                if slot_type == "after":
                    responset_text = f"""We have availability on {response}, with {params['doctor_name']} at our {params['clinic_name']}. Does this time work for you?"""
                    func_call.result = responset_text
                elif slot_type == "before":
                    responset_text = f"""We have availability on {response}, with {params['doctor_name']} at our {params['clinic_name']}. Does this time work for you?"""
                    func_call.result = responset_text
                elif slot_type == "exact":
                    responset_text = f"""Yes, We have availability on {response}, with {params['doctor_name']} at our {params['clinic_name']}. Shall I schedule an appointment for you?"""
                    func_call.result = responset_text
                elif slot_type == "slot already booked":
                    responset_text = f"""Sorry but it seems like the slot you requested is already booked, however, the closest available slot is {response} with {params['doctor_name']} at our {params['clinic_name']}. Does this time work for you?"""
                    func_call.result = responset_text
                elif slot_type == "closest": 
                    responset_text = f"""We have availability on {response}, with {params['doctor_name']} at our {params['clinic_name']}. Does this time work for you?"""
                    func_call.result = responset_text
                elif slot_type == "no preferred time":
                    responset_text = f"""We have availability on {response}, with {params['doctor_name']} at our {params['clinic_name']}. Does this time work for you?"""
                    func_call.result = responset_text
            else:
                starts_at = self.convert_readable_datetime(response['starts_at'], params["timezone"])
                responset_text = f"""Unfortunately there aren’t any available appointments for {starts_at}. Would you like to choose a different date for your appointment?"""
                func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content=func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            user_data['success'] = False
            return response, func_call
        
        elif status == 400:
            logger.error("No free slots available for specific day")
            responset_text = f"It seems like there are no free slots available for the requested date with {params['doctor_name']}, at {params['clinic_name']}. Would you like to choose a different date for your appointment or perhaps a different practitioner?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            user_data['success'] = False
            return response, func_call
        elif status == 404:
            logger.error("No free slots available for specific day")
            responset_text = f"It seems like there are no free slots available for the requested time {params['doctor_name']}, at {params['clinic_name']}. Would you like to choose a different time for your appointment or perhaps a different practitioner?"
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            user_data['success'] = False
            return response, func_call
        else:
            logger.error("Error While Getting Specific Day Available Slot")
            responset_text = "Sorry but there seems to be an error when getting an available appointment slot. Kindly try contacting directly to our clinic."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            user_data['success'] = False
            return response, func_call
            
    
    async def send_email(self, params: dict, func_call, request):
        """Send an email based on provided parameters."""
        logger.info("Preparing to send email.")
        
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "Valorantwalisarkar5@gmail.com"
        sender_password = os.environ.get("EMAIL_PASSWORD")  # Use environment variables in production!

        recipient = params["recipient"]
        subject = params["subject"]
        body = params["message"]
        cc = params.get("cc", [])
        bcc = params.get("bcc", [])

        # Create the email
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = ", ".join(cc)
        
        # Add the body
        msg.attach(MIMEText(body, "html"))

        recipients = [recipient] + cc + bcc

        try:
            # Connect to the SMTP server and send the email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipients, msg.as_string())

            logger.info("Email sent successfully.")
            responset_text = "Your message has been sent successfully. Thank you for calling us. We will get back to you soon."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True,
            )
            return response, func_call
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            responset_text = "Sorry but there seems to be an error when sending your email. I will have to pass on your information onto our team and a team member will get in contact with you."
            func_call.result = responset_text
            response = CustomLlmResponse(
                response_id=request.response_id,
                content= func_call.result,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True,
            )
            return response, func_call
                    
    
    def draft_begin_message(self):
        response = CustomLlmResponse(
            response_id=0,
            content=self.BEGIN_SENTENCE_DYNAMIC,
            content_complete=True,
            end_call=False,
            no_interruption_allowed=True
        )
        return response

    def prepare_prompt(self, request: CustomLlmResponse, func_result: FunctionCall):
        print("9. func_call", func_result)
        
        # Get the timezone identifier from the clinic data
        timezone_identifier = self.clinic_data["timezone_identifier"]
        current_datetime = datetime.now(pytz.timezone(timezone_identifier))

        day_of_week_name = current_datetime.strftime("%A")
        TODAY_DATE = current_datetime.strftime('%A, %B %d, %Y')
        TODAY_TIME= current_datetime.strftime("%H:%M:%S")
        
        prompt = [
            {
                "role": "system",
                "content": self.prompts,
            },
            {
                "role": "system",
                "content": f"Today's date is {TODAY_DATE}, and the time is {TODAY_TIME}. Ensure all responses use this date.",
            },
        
        ]

        transcript_messages = self.convert_transcript_to_openai_messages(
                request.transcript
            )
        for message in transcript_messages:
            prompt.append(message)
            # print("Test in prompt:", message, prompt)

        
        # print('OUTSIDE Func result', func_result)
        if func_result:
            # print("INSIDE FUNC_RESULT-----")
            prompt.append(
                {
                    "role": "assistant",
                    "content": None,
                    "toolCalls": [
                        {
                            "id": func_result.id,
                            "type": "function",
                            "function": {
                                "name": func_result.func_name,
                                "arguments": str(func_result.arguments),
                            },
                        }
                    ],
                }
            )

            # print("Appending the func_result.result", func_result.result)
            # print("Name of the func_result.name", func_result.func_name)
            
            # add function call result to prompt
            prompt.append(
                    {
                        "role": "tool",
                        "toolCallId": func_result.id,
                        "content": func_result.result,
                    }
                )

        if request.interaction_type == "reminder_required":
            prompt.append(
                {
                    "role": "user",
                    "content": "(Now the user has not responded in a while, you would say: Are you there? Should I repeat my question?)",
                }
            )
        # print("PROMPT-:" , prompt)
        return prompt



    def convert_transcript_to_openai_messages(self, transcript: List[Utterance]):
        messages = []
        for utterance in transcript:
            role = "assistant" if utterance["role"] == "agent" else "user"
            messages.append({"role": role, "content": utterance["content"]})
            # print("Messages in convert transcript:",messages)
            
        return messages
    
    def initialize_functions(self):
        functions = [
            nookal_function_calls_schema.end_call_function_schema,
            nookal_function_calls_schema.create_appointment_new_patient_schema,
            nookal_function_calls_schema.create_appointment_existing_patient_schema,
            nookal_function_calls_schema.update_individual_appointment_schema,
            nookal_function_calls_schema.cancel_individual_appointment_schema,
            nookal_function_calls_schema.transfer_call_function_schema,
            nookal_function_calls_schema.send_email_function_schema,
            nookal_function_calls_schema.get_next_available_slot_schema,
            nookal_function_calls_schema.get_patient_appointment_schema,
            nookal_function_calls_schema.get_specific_available_slot_schema,
            nookal_function_calls_schema.get_patient_data_from_dynamo_schema
        ]
        return functions

    async def draft_response(self, request, func_result = None):
        try:
            # print("Draft_response start func_result:", func_result)
            models = ["gpt-4-turbo", "gpt-3.5-turbo-0125", "gpt-4o", "gpt-4.1"]
            prompt = self.prepare_prompt(request, func_result)
            print('After prepare prompt')
            func_call: FunctionCall = {}
            func_arguments = ""
            
            # print('1. func_call', func_call)
            
            stream = await self.client.chat.completions.create(
                model=models[3],
                messages=prompt,
                temperature=0,
                stream=True,
                tools=self.initialize_functions(),
                tool_choice="auto",
            )


            async for chunk in stream:
                if len(chunk.choices) == 0:
                    continue

                if chunk.choices[0].delta.tool_calls:
                    tool_calls = chunk.choices[0].delta.tool_calls[0]
                    print("print tool calls" ,tool_calls)
                    if tool_calls.id:
                        # print('2. func_call', func_call)
                        if func_call:
                            print("func_call break")
                            break
                        print('func_call not break')
                        func_call = FunctionCall(
                            id=tool_calls.id,
                            func_name=tool_calls.function.name or "",
                            arguments={},
                        )
                        # print('3. func_call', func_call)
                    else:
                        # print('4. func_call', func_call)
                        func_arguments += tool_calls.function.arguments or ""

                if chunk.choices[0].delta.content:
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=chunk.choices[0].delta.content,
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=False,
                    )
                    yield response
                    

            if func_call:
                # print('5. func_call', func_call)
                logger.info(f"In Function Call {func_call.func_name}")
                print(f"In Function Call {func_call.func_name}")
                
                if func_call.func_name == "end_call":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=self.END_SENTENCE_DYNAMIC,
                        content_complete=True,
                        end_call=True,
                    )
                    yield response                    
                
                elif func_call.func_name == "transfer_call":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="I will go ahead and transfer your call to one of our team members to help you further. Please wait. ",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    )
                    yield response
                    resp, func_call = await self.transfer_call_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result=func_call)

                elif func_call.func_name == "send_email":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I deliver your messsage to our team",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True,
                    )
                    yield response
                    resp, func_call = await self.send_email(func_call.arguments, func_call, request)
                    yield resp
                    self.draft_response(request, func_result=func_call)

                elif func_call.func_name == "get_patient_data_from_dynamo":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="-",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True,
                    )
                    yield response
                    resp, func_call = await self.get_patient_data_from_dynamo_nookal(func_call.arguments, func_call, request)
                    yield resp
                    self.draft_response(request, func_result=func_call)
                
                elif func_call.func_name == "get_next_available_slot":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="while I look into our system for some available times",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True,
                    )
                    yield response
                    resp, func_call = await self.get_next_available_slot_nookal(func_call.arguments, func_call, request)
                    yield resp
                    self.draft_response(request, func_result=func_call)
                    
                elif func_call.func_name == "get_specific_available_slot":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I look into our system for some available times",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True,
                    )
                    yield response
                    resp, func_call = await self.get_specific_day_slots_nookal(func_call.arguments, func_call, request)
                    yield resp
                    self.draft_response(request, func_result=func_call)

                elif func_call.func_name == "create_appointment_new_patient":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I book in your appointment",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    )
                    yield response
                    resp, func_call = await self.create_appointment_new_patient_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request=request, func_result=func_call)

                elif func_call.func_name == "create_appointment_existing_patient":
                    print(f"Func Call: {func_call.func_name}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I book in your appointment",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    )

                    print("response 1. create_appointment_existing_patient", response)
                    yield response
                    resp, func_call = await self.create_appointment_existing_patient_nookal(
                        func_call.arguments, func_call, request
                    )
                    print("response 2. create_appointment_existing_patient", resp)
                    yield resp
                    self.draft_response(request=request, func_result=func_call)

                elif func_call.func_name == "update_individual_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    print(f"Func Call: {func_call.func_name}")
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content= "Please give me a moment while I reschedule your appointment",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    )
                    yield response
                    resp, func_call = await self.update_appointment_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request=request, func_result=func_call)

                elif func_call.func_name == "get_patient_appointment":
                    print(f"Func Call: {func_call.func_name}")
                    # print('6. func_call', func_call)
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a second while look at our appointments",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    ) 
                    print(f'1. {response}')
                    yield response

                    resp, func_call = await self.get_patient_appointment_nookal(
                        func_call.arguments, func_call, request
                    )

                    print(f'2. {resp}')
                    # print('7. func_call', func_call)
                    yield resp
                    # print('8. func_call', func_call)
                    self.draft_response(request=request, func_result=func_call)

                elif func_call.func_name == "cancel_individual_appointment":
                    print(f"Func Call: {func_call.func_name}")
                    # print('6. func_call', func_call)
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I cancel your appointment",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    ) 
                    print(f'1. {response}')
                    yield response

                    resp, func_call = await self.cancel_appointment_nookal(
                        func_call.arguments, func_call, request
                    )

                    print(f'2. {resp}')
                    # print('7. func_call', func_call)
                    yield resp
                    # print('8. func_call', func_call)
                    self.draft_response(request=request, func_result=func_call)
            else:
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content='',
                    content_complete=True,
                    end_call=False,
                    no_interruption_allowed=False
                )
                yield response 
        except Exception as err:
            logger.error(err)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="Sorry but there seems to be an error, Please try again later",
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )


    def convert_readable_datetime(self, iso_string):
        # Parse the ISO 8601 string
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

    def add_hours_from_time(self, time_str, hours_to_add):
        # Parse the string to a datetime object
        original_time = datetime.fromisoformat(time_str)
        
        # Add the specified hours
        new_time = original_time + timedelta(hours=hours_to_add)
        
        # Format the new time as UTC
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return utc_time_str

    def get_user_id(self, call_id):
            call_info = retell.call.retrieve(call_id)
            return call_info.agent_id

    def compare_params(self, dict1, dict2):
        print("DICT1 in compare_params func:", dict1)
        print("DICT2 in compare_params func:", dict2)

        # Compare only the keys present in both dictionaries
        common_keys = set(dict1.keys()).intersection(set(dict2.keys()))
        print("Common keys:", common_keys)

        for key in common_keys:
            value1, value2 = dict1.get(key), dict2.get(key)

            # Skip keys with None values in either dictionary
            if value1 is None or value2 is None:
                print("Skipping key due to None value:", key)
                continue

            # Handle nested dictionaries
            if isinstance(value1, dict) and isinstance(value2, dict):
                print(f"Key '{key}': Comparing nested dictionaries.")
                if not self.compare_params(value1, value2):
                    print(f"Mismatch found in nested dictionary for key '{key}'")
                    return False

            # Handle lists or sets
            elif isinstance(value1, (list, set)) and isinstance(value2, (list, set)):
                print(f"Key '{key}': Comparing lists/sets.")
                if set(value1) != set(value2):  # Allow unordered comparison
                    print(f"Mismatch found in list/set for key '{key}': {value1} != {value2}")
                    return False

            # Handle string comparison (case-insensitive)
            elif isinstance(value1, str) and isinstance(value2, str):
                print(f"Key '{key}': Comparing strings.")
                if value1.lower() != value2.lower():
                    print(f"Mismatch found in strings for key '{key}': {value1} != {value2}")
                    return False

            # Handle scalar value comparison (e.g., int, float)
            elif value1 != value2:
                print(f"Key '{key}': Comparing scalar values.")
                print(f"Mismatch found for key '{key}': {value1} != {value2}")
                return False

            # Handle type mismatches (e.g., dict vs string)
            elif type(value1) != type(value2):
                print(f"Type mismatch for key '{key}': {type(value1)} != {type(value2)}")
                return False

        # If all common keys match, return True
        return True

    async def check_function_already_called(self, func, params: dict): 
        
        if func in self.function_calls:
            stored_params = self.function_calls[func]['params']
            
            compare_params = self.compare_params(stored_params, params)
            print("COMPARE PARAMS-----" , compare_params)
            if compare_params:
                return True
            else:
                return False
        else:
            self.function_calls[func] = {'finished': False}    
            return False
