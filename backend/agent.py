import json
import logging
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from openai import OpenAI
from sqlalchemy.orm import Session

from config import settings
from kb import retrieve_clinic_info
from tools import book_appointment, check_availability, list_available_slots

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are VPilot, the AI receptionist for Sunrise Family Clinic (demo MVP).

Today's date is {today}. When users say "tomorrow", use {tomorrow}.

Rules:
- Answer general clinic questions using the search_clinic_knowledge tool. Do not invent facts.
- For availability, use check_availability with doctor name, date (YYYY-MM-DD), and time.
- For booking, you MUST have customer name, doctor, date, and time. Ask for anything missing.
- Before confirming a booking, call check_availability, then book_appointment only if available.
- Only say an appointment is booked after book_appointment returns booked=true.
- If you cannot answer safely, say the information is unavailable.
- Be concise and friendly.

Doctors at this clinic: Dr. Ahmed (General Practice), Dr. Lee (Pediatrics), Dr. Santos (Women's Health).
"""


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_clinic_knowledge",
            "description": "Search the clinic FAQ/knowledge base for policies, hours, location, insurance, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User question or topic to look up"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check if a doctor has an available appointment slot at a date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {"type": "string"},
                    "appointment_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "appointment_time": {"type": "string", "description": "e.g. 15:00 or 3:00 PM"},
                },
                "required": ["doctor_name", "appointment_date", "appointment_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment after verifying availability. Only call when all details are known.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "doctor_name": {"type": "string"},
                    "appointment_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "appointment_time": {"type": "string", "description": "e.g. 15:00 or 3:00 PM"},
                },
                "required": ["customer_name", "doctor_name", "appointment_date", "appointment_time"],
            },
        },
    },
]


def _client() -> OpenAI:
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY is required. Set it in backend/.env or your deployment environment.")
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def _run_tool(db: Session, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "search_clinic_knowledge":
        text = retrieve_clinic_info(arguments.get("query", ""))
        if not text:
            return {"ok": True, "found": False, "message": "No matching clinic information in the knowledge base."}
        return {"ok": True, "found": True, "content": text}

    if name == "check_availability":
        return check_availability(
            db,
            doctor_name=arguments["doctor_name"],
            appointment_date=arguments["appointment_date"],
            appointment_time=arguments["appointment_time"],
        )

    if name == "book_appointment":
        return book_appointment(
            db,
            customer_name=arguments["customer_name"],
            doctor_name=arguments["doctor_name"],
            appointment_date=arguments["appointment_date"],
            appointment_time=arguments["appointment_time"],
        )

    return {"ok": False, "error": f"Unknown tool: {name}"}


def run_agent(db: Session, messages: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    """Simple tool-calling loop (max 6 rounds)."""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    system = SYSTEM_PROMPT.format(today=today.isoformat(), tomorrow=tomorrow.isoformat())

    chat_messages: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
    tool_traces: list[dict[str, Any]] = []
    client = _client()

    for _ in range(6):
        try:
            hostname = (urlparse(settings.llm_base_url).hostname or "").lower()
            provider = "Groq" if hostname == "api.groq.com" or hostname.endswith(".groq.com") else "OpenAI-compatible"
            logger.info("LLM provider: %s", provider)
            logger.info("LLM model: %s", settings.llm_model)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=chat_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as exc:
            fallback = _fallback_reply(db, messages, str(exc))
            return fallback, tool_traces

        choice = response.choices[0].message
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": choice.content or ""}
        if choice.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.tool_calls
            ]
        chat_messages.append(assistant_msg)

        if not choice.tool_calls:
            text = (choice.content or "").strip()
            return text or "I'm sorry, I couldn't generate a response.", tool_traces

        for tc in choice.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _run_tool(db, tc.function.name, args)
            tool_traces.append({"tool": tc.function.name, "arguments": args, "result": result})
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )

    return "I need a bit more information to complete that request.", tool_traces


def _fallback_reply(db: Session, messages: list[dict[str, str]], llm_error: str) -> str:
    """Minimal offline-style help when the LLM is unreachable (demo continuity)."""
    last = (messages[-1]["content"] if messages else "").lower()
    if "hour" in last or "open" in last:
        text = retrieve_clinic_info("clinic hours")
        if text:
            return text + "\n\n(Note: LLM is offline; showing knowledge base directly.)"
    if "available" in last or "availability" in last:
        slots = list_available_slots(db, limit=5)
        if slots:
            lines = [f"- {s['doctor']} on {s['date']} at {s['time']}" for s in slots]
            return (
                "I couldn't reach the AI model ({err}). Here are some open slots:\n".format(err=llm_error)
                + "\n".join(lines)
            )
    return (
        "The AI assistant is temporarily unavailable ({err}). "
        "Please configure LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in backend/.env or your deployment environment."
    ).format(err=llm_error)
