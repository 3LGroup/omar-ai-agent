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
from src.components.gohighlevel.gohighlevel_client import GoHighLevelClient
from src.components.gohighlevel import gohighlevel_function_calls_schema
from datetime import datetime, timezone
from src.components.prompts.main_prompts import PROMPTS
from src.utils.session_vars import user_data
from src.db.db import DB

db_instance = DB()

class GoHighLevelInboundLLMClient:
    def __init__(self, call_id, agent_type="BOOKING"):
        self.client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.metadata = {}
        self.agent_type = agent_type
        self.user_id = self.get_user_id(call_id)
        self.call_id = call_id
        self.clinic_data = db_instance.get_clinic_data_sync(self.user_id)
        self.access_token = self.clinic_data['access_token']
        self.refresh_token = self.clinic_data['refresh_token']
        self.token_expires_at = self.clinic_data['token_expires_at']
        
        logger.info(f"Initializing GoHighLevel LLM Client for user_id: {self.user_id}")
        
        # Use GoHighLevel specific prompts if available, otherwise use default
        self.prompts = PROMPTS.get(self.clinic_data['inboundPrompt'], "") + \
                      PROMPTS.get(self.clinic_data['inboundPromptBooking'], "")
        
        self.businessName = self.clinic_data['businessName']
        self.agentName = self.clinic_data['agentName']
        self.location_id = self.clinic_data['ghl_location_id']
        
        # Initialize GoHighLevel client
        self.ghl_client = GoHighLevelClient(call_id=self.call_id, user_id=self.user_id, access_token=self.access_token, refresh_token=self.refresh_token, token_expires_at=self.token_expires_at)
        
        self.BEGIN_SENTENCE_DYNAMIC = self.clinic_data['beginSentence']
        self.END_SENTENCE_DYNAMIC = self.clinic_data['endSentence']
        
        self.function_calls = {}
        self.data = []
    
    async def create_appointment_new_customer_ghl(self, params: dict, func_call, request):
        """Create appointment for a new customer in GoHighLevel"""
        logger.info(f"Params in create_appointment_new_customer_ghl function: {params}")
        
        function_called = await self.check_function_already_called('create_appointment_new_customer_ghl', params)
        logger.info(f'Function called: {function_called}')
        logger.info(f'Function finished?: {self.function_calls.get("create_appointment_new_customer_ghl", {}).get("finished", False)}')
        
        if function_called and self.function_calls['create_appointment_new_customer_ghl']['finished']:
            logger.info("Function already called")
            
            func_call.result = self.function_calls['create_appointment_new_customer_ghl']['response']
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['create_appointment_new_customer_ghl']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )
            
            user_data['success'] = True
            return response, func_call
        
        logger.info("Creating new appointment for customer")
        self.function_calls['create_appointment_new_customer_ghl']['params'] = params

        # Check if start time is in the future
        start_dt = params['startTime']
        # if start_dt <= datetime.now():
        #     response_text = "Sorry but the date you have chosen is in the past. Can you please give me a date from today onwards?"
            
        #     func_call.result = response_text
            
        #     response = CustomLlmResponse(
        #         response_id=request.response_id,
        #         content=response_text,
        #         content_complete=True,
        #         end_call=False,
        #         no_interruption_allowed=True,
        #     )
        #     user_data['success'] = False
        #     self.function_calls['create_appointment_new_customer_ghl']['response'] = response_text
        #     self.function_calls['create_appointment_new_customer_ghl']['finished'] = True
        #     return response, func_call
        
        # Create appointment
        result, status = await self.ghl_client.create_appointment_new_customer(self.location_id, params)
        
        if status == 200 or status == 201:
            logger.info("Appointment booked successfully")
            
            # Convert time back to readable format
            # start_time_readable = self.convert_readable_datetime(start_dt)
            
            response_text = f"I have gone ahead and scheduled your appointment. Is there anything else I could help you with?"
            
            func_call.result = response_text
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True,
            )

            self.function_calls['create_appointment_new_customer_ghl']['response'] = response_text
            self.function_calls['create_appointment_new_customer_ghl']['finished'] = True
            
            return response, func_call
        
        elif status == 409:
            logger.error("Appointment conflict - time slot already booked")
            response_text = "Unfortunately that appointment time has already been taken. Would you like to choose a different time?"
            func_call.result = response_text
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            
            self.function_calls['create_appointment_new_customer_ghl']['response'] = response_text
            self.function_calls['create_appointment_new_customer_ghl']['finished'] = False
            user_data['success'] = False
            return response, func_call
        
        else:
            logger.error(f"Error booking appointment. Status: {status}, Result: {result}")
            response_text = "Sorry but there seems to be an error with booking the appointment. I will have to pass on your information onto our team and a team member will get in contact with you."
            func_call.result = response_text
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            
            self.function_calls['create_appointment_new_customer_ghl']['response'] = response_text
            self.function_calls['create_appointment_new_customer_ghl']['finished'] = True
            user_data['success'] = False
            return response, func_call
    
    async def cancel_appointment_ghl(self, params: dict, func_call, request):
        """Cancel an appointment in GoHighLevel"""
        logger.info(f"Params in cancel_appointment_ghl function: {params}")
        
        function_called = await self.check_function_already_called('cancel_appointment_ghl', params)
        logger.info(f'Function called: {function_called}')
        logger.info(f'Function finished?: {self.function_calls.get("cancel_appointment_ghl", {}).get("finished", False)}')
        
        if function_called and self.function_calls['cancel_appointment_ghl']['finished']:
            logger.info("Function already called")
            
            func_call.result = self.function_calls['cancel_appointment_ghl']['response']
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=self.function_calls['cancel_appointment_ghl']['response'],
                content_complete=True,
                end_call=False,
                no_interruption_allowed=False
            )
            
            user_data['success'] = True
            return response, func_call
        
        logger.info("Cancelling appointment")
        self.function_calls['cancel_appointment_ghl']['params'] = params
        
        # Cancel appointment
        result, status = await self.ghl_client.cancel_appointment(self.location_id, params)
        
        if status == 200 or status == 204:
            logger.info("Appointment cancelled successfully")
            
            response_text = f"Thank you. I have gone ahead and cancelled your appointment. Was there anything else I could help you with?"
            
            func_call.result = response_text
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            
            self.function_calls['cancel_appointment_ghl']['response'] = response_text
            self.function_calls['cancel_appointment_ghl']['finished'] = True
            
            return response, func_call
        
        elif status == 404:
            logger.error("Appointment not found")
            response_text = f"Sorry but I can't seem to find your appointment on our system. Can you please repeat the appointment details?"
            func_call.result = response_text
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=False,
                no_interruption_allowed=True
            )
            
            self.function_calls['cancel_appointment_ghl']['response'] = response_text
            self.function_calls['cancel_appointment_ghl']['finished'] = False
            user_data['success'] = False
            return response, func_call
        
        else:
            logger.error(f"Error cancelling appointment. Status: {status}, Result: {result}")
            response_text = "Sorry but there seems to be an error when cancelling your appointment. I will have to pass on your information onto our team and a team member will get in contact with you."
            func_call.result = response_text
            
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            
            self.function_calls['cancel_appointment_ghl']['response'] = response_text
            self.function_calls['cancel_appointment_ghl']['finished'] = True
            user_data['success'] = False
            return response, func_call
    
    def draft_begin_message(self):
        """Draft the beginning message for the call"""
        response = CustomLlmResponse(
            response_id=0,
            content=self.BEGIN_SENTENCE_DYNAMIC,
            content_complete=True,
            end_call=False,
            no_interruption_allowed=True
        )
        return response
    
    def prepare_prompt(self, request: CustomLlmResponse, func_result: FunctionCall):
        """Prepare the prompt for OpenAI"""
        logger.info("Preparing prompt for OpenAI")
        
        TODAY_DATE = datetime.now().strftime('%A, %B %d, %Y')
        TODAY_TIME = datetime.now().strftime("%H:%M:%S")
        
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
        
        transcript_messages = self.convert_transcript_to_openai_messages(request.transcript)
        for message in transcript_messages:
            prompt.append(message)
        
        if func_result:
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
        
        return prompt
    
    def convert_transcript_to_openai_messages(self, transcript: List[Utterance]):
        """Convert transcript to OpenAI messages format"""
        messages = []
        for utterance in transcript:
            role = "assistant" if utterance["role"] == "agent" else "user"
            messages.append({"role": role, "content": utterance["content"]})
        return messages
    
    def initialize_functions(self):
        """Initialize function schemas"""
        functions = [
            gohighlevel_function_calls_schema.end_call_function_schema,
            gohighlevel_function_calls_schema.create_appointment_new_customer_schema,
            gohighlevel_function_calls_schema.cancel_appointment_schema,
        ]
        return functions
    
    async def draft_response(self, request, func_result=None):
        """Draft response using OpenAI"""
        try:
            models = ["gpt-4-turbo", "gpt-3.5-turbo-0125", "gpt-4o", "gpt-4.1"]
            prompt = self.prepare_prompt(request, func_result)
            logger.info('Prompt prepared, calling OpenAI')
            
            func_call: FunctionCall = {}
            func_arguments = ""
            
            stream = await self.client.chat.completions.create(
                model=models[2],  # gpt-4o
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
                    
                    if tool_calls.id:
                        if func_call:
                            break
                        
                        func_call = FunctionCall(
                            id=tool_calls.id,
                            func_name=tool_calls.function.name or "",
                            arguments={},
                        )
                    else:
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
                logger.info(f"Function called: {func_call.func_name}")
                
                if func_call.func_name == "end_call":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=self.END_SENTENCE_DYNAMIC,
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                
                elif func_call.func_name == "create_appointment_new_customer":
                    logger.info("Creating appointment for new customer")
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I book in your appointment.",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    )
                    yield response
                    
                    resp, func_call = await self.create_appointment_new_customer_ghl(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request=request, func_result=func_call)
                
                elif func_call.func_name == "cancel_appointment":
                    logger.info("Cancelling appointment")
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Please give me a moment while I cancel your appointment.",
                        content_complete=False,
                        end_call=False,
                        no_interruption_allowed=True
                    )
                    yield response
                    
                    resp, func_call = await self.cancel_appointment_ghl(
                        func_call.arguments, func_call, request
                    )
                    yield resp
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
            logger.error(f"Error in draft_response: {err}")
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="Sorry but there seems to be an error. Please try again later.",
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True
            )
            yield response
    
    def convert_readable_datetime(self, dt):
        """Convert datetime to readable format"""
        day = dt.day
        date_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day if day < 20 else day % 10, 'th')
        if 11 <= day <= 13:
            date_suffix = 'th'
        
        formatted_date = f"{day}{date_suffix} {dt.strftime('%B')}"
        formatted_time = dt.strftime("%I:%M %p").lower().strip()
        
        return f"{formatted_date} {formatted_time}"
    
    def get_user_id(self, call_id):
        """Get user ID from call information"""
        logger.info(f"Getting user ID for call_id: {call_id}")
        call_info = retell.call.retrieve(call_id)
        return call_info.agent_id
    
    def compare_params(self, dict1, dict2):
        """Compare parameters to check if function was already called with same params"""
        common_keys = set(dict1.keys()).intersection(set(dict2.keys()))
        
        for key in common_keys:
            value1, value2 = dict1.get(key), dict2.get(key)
            
            if key == "context":
                continue
            
            if value1 is None or value2 is None:
                continue
            
            if isinstance(value1, dict) and isinstance(value2, dict):
                if not self.compare_params(value1, value2):
                    return False
            
            elif isinstance(value1, (list, set)) and isinstance(value2, (list, set)):
                if set(value1) != set(value2):
                    return False
            
            elif isinstance(value1, str) and isinstance(value2, str):
                if value1.lower() != value2.lower():
                    return False
            
            elif value1 != value2:
                return False
            
            elif type(value1) != type(value2):
                return False
        
        return True
    
    async def check_function_already_called(self, func, params: dict):
        """Check if function was already called with same parameters"""
        if func in self.function_calls:
            stored_params = self.function_calls[func]['params']
            compare_params = self.compare_params(stored_params, params)
            
            if compare_params:
                return True
            else:
                return False
        else:
            self.function_calls[func] = {'finished': False}
            return False

