import json
from pprint import pprint
from typing import List
from openai import OpenAI
from urllib import parse
import os

import requests
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
    RESCHEDULE_AGENT_PROMPT,
    NOOKAL_BASE_URL,
)


class LlmClient:
    def __init__(self, agent_type="BOOKING", metadata=None):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
        )
        self.agent_type = agent_type
        self.nookal = NookalClient()
        self.metadata = metadata

    def nookal_check_appointment_availibility(self, params: dict, func_call, request):
        params["location_id"] = 1
        params["practitioner_id"] = 1
        params["appointment_type_id"] = 4
        # params.pop("message")
        params.pop("message", None)

        logger.info("Check Appointment Availibility")
        response = self.nookal.check_appointment_availability(
            params["location_id"],
            params["practitioner_id"],
            params["date_from"],
            params["date_from"],
        )
        if response["status"] == "success":
            response_text = f"""Checking availibility"""
            func_call.result = response
            # print("Response Success")
            # response = CustomLlmResponse(
            #     response_id=request.response_id,
            #     content=response_text,
            #     content_complete=True,
            #     end_call=False,
            # )
            # return response, func_call
            return func_call

        else:
            logger.error("Error")
            func_call.result = (
                "Error ocurred while checking availibility, Please Try Again Later"
            )
            # response = CustomLlmResponse(
            #     response_id=request.response_id,
            #     content="Double Error Occured, Please Try Again Later",
            #     content_complete=True,
            #     end_call=True,
            # )
            # return response, func_call
            return func_call

    def book_with_nookal(self, params: dict, func_call, request):
        params["location_id"] = 1
        params["practitioner_id"] = 1
        params["appointment_type_id"] = 4
        # params.pop("message")
        params.pop("message", None)

        logger.info("Booking APpointment")
        response = self.nookal.add_appointment_booking(params)
        logger.info(response)
        if response["status"] == "success":
            logger.info("Success")
            appointment_id = response["data"]["results"]["appointment_id"]
            case_id = response["data"]["results"]["case_id"]
            response_text = f"""Appointment booked successfully for Patient ID
            {params['patient_id']} Appointment ID is {appointment_id} Case ID is {case_id},
            Please note it down somewhere for future use"""
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

    def update_booking_nookal(self, params: dict, func_call, request):
        # params.pop("message")
        logger.info("Updating APpointment")

        params.pop("message", None)

        response = self.nookal.update_appointment_booking(params)
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

    def select_begin_message(self):
        if self.agent_type == "RESCHEDULE":
            return f"""Hi this is Julie speaking from Melbourne Foot and Ankle Clinic.
            Unfortunately, {self.metadata['dr']} has cancelled the appointment due to {self.metadata['reason']}
            and I need to reschedule your appointment.
            When are you available to come in again?"""
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
        day_of_week_name = current_datetime.strftime("%A")

        if self.agent_type == "RESCHEDULE":
            prompt = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT + RESCHEDULE_AGENT_PROMPT,
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

    def initialize_functions(self):
        functions = [
            # function_calls_schema.check_appointment_availability_schema,
            nookal_function_calls_schema.book_nookal_appointment_schema,
            nookal_function_calls_schema.reschedule_appointment_schema,
            nookal_function_calls_schema.end_call_function_schema,
        ]
        return functions

    def initialize_outbound_functions(self):
        functions = [
            nookal_function_calls_schema.end_call_function_schema,
            nookal_function_calls_schema.reschedule_appointment_schema,
        ]
        return functions

    def draft_outbound_response(self, request, func_result: FunctionCall = None):
        try:
            logger.info(request)
            prompt = self.prepare_prompt(request, func_result)
            pprint(prompt)

            # func_call = {}
            func_call: FunctionCall = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                # model="gpt-3.5-turbo-1106",
                # model="gpt-4-turbo",
                model="gpt-4o",
                messages=prompt,
                stream=True,
                # Step 2: Add the function into your request
                tools=self.initialize_outbound_functions(),
                tool_choice="auto",
            )
            # print(prompt)
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
                    logger.info("End Call Function")
                    logger.info(f"{chunk.choices[0]}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                # Step 5: Other functions here
                if func_call.func_name == "reschedule_appointment":
                    # parse arguments
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Rescheduling your appointment",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    logger.info(f"Making function call {func_call.arguments}")
                    resp, func_call = self.update_booking_nookal(
                        func_call.arguments, func_call, request
                    )
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
            # print(e)
            logger.error(e)
            print(e)
            response = CustomLlmResponse(
                response_id=request.response_id,
                content="There was an error, please call again",
                content_complete=True,
                end_call=True,
            )
            yield response

    def draft_response(self, request, func_result: FunctionCall = None):
        try:
            prompt = self.prepare_prompt(request, func_result)
            # func_call = {}
            func_call: FunctionCall = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                # model="gpt-3.5-turbo-1106",
                # model="gpt-4-turbo",
                model="gpt-4o",
                messages=prompt,
                stream=True,
                # Step 2: Add the function into your request
                tools=self.initialize_functions(),
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
                    logger.info("End Call Function")
                    logger.info(f"{chunk.choices[0]}")
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                # # Step 5: Other functions here
                # if func_call.func_name == "check_appointment_availability":
                #     # parse arguments
                #     func_call.arguments = json.loads(func_arguments)
                #     response = CustomLlmResponse(
                #         response_id=request.response_id,
                #         content=func_call.arguments["message"],
                #         content_complete=False,
                #         end_call=False,
                #     )
                #     yield response
                #     logger.info(f"Making function call {func_call.arguments}")
                #     func_result = self.book_with_nookal(
                #         func_call.arguments, func_call, request
                #     )
                #     logger.info(f"{func_result}")
                #     yield resp
                #     self.draft_response(request, func_result)

                if func_call.func_name == "book_appointment":
                    # parse arguments
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    logger.info(f"Making function call {func_call.arguments}")
                    resp, func_call = self.book_with_nookal(
                        func_call.arguments, func_call, request
                    )
                    logger.info(f"{resp}")
                    yield resp
                    self.draft_response(request, func_result)

                if func_call.func_name == "reschedule_appointment":
                    # parse arguments
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Rescheduling your appointment",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    logger.info(f"Making function call {func_call.arguments}")
                    resp, func_call = self.update_booking_nookal(
                        func_call.arguments, func_call, request
                    )
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
