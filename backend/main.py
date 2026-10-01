from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent import run_agent
from config import settings
from db import get_db
from seed import init_db
from tools import book_appointment, check_availability, list_available_slots

app = FastAPI(title="VPilot MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    tool_events: list[dict] = Field(default_factory=list)


class AppointmentCreate(BaseModel):
    customer_name: str
    doctor_name: str
    appointment_date: str
    appointment_time: str


@app.get("/")
def root() -> dict:
    return {
        "service": "VPilot API",
        "ui": "Run the React app: http://localhost:5173 (npm run dev in frontend/)",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages required")
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user")

    payload = [{"role": m.role, "content": m.content} for m in body.messages]
    reply, tool_events = run_agent(db, payload)
    return ChatResponse(reply=reply, tool_events=tool_events)


@app.get("/availability")
def availability(
    doctor_name: str = Query(...),
    appointment_date: str = Query(..., alias="date"),
    appointment_time: str = Query(..., alias="time"),
    db: Session = Depends(get_db),
) -> dict:
    return check_availability(
        db,
        doctor_name=doctor_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
    )


@app.get("/availability/open")
def open_slots(
    doctor_name: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_available_slots(db, doctor_name=doctor_name, limit=limit)


@app.post("/appointments")
def create_appointment(body: AppointmentCreate, db: Session = Depends(get_db)) -> dict:
    result = book_appointment(
        db,
        customer_name=body.customer_name,
        doctor_name=body.doctor_name,
        appointment_date=body.appointment_date,
        appointment_time=body.appointment_time,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result
