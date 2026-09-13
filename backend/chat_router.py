from fastapi import APIRouter
from pydantic import BaseModel
from chat import chat

class ChatRequest(BaseModel):
    session_id:str
    message:str


router = APIRouter()

@router.post("/chat")
def chat_endpoint(request: ChatRequest):
    result = chat(request.session_id, request.message)
    return {
        "response": result["reply"],
        "awaiting_patient_form": result["awaiting_patient_form"],
        "awaiting_booking_confirmation": result["awaiting_booking_confirmation"],
        "booking_confirmation": result["booking_confirmation"],
    }


