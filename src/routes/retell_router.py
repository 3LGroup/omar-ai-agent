import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import retell
from retell.resources.call import CallResponse
from src.components.inbound_llm import InboundLLMClient
from src import app

router = APIRouter(prefix="/retell")


@router.get("/")
async def hello():
    return {"status": "ok"}
