from fastapi import APIRouter
from fastapi.responses import JSONResponse
from src.db.db import DB

# main router
router = APIRouter(prefix="/api")
db = DB()

@router.get("/")
def index1():
    return "Hello"

@router.get("/call-tracking/{user_id}")
async def call_tracking(user_id: str):
    print("HERE")
    data = db.get_calls_for_user(user_id)
    print(data)
    response = {"data": data}
    return JSONResponse(content=response, status_code=200)