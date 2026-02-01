import asyncio
from datetime import datetime, timedelta
import json
import os
from typing import Optional
from fastapi import FastAPI, Request, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from retell import Retell
from src.components.cliniko.cliniko_client import ClinikoClient
from src.components.archive.redis_service import RedisService
from src.components.odoo.llm import ThreeLinesLLMClient
from fastapi import WebSocket
from twilio.twiml.voice_response import VoiceResponse, Dial
from src.components.twilio_client import TwilioClient
from src.logger import logger
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
from src.db.db import DB
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    # docs_url=None
    # if os.environ.get("DOCS_URL") == "None"
    # else os.environ.get("DOCS_URL"),
    # redoc_url=None
    # if os.environ.get("RE_DOC_URL") == "None"
    # else os.environ.get("RE_DOC_URL"),
)

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# redis = RedisService()

@app.get("/")
def index():
    return {"status": "ok"}

@app.get("/health")
def hello():
    return {"status": "ok"}


retell = Retell(api_key=os.getenv("RETELL_API_KEY"))
twilio_client = TwilioClient()

# azure
# Nookal Agent
# twilio_client.register_phone_agent("+61483968461", "agent_e0d536aacf9c5889c4099eec51") # MacPhysio Clinic Prod Inbound

# # # Cliniko Production
# twilio_client.register_phone_agent("+15074605760", "agent_f7de1474c39784d96ebe5f09c1") # Cliniko Demo Answerly

# routes here
from .routes import outbound_router
from src.routes import cliniko_router, coreplus_router, nookal_router
from src.routes import outbound_cliniko_router
from src.routes import payment_router
from src.routes import db_router
from src.routes import lambda_flow
from src.routes import gohighlevel_router
from src.routes import threelines_router

# from src.routes import api_router

# # nested routes
app.router.include_router(router=outbound_router.router)
app.router.include_router(router=cliniko_router.router)
app.router.include_router(router=coreplus_router.router)
app.router.include_router(router=nookal_router.router)
app.router.include_router(router=outbound_cliniko_router.router)
app.router.include_router(router=payment_router.router)
app.router.include_router(router=db_router.router)
app.router.include_router(router=lambda_flow.router)
app.router.include_router(router=gohighlevel_router.router)
app.router.include_router(router=threelines_router.router)
# app.router.include_router(router=api_router.router)

db = DB()
@app.post('/call-tracking/{user_id}')
async def call_tracking(user_id: str):
    print("HERE")
    data = db.get_calls_for_user(user_id)
    return JSONResponse(content=data, status_code=200)

@app.get('/credits/{user_id}')
async def call_tracking(user_id: str):
    print("Credits table being read")
    data = db.get_credits_for_user(user_id)
    return JSONResponse(content=data, status_code=200)

@app.post("/twilio-voice-webhook/{agent_id_path}")
async def handle_twilio_voice_webhook(
    request: Request,
    agent_id_path: str,
    dr: Optional[str] = None,
    reason: Optional[str] = None,
    agent_type: Optional[str] = None,
    appointment_id: Optional[str] = None,
    date: Optional[str] = None,

    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    crm: Optional[str] = None,
    old_start_date: Optional[str] = None,
    old_end_date: Optional[str] = None,
    appointment_date: Optional[str] = None, 
):
    try:
        logger.info("twilio voice webhook")
        # Check if it is machine
        post_data = await request.form()
        print("post_data----------->", post_data)
        if "AnsweredBy" in post_data and post_data["AnsweredBy"] == "machine_start":
            twilio_client.end_call(post_data["CallSid"])
            return PlainTextResponse("")
        elif "AnsweredBy" in post_data:
            return PlainTextResponse("")
        call_type = "outbound" if dr is not None and reason is not None else "inbound"

        print('call_type->', call_type)
        
        if crm == "cliniko" or crm == "coreplus":
            call_response = retell.call.register_phone_call(
                agent_id=agent_id_path,
                direction=call_type,
                from_number=post_data["From"],
                to_number=post_data["To"],
                metadata={
                    "twilio_call_sid": post_data["CallSid"],
                    "agent_id": agent_id_path,
                    "dr": dr,
                    "reason": reason,
                    "agent_type": agent_type,
                    "call_type": call_type,
                    "old_start_date": old_start_date, 
                    "old_end_date": old_end_date,
                    "first_name": first_name,
                    "last_name": last_name,
                    "appointment_date": appointment_date,
                    "date_of_birth": date_of_birth,
                },
            )
        else:
            call_response = retell.call.register_phone_call(
                agent_id=agent_id_path,
                direction=call_type,
                from_number=post_data["From"],
                to_number=post_data["To"],
                metadata={
                    "twilio_call_sid": post_data["CallSid"],
                    "dr": dr,
                    "reason": reason,
                    "agent_type": agent_type,
                    "call_type": call_type,
                    "date": date,
                    "appointment_id": appointment_id,
                },
            )
            print("Call Response from INIT.PY-------" , call_response)


        response = VoiceResponse()
        response.dial
        dial= Dial()
        dial.sip(f"sip:{call_response.call_id}@5t4n6j0wnrl.sip.livekit.cloud")
        response.append(dial)
        start = response.connect()
        start.stream(
            url=f"wss://api.retellai.com/audio-websocket/{call_response.call_id}"
        )
        return PlainTextResponse(str(response), media_type="text/xml")
    except Exception as err:
        print(f"Error in twilio voice webhook: {err}")
        logger.error(f"Error in twilio voice webhook: {err}")
        return JSONResponse(
            status_code=500, content={"message": "Internal Server Error"}
        )


# Custom LLM Websocket handler, receive audio transcription and send back text response
@app.websocket("/llm/{call_id}")
async def websocket_handler(websocket: WebSocket, call_id: str):
    from src.components.nookal.llm import InboundLLMClient
    await websocket.accept()

    # retrieve call details
    call_details = retell.call.retrieve(call_id)
    print(call_details.metadata)

    logger.info(call_details.metadata)

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
    llm_client = InboundLLMClient()

    # Send first message to signal ready of server
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        nonlocal response_id
        for event in llm_client.draft_response(request):
            if event.__dict__:
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


@app.post("/update-agent")
def update_agent_voice():
    agent = retell.agent.update(
        "b3c9bfe6f863192a49ea7e61ce55974e", voice_id="11labs-Anna"
    )
    return agent.agent_id

@app.post("/test")
def update_agent_voice(date:str):
    client = ClinikoClient(api_key= 'MS0xNDU1ODY1MTA4ODg1NDE1NDIzLUhzakVhMXpaU2VKRGFuWk9wTXlFcmcvNS9laEFDR0Yw-au4')
    datetime_str = date
    input_date = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
    adjusted_date = input_date + timedelta(hours=5)
    formatted_date = adjusted_date.strftime("%Y-%m-%dT%H:%M:%S")
    print(formatted_date)

    params = {'appointment_type_id': '1455858097300973099',
    'business_id': '1455858098517320785',
    'date_of_birth': '2000-08-18',
    'email': 'alexjacob260@gmail.com',
    'first_name': 'John',
    'last_name': 'Mango',
    #  'practitioner_id': '1435322059428210417',
    'practitioner_id': '1455858094155245241',
    #  'ends_at': '2024-07-02T08:30:00',
    'starts_at':formatted_date 
    # 'starts_at': datetime_str 
    }
    data, _ = client.create_individual_appointment(params)
    return data
