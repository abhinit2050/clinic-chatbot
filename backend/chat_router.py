from fastapi import APIRouter
from pydantic import BaseModel
from chat import chat

class ChatRequest(BaseModel):
    session_id:str
    message:str


router = APIRouter()

@router.post("/chat")
def chat_endpoint(request: ChatRequest):
    response = chat(request.session_id, request.message)
    return {"response":response}


