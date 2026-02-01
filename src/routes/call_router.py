from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from src import open_ai
from src.constants import INITIAL_MESSAGE
from src.components.archive.messages import Messages
from src.components.archive.openai_chatbot import ChatBot
from src import redis

# router for user
router = APIRouter(prefix="/call")


@router.post("/")
async def receive_call(
    request: Request,
):
    try:
        post_data = await request.form()
        sid = post_data["CallSid"]
        voice_response = VoiceResponse()
        if not redis.check_key_in_redis(sid):
            voice_response.say(
                INITIAL_MESSAGE, voice="Google.en-IN-Standard-A", language="en-IN"
            )
        # voice_response.say(INITIAL_MESSAGE)

        gather = Gather(
            input="speech",
            speech_timeout="auto",
            speech_model="experimental_conversations",
            enhanced=True,
            language="en-US",
            action="/call/respond",
            method="POST",
        )
        voice_response.append(gather)

        # redi
        response = Response(content=str(voice_response), media_type="application/xml")

        return response

    except Exception as err:
        print(err)


@router.post("/respond")
async def handle_response(
    request: Request,
):
    try:
        form_data = await request.form()
        voice_response = VoiceResponse()
        sid = form_data.get("CallSid")
        speech_result = form_data.get("SpeechResult")
        # speech_result = "Can you book an appointment with the doctor?"

        messages_list = Messages()
        if redis.check_key_in_redis(sid):
            messages_list.messages = redis.read_from_redis(sid)

        chat_bot = ChatBot(open_ai)
        # add the user question to the list
        messages_list.add_user_message(str(speech_result))
        # forward users message to llm
        assistant_response = chat_bot.ask(messages_list)
        # render llm response
        voice_response.say(
            str(assistant_response), voice="Google.en-IN-Standard-A", language="en-IN"
        )

        voice_response.redirect(url="/call/", method="POST")

        # add the llm response to the messages list
        messages_list.add_ai_message(str(assistant_response))
        redis.write_to_redis(sid, messages_list.messages)

        response = Response(content=str(voice_response), media_type="application/xml")
        return response

    except Exception as e:
        print(e)


@router.post("/upload")
def upload_to_redis(key: str, value: str):
    messages = [
        {
            "role": "system",
            "content": "You are an helpful healthcare phone assistant, you can help the patient/customer to book an appointment for the doctor",
        },
        {"role": "assistant", "content": INITIAL_MESSAGE},
    ]
    redis.write_to_redis(key, messages)
    return {"Success": True}


@router.post("/get")
def get_from_redis(key: str):
    data = redis.read_from_redis(key)
    return {"data": data}


@router.post("/check")
def check_from_redis(key: str):
    data = redis.check_key_in_redis(key)
    return {"data": data}
