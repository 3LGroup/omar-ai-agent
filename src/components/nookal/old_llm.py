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
from src.constants import (
    BEGIN_SENTENCE,
    SYSTEM_PROMPT,
    AGENT_PROMPT,
    RESCHEDULE_CLINIKO_AGENT_PROMPT
)

class InboundLLMClient:
    def __init__(self, agent_type="BOOKING"):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
        )

        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.metadata = {}
        self.agent_type = agent_type
        self.nookal = NookalClient()

    async def search_patient_with_nookal(
        self,params: dict, func_call, request,
      ):
        logger.info("Search Patients")
        response = await self.nookal.search_patient(
            params
        )
        print(response)
        if response["status"] == "success":
            if len(response['data']['results']['patients'])>0:
                patient_id = response['data']['results']['patients'][0]['ID']
                func_call.result = f"Patient ID: {patient_id}"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= f"Your Patient ID: {patient_id} is this, do you want to book an appointment?",
                    content_complete=True,
                    end_call=False,
                )
                return response, func_call
            else:
                func_call.result = "No Patients Found with the following details"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= "No Patients Found with the following details, please try again later",
                    content_complete=True,
                    end_call=True,
                )
                return response, func_call
           
        else:
            logger.error("Error")
            func_call.result = (
                "Error ocurred while searching patient, Please Try Again Later"
            )
            return response, func_call

    async def add_patient(
        self,params: dict, func_call, request,
      ):
        logger.info("Add Patients")
        response = await self.nookal.add_patient(
            params
        )
        print(response)
        if response["status"] == "success":
                patient_id = response['data']['results']['patient_id']
                func_call.result = f"Patient ID: {patient_id}"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= f"Your Patient ID: {patient_id} is this, do you want to book an appointment?",
                    content_complete=True,
                    end_call=False,
                )
                return response, func_call
            
        else:
            logger.error("Error")
            func_call.result = (
                "Error ocurred while adding patient, Please Try Again Later"
            )
            return response, func_call

    async def cancel_appointment(
        self,params: dict, func_call, request,
      ):
        
        params['patient_id'] = await self.nookal.get_patient_id(params)
        params['appointment_id'] = await self.nookal.get_appointment_id(params)
        logger.info("Cancel Appointment")
        response = await self.nookal.cancel_appointment(
            params
        )
        print(response)
        if response["status"] == "success":
                rp= f"Appointment cancelled for Patient ID: {params['patient_id']}"
                func_call.result = rp
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content= rp,
                    content_complete=True,
                    end_call=False,
                )
                return response, func_call
            
        else:
            logger.error("Error")
            func_call.result = (
                "Error ocurred while cancelling appointment, Please Try Again Later"
            )
            return response, func_call
   
    async def book_with_nookal(self, params: dict, func_call, request):
        # params["location_id"] = 1
        # params["practitioner_id"] = 1
        # params["appointment_type_id"] = 4
        
        params["location_id"] = await self.nookal.get_location_id(params)
        params["practitioner_id"] = await self.nookal.get_practitioner_id(params)
        params["appointment_type_id"] = await self.nookal.get_appointment_type_id(params)
        params['patient_id'] = await self.nookal.get_patient_id(params)
        
        params.pop("message", None)

        logger.info("Booking Appointment")
        response = self.nookal.add_appointment_booking(params)
        logger.info(response)
        if response["status"] == "success":
            logger.info("Success")
            appointment_id = response["data"]["results"]["appointment_id"]
            case_id = response["data"]["results"]["case_id"]
            response_text = f"""Appointment booked successfully for Patient ID
            {params['patient_id']} Appointment ID is {appointment_id} Case ID is {case_id},
            Please note it down somewhere for future use, Do you want to end the call?"""
            func_call.result = response_text
            # print("Response Success")
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=False,
            )
            return response, func_call

        elif response["status"] == "failure":
            if response["errorCode"] == "E016":
                logger.error("Error")

                func_call.result = "Appointment already exists here, check the availabilities and book again"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="Appointment already exists here, check the availabilities and book again",
                    content_complete=True,
                    end_call=True,
                )
                return response, func_call
            else:
                logger.error("Error")
                func_call.result = "Unkwown Error Occured, Please Try Again Later"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="Double Error Occured, Please Try Again Later",
                    content_complete=True,
                    end_call=True,
                )
                return response, func_call

    async def update_booking_nookal(self, params: dict, func_call, request):
        params['patient_id']= await self.nookal.get_patient_id(params)
        params['appointment_id'] = await self.nookal.get_appointment_id(params)

        logger.info("Updating Appointment")

        response = await self.nookal.update_appointment_booking(params)
        logger.info(response)

        if response["status"] == "success":
            logger.info("Success")
            try:
                appointment_id = response["data"]["results"]["appointments"]["ID"]
                old_date = response["data"]["results"]["appointments"]["dateCreated"]
                new_date = params["data"]["results"]["appointments"]["appointmentDate"]
                response_text = f"""Rescheduled appointment successfully from {old_date}
                to {new_date} Appointment ID is {appointment_id},
                Please note it down somewhere for future use"""
            except:
                response_text = "Rescheduled Successfully"
            func_call.result = response_text
            # print("Response Success")
            response = CustomLlmResponse(
                response_id=request.response_id,
                content=response_text,
                content_complete=True,
                end_call=False,
            )
            return response, func_call

        elif response["status"] == "failure":
            if response["errorCode"] == "E016":
                logger.error("Error")

                func_call.result = "Appointment already exists here, check the availabilities and book again"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="Appointment already exists here, check the availabilities and book again",
                    content_complete=True,
                    end_call=True,
                )
                return response, func_call
            else:
                logger.error("Error")
                func_call.result = "Unkwown Error Occured, Please Try Again Later"
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="Double Error Occured, Please Try Again Later",
                    content_complete=True,
                    end_call=True,
                )
                return response, func_call

    def draft_begin_message(self):
        response = CustomLlmResponse(
            response_id=0,
            content=BEGIN_SENTENCE,
            content_complete=True,
            end_call=False,
        )
        return response

    def prepare_prompt(self, request: CustomLlmRequest, func_result: FunctionCall):
        # if its an outbound reschedule agent
        current_datetime = datetime.now()

        # To get the name of the day
        day_of_week_name = current_datetime.strftime("%A")

        if self.agent_type == "RESCHEDULE":
            prompt = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT + RESCHEDULE_CLINIKO_AGENT_PROMPT,
                },
                {
                    "role": "system",
                    "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()} ",
                },
                {
                    "role": "system",
                    "content": f"""Appointment ID and Original Appointment Date are known,
                    appointment_id={self.metadata["appointment_id"]} and original_appointment_date={self.metadata["date"]}""",
                },
                {
                    "role": "assistant",
                    "content": self.select_begin_message(),
                },
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

    def convert_transcript_to_openai_messages(self, transcript: List[Utterance]):
        messages = []
        for utterance in transcript:
            role = "assistant" if utterance["role"] == "agent" else "user"
            messages.append({"role": role, "content": utterance["content"]})
        return messages

    def initialize_functions(self):
        functions = [
            nookal_function_calls_schema.end_call_function_schema,
            nookal_function_calls_schema.book_nookal_appointment_schema,
            nookal_function_calls_schema.add_patient_schema,
            nookal_function_calls_schema.search_patient_schema,
            nookal_function_calls_schema.reschedule_appointment_schema,
            nookal_function_calls_schema.cancel_appointment_schema,
            
        ]
        return functions

    async def draft_response(self, request, func_result: FunctionCall = None):
        try:
            models = ["gpt-4-turbo", "gpt-3.5-turbo-0125", "gpt-4o"]
            prompt = self.prepare_prompt(request, func_result)
            func_call: FunctionCall = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                model=models[1],
                messages=prompt,
                stream=True,
                tools=self.initialize_functions(),
                tool_choice="auto",
            )

            for chunk in stream:
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
                    )
                    yield response

            if func_call is not None:
                logger.info(f"In Function Call {func_call.func_name}")
                print(f"In Function Call {func_call.func_name}")
                
                if func_call.func_name == "end_call":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                elif func_call.func_name == "book_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Booking your appointment..",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = await self.book_with_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_call)

                elif func_call.func_name == "add_patient":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content= "Adding new patient...",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = await self.add_patient(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)

                elif func_call.func_name == "reschedule_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content= "Rescheduling appointment...",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = await self.update_booking_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)

                elif func_call.func_name == "cancel_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Cancelling your appointment",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = await self.cancel_appointment(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)

                # elif func_call.func_name == "check_appointment_availability":
                #     response = CustomLlmResponse(
                #         response_id=request.response_id,
                #         content=func_call.arguments["message"],
                #         content_complete=False,
                #         end_call=False,
                #     )
                #     yield response
                #     resp, func_call = self.check_availability_with_nookal(
                #         func_call.arguments, func_call, request
                #     )
                #     yield resp
                #     self.draft_response(request, func_result)

                elif func_call.func_name == "search_patient":
                    func_call.arguments = json.loads(func_arguments)
                    
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Searching Patients",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    
                    resp, func_call = await self.search_patient_with_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)

        except Exception as e:
            logger.error(e)
            print(e)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="There was an error, please call again",
                content_complete=True,
                end_call=True,
            )
            yield response
