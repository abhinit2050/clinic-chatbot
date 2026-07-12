from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chat_router import router
from database import create_tables

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

create_tables()

app.include_router(router)