from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.logger import logger
from src.utils.calculate_credits_used import update_total_cost
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
import asyncio
import json
from src.components.gohighlevel.llm_gohighlevel import GoHighLevelInboundLLMClient
import time
from src.db.db import DB
from datetime import datetime
from src.utils.session_vars import user_data
from src import retell

# GoHighLevel router
router = APIRouter(prefix="/gohighlevel")

@router.websocket("/inbound/{call_id}")
async def websocket_handler(websocket: WebSocket, call_id: str):
    await websocket.accept()
    print("WebSocket connection established for call_id: ", call_id)
    call_start_timestamp = time.time()
    user_data['call_type'] = "INBOUND"
    
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
    logger.info(f"WebSocket connection established for call_id: {call_id}")
    
    llm_client = GoHighLevelInboundLLMClient(call_id=call_id)
    
    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))
    
    async def stream_response(request: CustomLlmRequest):
        nonlocal response_id
        async for event in llm_client.draft_response(request):
            if event.__dict__:
                await websocket.send_text(json.dumps(event.__dict__))
            
            if request.response_id < response_id:
                logger.info('Abandoning response - new response needed')
                return  # new response needed, abandon this one
    
    try:
        while True:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=100 * 60
            )  # 100 minutes timeout
            
            request_json = json.loads(message)
            request: CustomLlmRequest = CustomLlmRequest(**request_json)
            
            # Handle different interaction types
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
                logger.info(
                    f"Received interaction_type={request_json['interaction_type']}, "
                    f"response_id={response_id}, "
                    f"last_transcript={request_json['transcript'][-1]['content'] if request_json.get('transcript') else 'N/A'}"
                )
                
                asyncio.create_task(stream_response(request))
    
    except WebSocketDisconnect as e:
        logger.error(f"LLM WebSocket disconnected for {call_id} due to {e}")
    
    except Exception as e:
        logger.error(f"Error in LLM WebSocket: {e}")
    
    finally:
        call_end_timestamp = time.time()
        db = DB()
        
        start_time = datetime.fromtimestamp(call_start_timestamp)
        end_time = datetime.fromtimestamp(call_end_timestamp)
        await asyncio.sleep(2)
        
        # Get call info from retell
        call_info = retell.call.retrieve(call_id)
        
        # Test agents - skip storing data for these
        testAgent = ["agent_7987500be36c3df79914b65afb", "agent_7520b7026a607bf8a9a6b629a5", "agent_dc542530e97a7ab81f367da9ae"]
        if call_info.agent_id in testAgent:
            logger.info(f"Test agent call - no data stored for call {call_id}")
            return
        
        # Store required info from retell
        transcript = call_info.transcript
        agent_id = call_info.agent_id
        recording_url = call_info.recording_url
        disconnection_reason = call_info.disconnection_reason
        from_number = getattr(call_info, "from_number", "Web Call")
        user_sentiment = call_info.call_analysis.user_sentiment
        summary = call_info.call_analysis.call_summary
        call_successful = call_info.call_analysis.call_successful
        seconds = call_info.call_cost.total_duration_seconds
        
        # Calculate cost per call
        minutes, seconds = divmod(seconds, 60)
        full_minute_credits = minutes
        partial_minute_credits = seconds / 60
        call_time = full_minute_credits + partial_minute_credits
        cost_per_call = (call_time * 0.15)
        logger.info(f"Cost per call: {cost_per_call}")
        
        # Get user data
        admin_data = db.get_user_by_agent_id(agent_id)
        logger.info(f"Admin data retrieved for agent_id: {agent_id}")
        
        # Write call info to Firestore
        doc = db.write_to_firestore(
            "calls_tracking",
            {
                "admin_id": len(admin_data) > 0 and admin_data[0]["uid"] or "",
                "call_id": call_id,
                "agent_id": agent_id,
                "call_type": user_data.get('call_type', 'INBOUND'),
                "success": user_data.get('success', False),
                "duration": (end_time - start_time).total_seconds(),
                "patient_dob": user_data.get("patient_dob", ""),
                "patient_id": user_data.get("patient_id", ""),
                "patient_name": f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                "patient_number": user_data.get("phone", ""),
                "time": start_time,
                "recording_url": recording_url,
                "disconnection_reason": disconnection_reason,
                "user_sentiment": user_sentiment,
                "call_successful": call_successful,
                "cost_per_call": cost_per_call,
                "phone_number": from_number,
                "summary": summary,
                "transcript": transcript
            }
        )
        
        # Update total cost per client
        await update_total_cost(cost_per_call, call_time, agent_id)
        
        logger.info(f"Call info stored: {doc.id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")

