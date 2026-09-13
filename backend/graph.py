# WHY THIS FILE EXISTS
# ---------------------
# The old chat.py drove the conversation with a hand-written `while True` loop:
# call the model, look at what it returned, manually if/elif over which tool
# was called, manually append the right shape of message to history, repeat.
# Every new tool meant touching that loop again, and nothing *structurally*
# stopped the model from calling tools out of order — the only guardrail was
# prompt text ("always call list_doctors first").
#
# LangGraph replaces that loop with an explicit state machine: a small set of
# named nodes (steps) and edges (allowed transitions between them), compiled
# once at import time. If you've built a Node/Express app before, think of
# nodes here as roughly analogous to route handlers, except instead of an HTTP
# router deciding which handler runs next based on a URL, a "conditional edge"
# function decides which node runs next based on the conversation state (did
# the model ask for a tool? did a booking/cancellation just succeed?). The
# routing logic is centralized and readable in one place (see the edges at the
# bottom of this file) instead of being implicit in scattered if-statements.
import json
import os
import sqlite3
from datetime import date

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.prebuilt import ToolNode

from tools import (
    book_appointment,
    cancel_appointment,
    check_availability,
    confirm_booking_details,
    list_appointments,
    list_doctors,
    request_patient_details,
)

load_dotenv()

TOOLS = [
    list_doctors,
    check_availability,
    confirm_booking_details,
    book_appointment,
    list_appointments,
    cancel_appointment,
    request_patient_details,
]
TERMINAL_TOOLS = {"book_appointment", "cancel_appointment"}
# request_patient_details and confirm_booking_details aren't "terminal"
# actions (nothing in the DB changes) — they're UI signals, tracked
# separately from terminal_action_pending so the frontend can tell "show a
# form/summary now" apart from "a booking just completed, wrap up the
# session."
FORM_REQUEST_TOOL = "request_patient_details"
BOOKING_CONFIRM_TOOL = "confirm_booking_details"

llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
llm_with_tools = llm.bind_tools(TOOLS)


class ChatState(MessagesState):
    # True right after a booking/cancellation tool call has succeeded, for one
    # turn — tells the graph to run the summarize node next instead of ending.
    terminal_action_pending: bool
    # The text to actually hand back to the caller for this turn. Kept
    # separate from `messages` because summarize_node prunes/replaces the
    # message list right after a terminal action — if chat.py read the reply
    # off `messages[-1]` directly, the user would see the *summary* instead of
    # the confirmation the model just wrote for them. Same idea as keeping an
    # API response body separate from whatever you persist server-side.
    last_reply: str
    # True for one turn right after the model calls request_patient_details —
    # tells chat_router.py to tell the frontend "render the patient-details
    # form now" instead of relying on the frontend to guess from the message
    # text, which would be fragile (breaks the moment the wording changes).
    awaiting_patient_form: bool
    # Same idea, for the Yes/Cancel confirm_booking_details step — set once
    # the model has all the details and wants the patient to explicitly
    # approve them before anything is booked.
    awaiting_booking_confirmation: bool
    # The exact doctor/slot/patient fields confirm_booking_details echoed
    # back, so the frontend can render the summary card without re-parsing
    # it out of the model's prose reply.
    booking_confirmation: dict | None


def agent_node(state: ChatState) -> dict:
    """The 'brain' node: gives the model the current message history + tools and lets it decide what to do next (reply in text, or call a tool)."""
    today = date.today().strftime("%Y-%m-%d")
    system_prompt = f"""
    You are a helpful clinic appointment assistant. You help patients book, cancel, and check appointments with doctors.
    Today's date is {today}. Use this as reference when the user says "today", "tomorrow", or any relative date.

    You have access to the following tools:
    - list_doctors: use this when the user asks about available doctors
    - check_availability: use this when the user has chosen a doctor and a date
    - request_patient_details: the ONLY way to collect the patient's name/phone/email — it shows them a form, there is no other input channel for it. RULE: the instant the patient confirms a specific doctor + date + time slot, your entire response for that turn must be a call to this tool — not a text reply. If your response would contain words like "details", "name", "phone", or "few things I need", that is a sign you must be calling this tool instead of writing that sentence. A text-only reply that talks about needing details without calling this tool is always wrong and leaves the patient stuck with nothing to click.
    - confirm_booking_details: call this once you have ALL of doctor, date, time slot, AND the patient's name + phone (from request_patient_details) — pass every one of those exact values. This shows the patient a summary card with Yes/Cancel buttons; it does not book anything. Do NOT call book_appointment in the same turn as this — wait for the patient's next message.
    - book_appointment: call this ONLY in the turn right after the patient has replied to a confirm_booking_details summary by clicking Yes. Use the exact same doctor/slot/name/phone/email you just showed them in confirm_booking_details — do not change or re-derive them. If they clicked Cancel or asked to change something instead, do not call this — go back to confirm_booking_details with the corrected values once you have them. Email is optional but nice to collect (it enables appointment reminder emails). If the patient mentioned any symptoms or a reason for the visit earlier in the conversation, you MUST pass it as the `reason` argument — don't drop it just because they haven't repeated it right before booking.
    - list_appointments: use this when the user wants to see, or cancel, their existing appointments. Ask for their phone number or email to look them up — whichever they find easier to give, either one is enough.
    - cancel_appointment: use this only after list_appointments has shown the patient their appointments and they've confirmed which one to cancel. Never guess an appointment id.
    - Always use the exact doctor id, slot id, and appointment id returned by the tools. Never guess or make up ids.
    - Always call list_doctors first before check_availability to get the correct doctor ids. Never assume a doctor's id.
    - After a booking or cancellation is complete, present a natural confirmation message to the user with the relevant doctor's name, date and time. Do not include any ids in the confirmation message.

    Always be polite and conversational. If the user hasn't provided all necessary information, ask for it one piece at a time. Never make up doctor names, slots, or appointments — always use the tools to fetch real data.
    """
    response = llm_with_tools.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    return {"messages": [response], "last_reply": response.content}


tools_node = ToolNode(TOOLS)


def check_signals_node(state: ChatState) -> dict:
    """Looks at the tool results the agent node's last tool call(s) just produced, and raises flags for the rest of the graph (and eventually the frontend) to react to: did a booking/cancellation just succeed (terminal_action_pending — triggers summarize), did the model just ask to show the patient-details form (awaiting_patient_form), and did it just ask for Yes/Cancel confirmation on a booking summary (awaiting_booking_confirmation)."""
    terminal_action_pending = False
    awaiting_patient_form = False
    awaiting_booking_confirmation = False
    booking_confirmation = None
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        if message.name == FORM_REQUEST_TOOL:
            awaiting_patient_form = True
        if message.name == BOOKING_CONFIRM_TOOL:
            try:
                booking_confirmation = json.loads(message.content)
            except (json.JSONDecodeError, TypeError):
                booking_confirmation = None
            awaiting_booking_confirmation = booking_confirmation is not None
        if message.name in TERMINAL_TOOLS:
            try:
                result = json.loads(message.content)
            except (json.JSONDecodeError, TypeError):
                result = {}
            if result.get("success"):
                terminal_action_pending = True
    return {
        "terminal_action_pending": terminal_action_pending,
        "awaiting_patient_form": awaiting_patient_form,
        "awaiting_booking_confirmation": awaiting_booking_confirmation,
        "booking_confirmation": booking_confirmation,
    }


def summarize_node(state: ChatState) -> dict:
    """Runs once a booking or cancellation has just completed. Same idea as the old chat.py's summarize_conversation(): a clinic chatbot session has a natural end point, so we condense the whole transcript into a short summary and drop the raw turns/tool-call noise — keeping future context (and token cost) small if the same session_id/thread keeps talking."""
    summary_prompt = (
        "Summarize this entire clinic chatbot session in a few sentences — "
        "note what was booked and/or cancelled, for whom, and when. "
        "Only state what actually happened in this conversation and the tool "
        "results above — do not invent or assume any outcome (e.g. whether an "
        "email was sent or received) that isn't directly shown here."
    )
    summary_response = llm.invoke(state["messages"] + [SystemMessage(content=summary_prompt)])

    # RemoveMessage(id=REMOVE_ALL_MESSAGES) is LangGraph's built-in way to wipe
    # a thread's message list via the state update mechanism, rather than
    # reaching in and mutating conversation_store by hand like the old code did.
    return {
        "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), AIMessage(content=summary_response.content)],
        "terminal_action_pending": False,
        "awaiting_patient_form": False,
        "awaiting_booking_confirmation": False,
        "booking_confirmation": None,
    }


def route_after_agent(state: ChatState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    if state.get("terminal_action_pending"):
        return "summarize"
    return END


builder = StateGraph(ChatState)
builder.add_node("agent", agent_node)
builder.add_node("tools", tools_node)
builder.add_node("check_signals", check_signals_node)
builder.add_node("summarize", summarize_node)

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "summarize": "summarize", END: END})
# Always loop back to the agent after tools run (rather than ending right after
# a successful booking, like the old code's hardcoded confirmation string did)
# so the model gets a turn to phrase a natural, LLM-generated confirmation.
builder.add_edge("tools", "check_signals")
builder.add_edge("check_signals", "agent")
builder.add_edge("summarize", END)

# checkpoints.db is deliberately a separate SQLite file from clinic.db — this
# one holds LangGraph's own conversation/session state (which thread said what,
# keyed by thread_id), not clinic appointment data. It's the direct replacement
# for the old in-memory `conversation_store` dict: same job (remember each
# session's history), but backed by disk so it survives a server restart —
# conceptually similar to swapping an in-memory session store for a
# Redis/DB-backed one in a Node app.
_checkpoint_conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(_checkpoint_conn)

graph = builder.compile(checkpointer=checkpointer)
