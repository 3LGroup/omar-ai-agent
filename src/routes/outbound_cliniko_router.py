import asyncio
import json
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from src.logger import logger
from src.components.cliniko.outbound_llm import OutboundLLMCliniko
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
from src import twilio_client, retell
from src.schemas.Outbound_Cliniko_Request import (
    OutboundRescheduleRequest,
    OutboundPatientReviewRequest,
    OutboundAppointmentConfirmationRequest,
    OutboundPatientOutreachRequest,
    OutboundSMSAppointmentConfirmation
)
import time
from src.utils.calculate_credits_used import update_total_cost
from src.utils.session_vars import user_data
from src.db.db import DB
from datetime import datetime
from src.components.cliniko.cliniko_client import ClinikoClient
from src.components.cliniko.utils import subtract_hours_from_time, add_hours_to_time


# main router
router = APIRouter(prefix="/cliniko/outbound")

@router.get('/test')
def test():
    return 'test'


@router.post("/reschedule")
async def call_outbound(params: OutboundRescheduleRequest):
    try:
        call = twilio_client.create_phone_call_cliniko(
            # cliniko outbound
            from_number = params.phone_number_from,
            to_number = params.phone_number_to,
            agent_id = params.agent_id,
            dr = params.doctor_name,
            reason = params.message,
            agent_type = "RESCHEDULE",
            first_name=params.first_name,
            last_name=params.last_name,
            date_of_birth=params.date_of_birth,
            old_start_date = params.old_start_date,
            old_end_date = params.old_end_date,
            crm = "cliniko",
        )

        print(f"Call outbound params: {params}")
        return JSONResponse(
            content={"message": "Successful in Outbound Call", "call_id": call.sid},
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Error creating phone call {e}")
        return JSONResponse(
            content={"message": "Failed to Connect", "error": str(e)}, status_code=404
        )

@router.post('/patient-review')
async def patient_review(params: OutboundPatientReviewRequest):
    try:
        call = twilio_client.create_phone_call_cliniko_patient_review(
            from_number = params.phone_number_from,
            to_number = params.phone_number_to,
            agent_id = params.agent_id,
            dr = params.doctor_name,
            reason = params.message,
            agent_type = "PATIENT_REVIEW",
            first_name = params.first_name,
            last_name = params.last_name,
            appointment_date = params.appointment_date,
            checkup = params.checkup,
            review = params.review,
            crm = "cliniko",
        )

        print(f"Call outbound params: {params}")
        return JSONResponse(content={"message": "Successful in Patient Review", "call_id": call.sid}, status_code=200)


    except Exception as e:
        logger.error(f"Error creating phone call {e}")
        return JSONResponse(content={"message": "Failed to Connect", "error": str(e)}, status_code=404)

@router.post('/appointment-confirmation')
async def appointment_confirmation(params: OutboundAppointmentConfirmationRequest):
    client = ClinikoClient()

    try:
        appointment_date = params.appointment_date # 2024-08-26T00:00:00Z

        start_time = subtract_hours_from_time(appointment_date, 10)
        end_time = add_hours_to_time(appointment_date, 24)

        all_appointments, status = await client.list_bookings({
            "q": [
                f"starts_at:<={end_time}",
                f"ends_at:>={start_time}"
            ]})
        

        for appointment in all_appointments['bookings']:
            patient_data_url = appointment['patient']['links']['self']

            patient_data = await client.get_patient_by_url(patient_data_url)

            patient_phone_number = patient_data['patient_phone_numbers'][0]['number']

            call = twilio_client.create_call_cliniko_appointment_confirmation(
                from_number = params.phone_number_from,
                to_number = params.phone_number_to,
                agent_id = params.agent_id,
                dr = params.doctor_name,
                reason = params.reason,
                agent_type = "APPOINTMENT_CONFIRMATION",
                first_name = patient_data['first_name'],
                last_name = patient_data['last_name'],
                date_of_birth = patient_data['date_of_birth'],
                appointment_date = appointment['starts_at'],
                crm = "cliniko",
            )
            print('Patient phone number: ', '+92' + patient_phone_number[1:])
            print('Call data: ', call.sid)
            print(f"Call outbound params: {params}")

        return JSONResponse(content={"message": "Successful in Appoint confirmation", "Appointments": all_appointments}, status_code=200)

    except Exception as e:
        logger.error(f"Error creating phone call {e}")
        return JSONResponse(content={"message": "Something went wrong", "error": str(e)}, status_code=500)

@router.post('/patient-outreach')
async def patient_outreach(params: OutboundPatientOutreachRequest):
    try:
        call = twilio_client.create_phone_call_cliniko_patient_outreach(
            # cliniko outbound
            from_number = params.phone_number_from,
            to_number = params.phone_number_to,
            agent_id = params.agent_id,
            dr = params.doctor_name,
            reason = params.message,
            agent_type = "PATIENT_OUTREACH",
            first_name=params.first_name,
            last_name=params.last_name,
            date_of_birth=params.date_of_birth,
            old_start_date = params.appointment_date,
            crm = "cliniko",
        )

        print(f"Call outbound params: {params}")
        return JSONResponse(
            content={"message": "Successful in Outbound Call", "call_id": call.sid},
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Error creating phone call {e}")
        return JSONResponse(
            content={"message": "Failed to Connect", "error": str(e)}, status_code=404
        )

@router.post('/appointment-confirmation-sms')
async def send_confirmation_sms(params: OutboundSMSAppointmentConfirmation):
    try:
        variable_params = {
            "outbound_type" : params.outbound_type,
            "appointment_id" : params.appointment_id
        }
        message = twilio_client.send_message(
            from_number= params.phone_number_from,   
            to_number = params.phone_number_to,
            message_body = params.message,
            params = variable_params
        )
        print(f"Confirmation Message outbound params: {params}")
        return JSONResponse(
            content={"message": "Successful in Outbound SMS", "sms_id": message.sid},
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Error creating phone call {e}")
        return JSONResponse(
            content={"message": "Failed to Connect", "error": str(e)}, status_code=404
        )

# Custom Webhook to Handle incoming messages from Twilio and respond as needed depending on the message 
@router.post('/handle-incoming-messages')
async def handle_incoming_messages(request: Request):
    try:
        print("INSIDE HANDLE INCOMING MESSAGES")
        print("Request BODY" , request.body)
        request_body = await request.json()
        print("RequestJSON BODY" , request_body)
        twilio_client.handle_incoming_messages(request_body)
        return JSONResponse(content={"message": "Message handled successfully"}, status_code=200)
    except Exception as e:
        logger.error(f"Error handling incoming messages {e}")
        return JSONResponse(content={"message": "Failed to handle incoming messages", "error": str(e)}, status_code=404)

# Custom LLM Websocket handler, receive audio transcription and send back
#  text response
@router.websocket("/reschedule/{call_id}")
async def websocket_handler(
    websocket: WebSocket,
    call_id: str,
):
    await websocket.accept()
    logger.info("Outbound::LLM")

    call_details = retell.call.retrieve(call_id)
    metadata = call_details.metadata

    print(f"call_details: {call_details}")
    print(f"metadata: {metadata}")

    call_start_timestamp = time.time()

    # Send optional config to Retell server
    config = CustomLlmResponse(
        response_type="config",
        config={
            "auto_reconnect": True,
            "call_details": True,
        },
        response_id=1,
    )
    await websocket.send_text(json.dumps(config.__dict__))

    llm_client = OutboundLLMCliniko(
            metadata=metadata,
            agent_type="RESCHEDULE",
        )
    
    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        print("In Stream Response")
        nonlocal response_id
        #  TODO : BUG
        async for event in llm_client.draft_response(request):
            await websocket.send_text(json.dumps(event.__dict__))
            await asyncio.sleep(0.005)
            if request.response_id < response_id:
                return  # new response needed, abandon this one
            
    try:
        while True:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=100 * 60
            )  # 100 minutes
            # await asyncio.sleep(0)
            request_json = json.loads(message)
            request: CustomLlmRequest = CustomLlmRequest(**request_json)
            # logger.info(json.dumps(request.__dict__, indent=4))
            # print(json.dumps(request.__dict__, indent=4))

            # There are 5 types of interaction_type: call_details, pingpong, update_only, response_required, and reminder_required.
            # Not all of them need to be handled, only response_required and reminder_required.
            if request.interaction_type == "call_details":
                continue
            if request.interaction_type == "ping_pong":
                await websocket.send_text(
                    json.dumps(
                        {"response_type": "ping_pong", "timestamp": request.timestamp}
                    )
                )
                continue
            if request.interaction_type == "update_only":
                continue
            if (
                request.interaction_type == "response_required"
                or request.interaction_type == "reminder_required"
            ):
                response_id = request.response_id
                print(
                    f"""Received interaction_type={request_json['interaction_type']}, response_id={response_id}, last_transcript={request_json['transcript'][-1]['content']}"""
                )

                asyncio.create_task(stream_response(request))

    except WebSocketDisconnect as e:
        print(f"LLM WebSocket disconnected for {call_id} due to {e}")
        logger.error(f"LLM WebSocket disconnected for {call_id}")
    except Exception as e:
        print(f"Error in LLM WebSocket: {e}")
        logger.error(f"Error in LLM WebSocket: {e}")
    finally:
        call_end_timestamp = time.time()
        db = DB()

        start_time = datetime.fromtimestamp(call_start_timestamp)
        end_time = datetime.fromtimestamp(call_end_timestamp)

        call_info = retell.call.retrieve(call_id)

        # Get call info from retell 
        transcript = call_info.transcript
        agent_id= call_info.agent_id
        recording_url= call_info.recording_url
        disconnection_reason= call_info.disconnection_reason
        summary = call_info.call_analysis.call_summary
        user_sentiment =call_info.call_analysis.user_sentiment
        call_successful= call_info.call_analysis.call_successful
        seconds= call_info.call_cost.total_duration_seconds

        #calculating cost per call
        minutes, seconds = divmod(seconds, 60)
        full_minute_credits = minutes
        partial_minute_credits = seconds / 60  # This gives a fraction of a credit for partial minutes
        call_time = full_minute_credits + partial_minute_credits

        # Round to 3 decimal places for clarity
        cost_per_call = round(call_time * 0.15, 3)

        # Get user data
        admin_data = db.get_user_by_agent_id(agent_id)

        # Write call info to Firestore
        doc = db.write_to_firestore(
            "calls_tracking", 
            {
                "admin_id": len(admin_data) > 0 and admin_data[0]["id"] or "",
                "call_id": call_id, 
                "agent_id": agent_id,
                "call_type": user_data['call_type'],
                "success": user_data['success'],
                "duration": (end_time - start_time).total_seconds(),
                "patient_dob": user_data["patient_dob"],
                "patient_id": user_data["patient_id"],
                "patient_name": user_data["patient_name"],
                "patient_number": user_data["patient_number"],
                "time": start_time,
                "recording_url": recording_url,
                "disconnection_reason": disconnection_reason,
                "user_sentiment": user_sentiment,
                "call_successful": call_successful,
                "cost_per_call": cost_per_call,
                "summary": summary,
                "transcript": transcript
            }
        )

        # Update total cost per client
        await update_total_cost(cost_per_call, call_time, agent_id)
        print(f"LLM WebSocket connection closed for {call_id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")

@router.websocket("/patient-review/{call_id}")
async def websocket_handler(
    websocket: WebSocket,
    call_id: str,
):
    await websocket.accept()
    logger.info("Outbound::LLM")

    call_details = retell.call.retrieve(call_id)
    metadata = call_details.metadata

    print(f"call_details: {call_details}")
    print(f"metadata: {metadata}")

    call_start_timestamp = time.time()

    # Send optional config to Retell server
    config = CustomLlmResponse(
        response_type="config",
        config={
            "auto_reconnect": True,
            "call_details": True,
        },
        response_id=1,
    )
    await websocket.send_text(json.dumps(config.__dict__))
    
    llm_client = OutboundLLMCliniko(
        metadata=metadata,
        agent_type="PATIENT_REVIEW",
    )


    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        print("In Stream Response")
        nonlocal response_id
        #  TODO : BUG
        async for event in llm_client.draft_response(request):
            await websocket.send_text(json.dumps(event.__dict__))
            await asyncio.sleep(0.005)
            if request.response_id < response_id:
                return  # new response needed, abandon this one
            
    try:
        while True:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=100 * 60
            )  # 100 minutes
            # await asyncio.sleep(0)
            request_json = json.loads(message)
            request: CustomLlmRequest = CustomLlmRequest(**request_json)
            # logger.info(json.dumps(request.__dict__, indent=4))
            # print(json.dumps(request.__dict__, indent=4))

            # There are 5 types of interaction_type: call_details, pingpong, update_only, response_required, and reminder_required.
            # Not all of them need to be handled, only response_required and reminder_required.
            if request.interaction_type == "call_details":
                continue
            if request.interaction_type == "ping_pong":
                await websocket.send_text(
                    json.dumps(
                        {"response_type": "ping_pong", "timestamp": request.timestamp}
                    )
                )
                continue
            if request.interaction_type == "update_only":
                continue
            if (
                request.interaction_type == "response_required"
                or request.interaction_type == "reminder_required"
            ):
                response_id = request.response_id
                print(
                    f"""Received interaction_type={request_json['interaction_type']}, response_id={response_id}, last_transcript={request_json['transcript'][-1]['content']}"""
                )

                asyncio.create_task(stream_response(request))

    except WebSocketDisconnect as e:
        print(f"LLM WebSocket disconnected for {call_id} due to {e}")
        logger.error(f"LLM WebSocket disconnected for {call_id}")
    except Exception as e:
        print(f"Error in LLM WebSocket: {e}")
        logger.error(f"Error in LLM WebSocket: {e}")
    finally:
        call_end_timestamp = time.time()
        db = DB()

        start_time = datetime.fromtimestamp(call_start_timestamp)
        end_time = datetime.fromtimestamp(call_end_timestamp)

        call_info = retell.call.retrieve(call_id)

        # Get call info from retell 
        transcript = call_info.transcript
        agent_id= call_info.agent_id
        recording_url= call_info.recording_url
        disconnection_reason= call_info.disconnection_reason
        summary = call_info.call_analysis.call_summary
        user_sentiment =call_info.call_analysis.user_sentiment
        call_successful= call_info.call_analysis.call_successful
        seconds= call_info.call_cost.total_duration_seconds

        #calculating cost per call
        minutes, seconds = divmod(seconds, 60)
        full_minute_credits = minutes
        partial_minute_credits = seconds / 60  # This gives a fraction of a credit for partial minutes
        call_time = full_minute_credits + partial_minute_credits

        # Round to 3 decimal places for clarity
        cost_per_call = round(call_time * 0.15, 3)

        # Get user data
        admin_data = db.get_user_by_agent_id(agent_id)

        # Write call info to Firestore
        doc = db.write_to_firestore(
            "calls_tracking", 
            {
                "admin_id": len(admin_data) > 0 and admin_data[0]["id"] or "",
                "call_id": call_id, 
                "agent_id": agent_id,
                "call_type": user_data['call_type'],
                "success": user_data['success'],
                "duration": (end_time - start_time).total_seconds(),
                "patient_dob": user_data["patient_dob"],
                "patient_id": user_data["patient_id"],
                "patient_name": user_data["patient_name"],
                "patient_number": user_data["patient_number"],
                "time": start_time,
                "recording_url": recording_url,
                "disconnection_reason": disconnection_reason,
                "user_sentiment": user_sentiment,
                "call_successful": call_successful,
                "cost_per_call": cost_per_call,
                "summary": summary,
                "transcript": transcript
            }
        )

        # Update total cost per client
        await update_total_cost(cost_per_call, call_time, agent_id)

        print(f"LLM WebSocket connection closed for {call_id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")

@router.websocket("/appointment-confirmation/{call_id}")
async def websocket_handler(
    websocket: WebSocket,
    call_id: str,
):
    await websocket.accept()
    logger.info("Outbound::LLM")

    call_details = retell.call.retrieve(call_id)
    metadata = call_details.metadata

    print(f"call_details: {call_details}")
    print(f"metadata: {metadata}")

    call_start_timestamp = time.time()

    # Send optional config to Retell server
    config = CustomLlmResponse(
        response_type="config",
        config={
            "auto_reconnect": True,
            "call_details": True,
        },
        response_id=1,
    )
    await websocket.send_text(json.dumps(config.__dict__))
    
    llm_client = OutboundLLMCliniko(
        metadata=metadata,
        agent_type="APPOINTMENT_CONFIRMATION",
    )

    print(f"llm_client.agent_type: {llm_client.agent_type}")


    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        print("In Stream Response")
        nonlocal response_id
        #  TODO : BUG
        async for event in llm_client.draft_response(request):
            await websocket.send_text(json.dumps(event.__dict__))
            await asyncio.sleep(0.005)
            if request.response_id < response_id:
                return  # new response needed, abandon this one
            
    try:
        while True:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=100 * 60
            )  # 100 minutes
            # await asyncio.sleep(0)
            request_json = json.loads(message)
            request: CustomLlmRequest = CustomLlmRequest(**request_json)
            # logger.info(json.dumps(request.__dict__, indent=4))
            # print(json.dumps(request.__dict__, indent=4))

            # There are 5 types of interaction_type: call_details, pingpong, update_only, response_required, and reminder_required.
            # Not all of them need to be handled, only response_required and reminder_required.
            if request.interaction_type == "call_details":
                continue
            if request.interaction_type == "ping_pong":
                await websocket.send_text(
                    json.dumps(
                        {"response_type": "ping_pong", "timestamp": request.timestamp}
                    )
                )
                continue
            if request.interaction_type == "update_only":
                continue
            if (
                request.interaction_type == "response_required"
                or request.interaction_type == "reminder_required"
            ):
                response_id = request.response_id
                print(
                    f"""Received interaction_type={request_json['interaction_type']}, response_id={response_id}, last_transcript={request_json['transcript'][-1]['content']}"""
                )

                asyncio.create_task(stream_response(request))

    except WebSocketDisconnect as e:
        print(f"LLM WebSocket disconnected for {call_id} due to {e}")
        logger.error(f"LLM WebSocket disconnected for {call_id}")
    except Exception as e:
        print(f"Error in LLM WebSocket: {e}")
        logger.error(f"Error in LLM WebSocket: {e}")
    finally:
        call_end_timestamp = time.time()
        db = DB()

        start_time = datetime.fromtimestamp(call_start_timestamp)
        end_time = datetime.fromtimestamp(call_end_timestamp)

        call_info = retell.call.retrieve(call_id)

        # Get call info from retell 
        transcript = call_info.transcript
        agent_id= call_info.agent_id
        recording_url= call_info.recording_url
        disconnection_reason= call_info.disconnection_reason
        summary = call_info.call_analysis.call_summary
        user_sentiment =call_info.call_analysis.user_sentiment
        call_successful= call_info.call_analysis.call_successful
        seconds= call_info.call_cost.total_duration_seconds

        #calculating cost per call
        minutes, seconds = divmod(seconds, 60)
        full_minute_credits = minutes
        partial_minute_credits = seconds / 60  # This gives a fraction of a credit for partial minutes
        call_time = full_minute_credits + partial_minute_credits

        # Round to 3 decimal places for clarity
        cost_per_call = round(call_time * 0.15, 3)

        # Get user data
        admin_data = db.get_user_by_agent_id(agent_id)

        # Write call info to Firestore
        doc = db.write_to_firestore(
            "calls_tracking", 
            {
                "admin_id": len(admin_data) > 0 and admin_data[0]["id"] or "",
                "call_id": call_id, 
                "agent_id": agent_id,
                "call_type": user_data['call_type'],
                "success": user_data['success'],
                "duration": (end_time - start_time).total_seconds(),
                "patient_dob": user_data["patient_dob"],
                "patient_id": user_data["patient_id"],
                "patient_name": user_data["patient_name"],
                "patient_number": user_data["patient_number"],
                "time": start_time,
                "recording_url": recording_url,
                "disconnection_reason": disconnection_reason,
                "user_sentiment": user_sentiment,
                "call_successful": call_successful,
                "cost_per_call": cost_per_call,
                "summary": summary,
                "transcript": transcript
            }
        )

        # Update total cost per client
        await update_total_cost(cost_per_call, call_time, agent_id)

        print(f"LLM WebSocket connection closed for {call_id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")

@router.websocket("/patient-outreach/{call_id}")
async def websocket_handler(
    websocket: WebSocket,
    call_id: str,
):
    await websocket.accept()
    logger.info("Outbound::LLM")

    call_details = retell.call.retrieve(call_id)
    metadata = call_details.metadata

    print(f"call_details: {call_details}")
    print(f"metadata: {metadata}")

    call_start_timestamp = time.time()

    # Send optional config to Retell server
    config = CustomLlmResponse(
        response_type="config",
        config={
            "auto_reconnect": True,
            "call_details": True,
        },
        response_id=1,
    )
    await websocket.send_text(json.dumps(config.__dict__))
    
    llm_client = OutboundLLMCliniko(
        metadata=metadata,
        agent_type="PATIENT_OUTREACH",
    )

    print(f"llm_client.agent_type: {llm_client.agent_type}")


    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        print("In Stream Response")
        nonlocal response_id
        #  TODO : BUG
        async for event in llm_client.draft_response(request):
            await websocket.send_text(json.dumps(event.__dict__))
            await asyncio.sleep(0.005)
            if request.response_id < response_id:
                return  # new response needed, abandon this one
            
    try:
        while True:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=100 * 60
            )  # 100 minutes
            # await asyncio.sleep(0)
            request_json = json.loads(message)
            request: CustomLlmRequest = CustomLlmRequest(**request_json)
            # logger.info(json.dumps(request.__dict__, indent=4))
            # print(json.dumps(request.__dict__, indent=4))

            # There are 5 types of interaction_type: call_details, pingpong, update_only, response_required, and reminder_required.
            # Not all of them need to be handled, only response_required and reminder_required.
            if request.interaction_type == "call_details":
                continue
            if request.interaction_type == "ping_pong":
                await websocket.send_text(
                    json.dumps(
                        {"response_type": "ping_pong", "timestamp": request.timestamp}
                    )
                )
                continue
            if request.interaction_type == "update_only":
                continue
            if (
                request.interaction_type == "response_required"
                or request.interaction_type == "reminder_required"
            ):
                response_id = request.response_id
                print(
                    f"""Received interaction_type={request_json['interaction_type']}, response_id={response_id}, last_transcript={request_json['transcript'][-1]['content']}"""
                )

                asyncio.create_task(stream_response(request))

    except WebSocketDisconnect as e:
        print(f"LLM WebSocket disconnected for {call_id} due to {e}")
        logger.error(f"LLM WebSocket disconnected for {call_id}")
    except Exception as e:
        print(f"Error in LLM WebSocket: {e}")
        logger.error(f"Error in LLM WebSocket: {e}")
    finally:
        call_end_timestamp = time.time()
        db = DB()

        start_time = datetime.fromtimestamp(call_start_timestamp)
        end_time = datetime.fromtimestamp(call_end_timestamp)

        call_info = retell.call.retrieve(call_id)

        # Get call info from retell 
        transcript = call_info.transcript
        agent_id= call_info.agent_id
        recording_url= call_info.recording_url
        disconnection_reason= call_info.disconnection_reason
        summary = call_info.call_analysis.call_summary
        user_sentiment =call_info.call_analysis.user_sentiment
        call_successful= call_info.call_analysis.call_successful
        seconds= call_info.call_cost.total_duration_seconds

        #calculating cost per call
        minutes, seconds = divmod(seconds, 60)
        full_minute_credits = minutes
        partial_minute_credits = seconds / 60  # This gives a fraction of a credit for partial minutes
        call_time = full_minute_credits + partial_minute_credits

        # Round to 3 decimal places for clarity
        cost_per_call = round(call_time * 0.15, 3)

        # Get user data
        admin_data = db.get_user_by_agent_id(agent_id)

        # Write call info to Firestore
        doc = db.write_to_firestore(
            "calls_tracking", 
            {
                "admin_id": len(admin_data) > 0 and admin_data[0]["id"] or "",
                "call_id": call_id, 
                "agent_id": agent_id,
                "call_type": user_data['call_type'],
                "success": user_data['success'],
                "duration": (end_time - start_time).total_seconds(),
                "patient_dob": user_data["patient_dob"],
                "patient_id": user_data["patient_id"],
                "patient_name": user_data["patient_name"],
                "patient_number": user_data["patient_number"],
                "time": start_time,
                "recording_url": recording_url,
                "disconnection_reason": disconnection_reason,
                "user_sentiment": user_sentiment,
                "call_successful": call_successful,
                "cost_per_call": cost_per_call,
                "summary": summary,
                "transcript": transcript
            }
        )

        # Update total cost per client
        await update_total_cost(cost_per_call, call_time, agent_id)

        print(f"LLM WebSocket connection closed for {call_id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")
