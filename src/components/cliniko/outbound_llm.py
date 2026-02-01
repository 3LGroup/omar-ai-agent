import json
import pytz
from datetime import datetime, timedelta
from typing import List
from openai import OpenAI
import os
from src.logger import logger
from src.utils.custom_types import (
    Utterance,
    CustomLlmRequest,
    CustomLlmResponse,
    FunctionCall,
)
from src.components.cliniko import cliniko_function_calls_schema
from src.components.cliniko.cliniko_client import ClinikoClient
from datetime import datetime
from src.constants import (
    BEGIN_SENTENCE,
    SYSTEM_PROMPT,
    AGENT_PROMPT,
    APPOINTMENT_CONFIRMATION_CLINIKO_AGENT_PROMPT,
    PATIENT_REVIEW_CLINIKO_AGENT_PROMPT,
    RESCHEDULE_CLINIKO_AGENT_PROMPT,
    PATIENT_OUTREACH_CLINIKO_AGENT_PROMPT
)
from src.utils.session_vars import user_data

class OutboundLLMCliniko:
    def __init__(self, agent_type="RESCHEDULE", metadata=None):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
        )
        self.agent_type = agent_type
        self.cliniko = ClinikoClient()
        self.metadata = metadata

    async def update_booking_cliniko(self, params: dict, func_call, request):
        logger.info('Updating Appointment')
        logger.info(f'Updating Appointment params {params}')        
        params.pop("message", None)

        response, status = await self.cliniko.update_individual_appointment(params)
        logger.info(f"response from cliniko {response}")
        # response = {
        #     "patient_name": "John Doe",
        #     "starts_at": "2022-06-01T10:00:00Z",
        #     "ends_at": "2022-06-01T11:00:00Z"
        # }
        # status = 200

        if status == 200:
            logger.info("Success")
            patient_name = response['patient_name']
            new_starts_date = self.convert_readable_datetime(response["starts_at"]) # response["starts_at"]
            user_data['success'] = True

            responset_text = f"""Appointment updated successfully for patient name {patient_name}
                New Start Date is {new_starts_date}
                Please write it down for future use. Take care and Goodbye
                """
            
            func_call.result = responset_text

            response = CustomLlmResponse(
                response_id=request.response_id,
                content=responset_text,
                content_complete=True,
                end_call=True,
            )
            return response, func_call
        
        elif status == 404 and response == "Patient not found":
            logger.error(f"Error booking appointment. Patient not found")
            func_call.result = "Could not find Patient with the provided data, Please Try Again Later"
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="Could not find Patient with the provided data, Please Try Again Later",
                content_complete=True,
                end_call=True,
            )
            user_data['success'] = False

            return response, func_call

        elif status == 404 and response == "Appointment not found":
            logger.error(f"Error booking appointment. Appointment not found")
            func_call.result = "Could not find Appointment with the provided data, Please Try Again Later"
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="Could not find Appointment with the provided data, Please Try Again Later",
                content_complete=True,
                end_call=True,
            )
            user_data['success'] = False

            return response, func_call

        elif status == 409:
            logger.error(f"Error booking appointment. Appointment conflict")
            func_call.result = "There is an appointment conflict, Please Try Again Later"
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="There is an appointment conflict, Please Try Again Later",
                content_complete=True,
                end_call=True,
            )
            user_data['success'] = False
            return response, func_call

        else:
            logger.error("Error")
            func_call.result = "Unkwown Error Occured, Please Try Again Later"
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="Unkwown Error Occured, Please Try Again Later",
                content_complete=True,
                end_call=True,
            )
            user_data['success'] = False
            return response, func_call

    async def create_appointment_existing_patient_cliniko(self, params: dict, func_call, request):
            logger.info(f"Booking an appointment with Cliniko")
            response, status = await self.cliniko.create_appointment_existing_patient(params)

            logger.info(f"response from cliniko {response}")

            if status == 201:
                logger.info(f"Appointment booked successfully")
                # appointment_id = response["id"]
                patient_name = response['patient_name']
                appointment_date = self.convert_readable_datetime(response["starts_at"])
                logger.info(f"patient name {patient_name} and appointment date {appointment_date}")
                response_text = f"""Excellent, {patient_name}. Your appointment has been successfully booked for {appointment_date} We look forward to seeing you then. Thank you for your time, and have a great day!"""

                func_call.result = response_text

                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content=response_text,
                    content_complete=True,
                    end_call=True,
                )
                user_data['success'] = True
                return response, func_call
            
            elif status == 404 and response == "Patient not found":
                logger.error(f"Error booking appointment. Patient not found")
                func_call.result = "Could not find Patient with the provided data, Please Try Again Later"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="Could not find Patient with the provided data, Please Try Again Later",
                    content_complete=True,
                    end_call=True,
                )
                user_data['success'] = False
                return response, func_call
            
            # Handle booking conflict
            elif status == 409 and response == "Booking Conflict":
                logger.error(f"Appointment conflict")
                func_call.result = "There is an appointment conflict, Please Try Again Later"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="There is an appointment conflict, Please Try Again Later",
                    content_complete=True,
                    end_call=True,
                )
                user_data['success'] = False
                return response, func_call

            else:
                user_data['success'] = False
                logger.error(f"Error booking appointment. {response}")
                func_call.result = "Error booking appointment, Please Try Again Later"
                response = CustomLlmResponse(
                
            )

    async def cancel_appointment_cliniko(self, params: dict, func_call, request):
                logger.info("Cancelling Appointment")

                response, status = await self.cliniko.cancel_individual_appointment(params)
                logger.info(f"Response from Cliniko {response}")

                if status == 204: # 204 means updated -> cancelled
                    logger.info("Success")

                    responset_text = f"""Your appointment has been cancelled successfully. Thank you for your time, and have a great day!"""
                    
                    func_call.result = responset_text

                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=responset_text,
                        content_complete=True,
                        end_call=True,
                    )
                    user_data['success'] = True
                    return response, func_call
                
                elif status == 404 and response == "Appointment not found":
                    logger.error(f"Error canceling appointment. Appointment not found")
                    func_call.result = "Could not find Appointment with the provided data, Please Try Again Later"
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Could not find Appointment with the provided data, Please Try Again Later",
                        content_complete=True,
                        end_call=True,
                    )
                    user_data['success'] = False
                    return response, func_call
                
                elif status == 404 and response == "Patient not found":
                    logger.error(f"Error canceling appointment. Patient not found")
                    func_call.result = "Could not find Patient with the provided data, Please Try Again Later"
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Could not find Patient with the provided data, Please Try Again Later",
                        content_complete=True,
                        end_call=True,
                    )
                    user_data['success'] = False
                    return response, func_call

                else:
                    logger.error("Error")
                    func_call.result = "Unkwown Error Occured, Please Try Again Later"
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Unkwown Error Occured, Please Try Again Later",
                        content_complete=True,
                        end_call=True,
                    )
                    user_data['success'] = False
                    return response, func_call

    def select_begin_message(self):
        if self.agent_type == "RESCHEDULE":
            return f"""Hi this is Julie speaking from Melbourne Foot and Ankle Clinic.
            Unfortunately, {self.metadata['dr']} has cancelled the appointment due to {self.metadata['reason']}
            and I need to reschedule your appointment.
            Your name is {self.metadata['first_name']} {self.metadata['last_name']} and your date of birth is {self.metadata['date_of_birth']}.
            When are you available again?"""
        
        elif self.agent_type == "PATIENT_REVIEW":
            return f"""Hello, {self.metadata['first_name']}. This is Alex calling from UFD. I hope you're doing well.
            I'm reaching out to follow up on your recent surgery. How have you been feeling since your procedure?"""
        
        elif self.agent_type == "APPOINTMENT_CONFIRMATION":
            return f""" Hello, {self.metadata['first_name']}. This is Alex calling from UFD. I hope you're doing well.
            I'm reaching out to let you know that you have an appointment with Dr. {self.metadata['dr']} on 
            {self.convert_readable_datetime(self.metadata['appointment_date'])}. Would you like to confirm your appointment?
            """

        elif self.agent_type == "PATIENT_OUTREACH":
            return f""" Hello, {self.metadata['first_name']}. This is Alex calling from UFD. I hope you're doing well. I am calling you for a
            review appointment with Doctor {self.metadata['dr']}. Please let me know if you are available for a review appointment."""
 
        else:
            return BEGIN_SENTENCE
        
    def draft_begin_message(self):
        response = CustomLlmResponse(
            response_id=0,
            content=self.select_begin_message(),
            content_complete=True,
            end_call=False,
        )
        return response

    def convert_transcript_to_openai_messages(self, transcript: List[Utterance]):
        messages = []
        for utterance in transcript:
            if utterance["role"] == "agent":
                messages.append({"role": "assistant", "content": utterance["content"]})
            else:
                messages.append({"role": "user", "content": utterance["content"]})
        return messages
    
    def prepare_prompt(self, request: CustomLlmRequest, func_result: FunctionCall):
        # if its an outbound reschedule agent
        current_datetime = datetime.now()

        # To get the name of the day
        day_of_week_name = current_datetime.strftime('%A')

        if self.agent_type == "RESCHEDULE":
            prompt = [
                {
                    "role": "system",
                    "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()}",
                },
                {
                    "role": "system",
                    "content": f"""First name, Last name and date of birth are known and Original Appointment Date are known,
                    first_name={self.metadata["first_name"]} last_name={self.metadata["last_name"]} 
                    date_of_birth={self.metadata["date_of_birth"]} and original_appointment_start_datetime={self.metadata["old_start_date"]}
                    and original_appointment_end_datetime={self.metadata["old_end_date"]}

                    {RESCHEDULE_CLINIKO_AGENT_PROMPT}""",
                },
                {
                    "role": "assistant",
                    "content": self.select_begin_message(),
                },
            ]

        elif self.agent_type == "PATIENT_REVIEW":
            prompt = [
                {
                    "role": "system",
                    "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()}",
                },
                {
                    "role": "system",
                    "content": f"""First name, last name are known. first_name={self.metadata['first_name']} last_name={self.metadata['last_name']}
                    . Following is the context.""",
                        # The patient appointment was on {self.convert_readable_datetime(self.metadata['appointment_date'])}
                },
                {
                    "role": "system",
                    "content": f"{PATIENT_REVIEW_CLINIKO_AGENT_PROMPT}",
                }
            ]

        elif self.agent_type == "APPOINTMENT_CONFIRMATION":
            prompt = [
                {
                    "role": "system",
                    "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()}",
                },
                {
                    "role": "system",
                    "content": f"""First name, last name are known. first_name={self.metadata['first_name']} last_name={self.metadata['last_name']} 
                    date_of_birth={self.metadata['date_of_birth']} and the appointment start date is {self.add_hours_from_time(self.metadata['appointment_date'], 10)}
                    . Following is the context.""",
                }, 
                {
                    "role": "system",
                    "content": f"{APPOINTMENT_CONFIRMATION_CLINIKO_AGENT_PROMPT}",
                }
            ]

        elif self.agent_type == "PATIENT_OUTREACH":
            prompt = [
                {
                    "role": "system",
                    "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()}",
                },
                {
                    "role": "system",
                    "content": f"""First name, last name are known. first_name={self.metadata['first_name']} last_name={self.metadata['last_name']} 
                    date_of_birth={self.metadata['date_of_birth']}
                    . Following is the context.""",
                }, 
                {
                    "role": "system",
                    "content": f"{PATIENT_OUTREACH_CLINIKO_AGENT_PROMPT}",
                }
            ]

        else:
            prompt = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT + AGENT_PROMPT,
                },
                   {
                    "role": "system",
                    "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()} ",
                },
            
            ]
      
        transcript_messages = self.convert_transcript_to_openai_messages(
            request.transcript
        )
        for message in transcript_messages:
            prompt.append(message)

        #  Populate func result to prompt so that GPT can know what to say given the result

        if func_result is not None:
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
                    "content": "(Now the user has not responded in a while, you would say:)",
                }
            )
        return prompt
    
    def initialize_outbound_functions(self):
        functions = [
            cliniko_function_calls_schema.end_call_function_schema,
            cliniko_function_calls_schema.update_outbound_appointment_schema,
            cliniko_function_calls_schema.create_appointment_existing_patient_schema,
            cliniko_function_calls_schema.cancel_individual_appointment_schema
        ]
        return functions
    
    async def draft_response(self, request, func_result: FunctionCall = None):
        try:
            models = ["gpt-4-turbo", "gpt-3.5-turbo-1106", "gpt-4o"]
            prompt = self.prepare_prompt(request, func_result)
            # func_call = {}
            func_call: FunctionCall = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                model=models[2],
                messages=prompt,
                stream=True,
                tools=self.initialize_outbound_functions(),
                tool_choice="auto",
            )

            for chunk in stream:
                # Step 3: Extract the functions
                # print('Chunk')
                if len(chunk.choices) == 0:
                    continue
                # print(chunk.choices[0])

                if chunk.choices[0].delta.tool_calls:
                    tool_calls = chunk.choices[0].delta.tool_calls[0]
                    if tool_calls.id:
                        if func_call:
                            # Another function received, old function complete, can break here.
                            break
                        func_call = FunctionCall(
                            id=tool_calls.id,
                            func_name=tool_calls.function.name or "",
                            arguments={},
                        )
                    else:
                        # append argument
                        func_arguments += tool_calls.function.arguments or ""

                # Parse transcripts
                if chunk.choices[0].delta.content:
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=chunk.choices[0].delta.content,
                        content_complete=False,
                        end_call=False,
                    )
                    yield response

            # Step 4: Call the functions
            if func_call is not None:

                logger.info(f"In Function Call {func_call.func_name}")
                
                if func_call.func_name == "end_call":
                    logger.info(f"In Function Call {func_call.func_name}")
                    logger.info(f"{chunk.choices[0]}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                
                if func_call.func_name == "update_outbound_appointment":
                        logger.info(f"In Function Call {func_call.func_name}")
                        # parse arguments
                        func_call.arguments = json.loads(func_arguments)
                        logger.info(f"Rescheduling appointment arguments {func_call.arguments}")
                        response = CustomLlmResponse(
                            response_id=request.response_id,
                            content="Rescheduling your appointment",
                            content_complete=False,
                            end_call=False,
                        )
                        yield response
                        logger.info(f"Making function call {func_call.arguments}")
                        print('=======> FUnction Call ==========>')
                        resp, func_call = await self.update_booking_cliniko(
                            func_call.arguments, func_call, request
                        )
                        # resp = CustomLlmResponse(
                        #     response_id=request.response_id,
                        #     content="Rescheduling your appointment",
                        #     content_complete=False,
                        #     end_call=False,
                        # )
                        logger.info(f"{resp}")
                        yield resp
                        self.draft_response(request, func_result)
                elif func_call.func_name == "create_appointment_existing_patient":
                        logger.info(f"In Function Call {func_call.func_name}")
                        # parse arguments
                        func_call.arguments = json.loads(func_arguments)
                        logger.info(f"Creating appointment existing patient arguments {func_call.arguments}")
                        response = CustomLlmResponse(
                            response_id=request.response_id,
                            content="Booking your appointment",
                            content_complete=False,
                            end_call=False,
                        )
                        yield response
                        logger.info(f"Making function call {func_call.arguments}")
                        print('=======> FUnction Call ==========>')
                        resp, func_call = await self.create_appointment_existing_patient_cliniko(
                            func_call.arguments, func_call, request
                        )
                        # resp = CustomLlmResponse(
                        #     response_id=request.response_id,
                        #     content="Rescheduling your appointment",
                        #     content_complete=False,
                        #     end_call=False,
                        # )
                        logger.info(f"{resp}")
                        yield resp
                        self.draft_response(request, func_result)
                elif func_call.func_name == "cancel_individual_appointment":
                        logger.info(f"In Function Call {func_call.func_name}")
                        # parse arguments
                        func_call.arguments = json.loads(func_arguments)
                        logger.info(f"Creating appointment existing patient arguments {func_call.arguments}")
                        response = CustomLlmResponse(
                            response_id=request.response_id,
                            content="Canceling your appointment",
                            content_complete=False,
                            end_call=False,
                        )
                        yield response
                        logger.info(f"Making function call {func_call.arguments}")
                        print('=======> FUnction Call ==========>')
                        resp, func_call = await self.cancel_appointment_cliniko(
                            func_call.arguments, func_call, request
                        )
                        # resp = CustomLlmResponse(
                        #     response_id=request.response_id,
                        #     content="Rescheduling your appointment",
                        #     content_complete=False,
                        #     end_call=False,
                        # )
                        logger.info(f"{resp}")
                        yield resp
                        self.draft_response(request, func_result)
            else:
                # No functions, complete response
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="",
                    content_complete=True,
                    end_call=False,
                )
                yield response
        except Exception as e:
            print(e)
            logger.error(e)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="There was an error, please call again",
                content_complete=True,
                end_call=True,
            )
            yield response

    def convert_readable_datetime(self, iso_string):
        # Parse the ISO 8601 string
        malaysian_time = self.add_hours_from_time(iso_string, 10)
        dt = datetime.fromisoformat(malaysian_time.replace('Z', '+00:00'))
        
        # Convert to the desired timezone (e.g., UTC)
        dt = dt.astimezone(pytz.UTC)
        
        # Manually format the day to remove leading zero
        day = dt.day
        date_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day if day < 20 else day % 10, 'th')
        if 11 <= day <= 13:
            date_suffix = 'th'
        
        formatted_date = f"{day}{date_suffix} {dt.strftime('%B')}"
        
        # Format the time
        formatted_time = dt.strftime("%I %p").lower().strip()
        
        return f"{formatted_date} {formatted_time}"

    def add_hours_from_time(self, time_str, hours_to_add):
        # Parse the string to a datetime object
        original_time = datetime.fromisoformat(time_str)
        
        # Add the specified hours
        new_time = original_time + timedelta(hours=hours_to_add)
        
        # Format the new time as UTC
        utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return utc_time_str
    