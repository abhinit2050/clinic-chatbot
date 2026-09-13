# The old version of this file WAS the agent loop (system prompt, while-loop,
# manual tool dispatch, in-memory conversation_store). All of that logic now
# lives in graph.py as an explicit LangGraph state machine. What's left here is
# a thin adapter: turn one incoming chat message into a graph invocation keyed
# by session_id, and hand back the model's reply plus any UI signal (like
# "show the patient form") the frontend needs to react to.
import threading

from langchain_core.messages import HumanMessage

from graph import graph

# SqliteSaver's own docs note it isn't safe for concurrent multi-threaded use
# (see graph.py). FastAPI runs sync endpoints like ours in a thread pool, so
# two overlapping requests could otherwise hit the same SQLite connection at
# once. A single process-wide lock serializes graph invocations — simple and
# plenty fast enough for a demo's traffic level. A production system handling
# real concurrent load would reach for an async checkpointer + async endpoints
# instead of a lock.
_invoke_lock = threading.Lock()


def chat(session_id, user_message):
    config = {"configurable": {"thread_id": session_id}}
    # check_signals_node (see graph.py) only recomputes awaiting_patient_form /
    # awaiting_booking_confirmation when a tool actually ran this turn. A
    # plain-text reply (e.g. the patient saying "actually, let me change
    # something" instead of clicking Yes) skips that node entirely, which
    # would otherwise leave last turn's flags — and the stale booking summary
    # that came with them — sitting in the checkpointed state and echoed back
    # as if they still applied. Resetting them here, as part of this turn's
    # input, means they only come back true if this turn's own tool calls set
    # them again.
    with _invoke_lock:
        result = graph.invoke(
            {
                "messages": [HumanMessage(content=user_message)],
                "awaiting_patient_form": False,
                "awaiting_booking_confirmation": False,
                "booking_confirmation": None,
            },
            config=config,
        )
    return {
        "reply": result["last_reply"],
        "awaiting_patient_form": result.get("awaiting_patient_form", False),
        "awaiting_booking_confirmation": result.get("awaiting_booking_confirmation", False),
        "booking_confirmation": result.get("booking_confirmation"),
    }