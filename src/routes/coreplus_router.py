from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.logger import logger
from src.utils.calculate_credits_used import update_total_cost
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
import asyncio
import json
from src.components.coreplus.llm_coreplus import CoreplusInboundLLMClient
import time
from src.db.db import DB
from datetime import datetime
from src.utils.session_vars import user_data
from src import retell

# main router
router = APIRouter(prefix="/coreplus")

@router.websocket("/inbound/{call_id}")
async def websocket_handler(websocket: WebSocket, call_id: str):
    await websocket.accept()

    call_start_timestamp = time.time()

    # Send optional config to Retell server
    config = CustomLlmResponse(
        response_type="config",
        config={
            "auto_reconnect": False,
            "call_details": True,
        },
        response_id=1,
    )
    await websocket.send_text(json.dumps(config.__dict__))
    llm_client = CoreplusInboundLLMClient(call_id=call_id)

    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        nonlocal response_id
        async for event in llm_client.draft_response(request):
            # print(event)
            if event.__dict__:
                # print(event.__dict__)j
                await websocket.send_text(json.dumps(event.__dict__))
                # await asyncio.sleep(0.005)
                # check if its end call, then calculate the credits
            # print('request.response_id', request.response_id)
            # print('response_id', response_id)
            
            if request.response_id < response_id:
                print('Abonding response')
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

        print(f"Call info: {doc.id} => {doc.get().to_dict()}")

        print(f"LLM WebSocket connection closed for {call_id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")
