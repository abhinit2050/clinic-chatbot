from fastapi import APIRouter
from pydantic import BaseModel
from chat import chat

class ChatRequest(BaseModel):
    conversation_history: list


router = APIRouter()

@router.post("/chat")
def chat_endpoint(request: ChatRequest):
    response = chat(request.conversation_history)
    return {"response":response}


