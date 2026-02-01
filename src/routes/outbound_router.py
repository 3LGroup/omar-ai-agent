import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from src.logger import logger
from src.components.nookal.outbound_llm import OutboundLlmClient
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
from src import twilio_client, retell
from src.schemas.outbound_call import OutboundRescheduleRequest

# main router
router = APIRouter(prefix="/outbound")


@router.post("/reschedule")
async def call_outbound(params: OutboundRescheduleRequest):
    try:
        call = twilio_client.create_phone_call(
            "+18563176120",
            params.phone_number_to,
            # for Azure
            "f7c1ffae3ef902281ac72c3c58c2f59d",
            # for local
            # "d9473318e057540d06669512a8773265",
            "Hashan",
            params.message,
            "RESCHEDULE",
            params.appointment_id,
            params.date,
        )
        return JSONResponse(
            content={"message": "Successful in Outbound Call", "call_id": call.sid},
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Error creating phone call {e}")
        return JSONResponse(
            content={"message": "Failed to Connect", "error": str(e)}, status_code=404
        )


# Custom LLM Websocket handler, receive audio transcription and send back text response
@router.websocket("/reschedule/{call_id}")
async def websocket_handler(
    websocket: WebSocket,
    call_id: str,
):
    await websocket.accept()
    logger.info("Outbound::LLM")

    call_details = retell.call.retrieve(call_id)
    metadata = call_details.metadata

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
    if metadata.get("agent_type") == "RESCHEDULE":
        llm_client = OutboundLlmClient(
            metadata=metadata,
        )
    
    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        nonlocal response_id
        #  TODO : BUG
        for event in llm_client.draft_response(request):
            await websocket.send_text(json.dumps(event.__dict__))
            # await asyncio.sleep(0.005)
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
                asyncio.create_task(stream_response(request))

    except WebSocketDisconnect as e:
        print(f"LLM WebSocket disconnected for {call_id} due to {e}")
        logger.error(f"LLM WebSocket disconnected for {call_id}")
    except Exception as e:
        print(f"Error in LLM WebSocket: {e}")
        logger.error(f"Error in LLM WebSocket: {e}")
    finally:
        print(f"LLM WebSocket connection closed for {call_id}")
        logger.info(f"LLM WebSocket connection closed for {call_id}")
