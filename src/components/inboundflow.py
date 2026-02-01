import json
from pprint import pprint
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
from src.components import function_calls_schema
from src.components.nookal.nookal_client import NookalClient
from datetime import datetime
from src.constants import (
    BEGIN_SENTENCE,
    SYSTEM_PROMPT,
    AGENT_PROMPT,
    RESCHEDULE_AGENT_PROMPT,
)


class LlmClient:
    def __init__(self, agent_type="BOOKING", metadata=None):
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
        )
        self.agent_type = agent_type
        self.nookal = NookalClient()
        self.metadata = metadata

    import json
import requests
from urllib import parse
from pprint import pprint
import logging

# Define API keys for Nookal and OpenAI APIs
api_key = os.getenv("NOOKAL_API_KEY", "")
api_key_ai = os.getenv("OPENAI_API_KEY", "")

# Base URL for the Nookal API
nookal_base_url = "https://api.nookal.com/production/v2/"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Define data classes for responses
class CustomLlmResponse:
    def __init__(self, response_id, content, content_complete=False, end_call=False):
        self.response_id = response_id
        self.content = content
        self.content_complete = content_complete
        self.end_call = end_call

class FunctionCall:
    def __init__(self, id, func_name, arguments):
        self.id = id
        self.func_name = func_name
        self.arguments = arguments

# Define a function to add a new patient
def add_patient(first_name, last_name, date_of_birth):
    params = {
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "api_key": api_key,
    }
    params = parse.urlencode(params)
    url = f"{nookal_base_url}addPatient?{params}"
    response = requests.get(url)
    return response.json()

# Define a function to check appointment availability
def check_appointment_availability(location_id, practitioner_id, date_from, date_to):
    params = {
        "location_id": location_id,
        "practitioner_id": practitioner_id,
        "date_from": date_from,
        "date_to": date_to,
        "api_key": api_key,
    }
    params = parse.urlencode(params)
    url = f"{nookal_base_url}getAppointmentAvailabilities?{params}"
    response = requests.get(url)
    return response.json()

# Define a function to book an appointment
def book_appointment(location_id, appointment_date, start_time, patient_id, practitioner_id, appointment_type_id):
    data = {
        "location_id": location_id,
        "appointment_date": appointment_date,
        "start_time": start_time,
        "patient_id": patient_id,
        "practitioner_id": practitioner_id,
        "appointment_type_id": appointment_type_id,
        "api_key": api_key,
    }
    params = parse.urlencode(data)
    try:
        resp = requests.request(
            "GET",
            f"{nookal_base_url}addAppointmentBooking?{params}",
        )
        data = resp.content.decode("utf-8")  # Decode byte string to a regular string
        json_data = json.loads(data)  # Convert JSON string to a Python dictionary
        return json_data
    except Exception as err:
        print(f"Error in Nookal API: {err}")
        return None

# Define a function to search for a patient
def search_patient(patient_id=None, email=None, first_name=None, last_name=None, date_of_birth=None):
    url = f"{nookal_base_url}searchPatients"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    params = {
        "patient_id": patient_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

# Define a function to manage an appointment (confirm, reschedule, or cancel)
def manage_appointment(appointment_id, status, patient_id=None, location_id=None, appointment_date=None, start_time=None, practitioner_id=None, appointment_type_id=None):
    if status == "reschedule":
        url = f"{nookal_base_url}updateAppointmentBooking"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "appointment_id": appointment_id,
            "location_id": location_id,
            "appointment_date": appointment_date,
            "start_time": start_time,
            "status": status,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "appointment_type_id": appointment_type_id,
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()
    elif status == "cancel":
        url = f"{nookal_base_url}cancelAppointment"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()
    else:
        return {"error": "Invalid appointment status"}

# Define the LlmClient class
class LlmClient:
    def __init__(self, client):
        self.client = client
        self.api_key_ai = api_key_ai
        self.api_key = api_key
        self.metadata = {}

    def prepare_prompt(self, request, func_result=None):
        prompt = [{"role": "system", "content": "You are an appointment booking assistant."}]
        if func_result:
            prompt.append({"role": "assistant", "content": func_result})
        prompt.append({"role": "user", "content": request.content})
        return prompt

    def initialize_functions(self):
        return [self.book_with_nookal, self.update_booking_nookal]

    def initialize_outbound_functions(self):
        functions = [function_calls_schema.end_call_function_schema, function_calls_schema.reschedule_appointment_schema]
        return functions

    def book_with_nookal(self, arguments, func_call, request):
        response = book_appointment(
            arguments["location_id"],
            arguments["appointment_date"],
            arguments["start_time"],
            arguments["patient_id"],
            arguments["practitioner_id"],
            arguments["appointment_type_id"]
        )
        return CustomLlmResponse(response_id=request.response_id, content=str(response)), func_call

    def update_booking_nookal(self, arguments, func_call, request):
        response = manage_appointment(
            arguments["appointment_id"],
            status="reschedule",
            location_id=arguments["location_id"],
            appointment_date=arguments["appointment_date"],
            start_time=arguments["start_time"],
            patient_id=arguments["patient_id"],
            practitioner_id=arguments["practitioner_id"],
            appointment_type_id=arguments["appointment_type_id"]
        )
        return CustomLlmResponse(response_id=request.response_id, content=str(response)), func_call

    def draft_outbound_response(self, request, func_result=None):
        try:
            logger.info(request)
            prompt = self.prepare_prompt(request, func_result)
            pprint(prompt)
            
            func_call = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                model="gpt-4o",
                messages=prompt,
                stream=True,
                tools=self.initialize_outbound_functions(),
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
                logger.info(f"In Function Call {func_call.func_name}" )
                if func_call.func_name == "end_call":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                if func_call.func_name == "reschedule_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Rescheduling your appointment",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = self.update_booking_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)
            else:
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="",
                    content_complete=True,
                    end_call=True)
                yield response
        except Exception as e:
            print(e)

    def select_begin_message(self):
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
        current_datetime = datetime.now()
        day_of_week_name = current_datetime.strftime('%A')

        if self.agent_type == "RESCHEDULE":
            prompt = [
                {"role": "system", "content": SYSTEM_PROMPT + RESCHEDULE_AGENT_PROMPT},
                {"role": "system", "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()} "},
                {"role": "system", "content": f"""Appointment ID and Original Appointment Date are known,
                appointment_id={self.metadata["appointment_id"]} and original_appointment_date={self.metadata["date"]}"""},
                {"role": "assistant", "content": self.select_begin_message()},
            ]
        else:
            prompt = [
                {"role": "system", "content": SYSTEM_PROMPT + AGENT_PROMPT},
                {"role": "system", "content": f"Todays Datetime {day_of_week_name} {current_datetime.isoformat()} "},
            ]
        transcript_messages = self.convert_transcript_to_openai_messages(request.transcript)
        for message in transcript_messages:
            prompt.append(message)

        if func_result is not None:
            prompt.append(
                {"role": "assistant", "content": None, "toolCalls": [
                    {"id": func_result.id, "type": "function", "function": {
                        "name": func_result.func_name, "arguments": str(func_result.arguments)}
                    }
                ]}
            )
            prompt.append(
                {"role": "tool", "toolCallId": func_result.id, "content": func_result.result}
            )

        if request.interaction_type == "reminder_required":
            prompt.append(
                {"role": "user", "content": "(Now the user has not responded in a while, you would say:)"}
            )
        return prompt

    def initialize_functions(self):
        functions = [function_calls_schema.end_call_function_schema, function_calls_schema.book_nookal_appointment_schema]
        return functions

    def initialize_outbound_functions(self):
        functions = [function_calls_schema.end_call_function_schema, function_calls_schema.reschedule_appointment_schema]
        return functions

    def draft_outbound_response(self, request, func_result: FunctionCall = None):
        try:
            logger.info(request)
            prompt = self.prepare_prompt(request, func_result)
            pprint(prompt)
            
            func_call: FunctionCall = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                model="gpt-4o",
                messages=prompt,
                stream=True,
                tools=self.initialize_outbound_functions(),
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
                logger.info(f"In Function Call {func_call.func_name}" )
                if func_call.func_name == "end_call":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                if func_call.func_name == "reschedule_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content="Rescheduling your appointment",
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = self.update_booking_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)
            else:
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="",
                    content_complete=True,
                    end_call=False,
                )
                yield response
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

    def draft_response(self, request, func_result: FunctionCall = None):
        try:
            prompt = self.prepare_prompt(request, func_result)
            func_call: FunctionCall = None
            func_arguments = ""
            stream = self.client.chat.completions.create(
                model="gpt-4o",
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
                if func_call.func_name == "end_call":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=True,
                        end_call=True,
                    )
                    yield response
                if func_call.func_name == "book_appointment":
                    func_call.arguments = json.loads(func_arguments)
                    response = CustomLlmResponse(
                        response_id=request.response_id,
                        content=func_call.arguments["message"],
                        content_complete=False,
                        end_call=False,
                    )
                    yield response
                    resp, func_call = self.book_with_nookal(
                        func_call.arguments, func_call, request
                    )
                    yield resp
                    self.draft_response(request, func_result)
            else:
                response = CustomLlmResponse(
                    response_id=request.response_id,
                    content="",
                    content_complete=True,
                    end_call=False,
                )
                yield response
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

