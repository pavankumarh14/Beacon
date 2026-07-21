"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  planner.py · make_plan()                                  — CANDIDATE TASK  ║
╚══════════════════════════════════════════════════════════════════════════════╝

OBJECTIVE
─────────
Beacon is a warm, voice-first concierge: the user speaks about anything they want
help with ("book a restaurant for four tonight", "help me plan a weekend trip",
"pick a birthday gift for my dad") and Beacon talks them through it. This file
turns that FIRST spoken utterance into a small, structured Plan that gives the
rest of the conversation direction.

WHAT TO BUILD
─────────────
make_plan(llm, goal) -> Plan            (Plan is defined in beacon/models.py)
  * Plan.intent            one-line restatement of what the user wants help with
                           ("help you book a restaurant for tonight").
  * Plan.steps             the few most useful things to find out or cover to
                           actually help (for a restaurant: cuisine, area, time,
                           party size). Keep it short — this guides the chat.
  * Plan.confirm_question  Beacon's OPENING spoken line: a warm acknowledgement
                           plus the single most useful first question to keep the
                           conversation moving ("Happy to help you book dinner —
                           what kind of food are you in the mood for?").
Use llm.chat_json(...) for understanding; keep the OUTPUT small and structured.

EXAMPLE SYSTEM PROMPT
─────────────────────
  "You are Beacon, a warm, proactive voice concierge. Given the first thing the
   user said, restate what they want help with, list the one or two most useful
   things to find out, and write a friendly OPENING line (an acknowledgement plus
   the single best first question). Your words are spoken aloud — no markdown, no
   lists. Reply with STRICT JSON only, using exactly the keys
   {"intent": str, "steps": [str, ...], "confirm_question": str}."

HOW TO WIRE IT IN
─────────────────
Called once by beacon/agent.py:run_agent() right after status -> PLANNING:
    from .planner import make_plan
    s.plan = make_plan(llm, s.goal)
s.plan.confirm_question becomes Beacon's first spoken reply; s.plan.steps can be
threaded into the narrator's prompt to keep later replies on-track.

ACCEPTANCE CRITERIA
───────────────────
  [ ] Returns a Plan with a non-empty intent and confirm_question.
  [ ] confirm_question is warm, spoken-friendly, and ends by moving the request
      forward (usually a question) — never a flat "How can I help?".
  [ ] NEVER crashes the session on a malformed/empty LLM reply — falls back to a
      safe, generic Plan instead.
  [ ] No I/O beyond the LLM call — planning only.

STARTER / PLACEHOLDER CODE
──────────────────────────
  messages = [
      {"role": "system", "content": _SYSTEM},
      {"role": "user", "content":
          f'The user said: "{goal}". Reply with STRICT JSON: '
          '{"intent": ..., "steps": [...], "confirm_question": ...}'},
  ]
  data = llm.chat_json(messages)
  return Plan(intent=data["intent"], steps=data["steps"],
              confirm_question=data["confirm_question"])
  # ...wrap the above in try/except and return a safe fallback Plan on any failure,
  #    e.g. Plan(intent=goal, steps=[], confirm_question=
  #              "Happy to help with that — tell me a little more about what you need?")
"""

from .llm import LLMClient
from .models import Plan


_SYSTEM = (
    "You are Beacon, a warm, proactive voice concierge that helps people get "
    "things done by talking. Given the first thing the user said, restate what "
    "they want help with, list the one or two most useful things to find out, and "
    "write a friendly opening line that moves the request forward. Your words are "
    "spoken aloud — keep them natural, no markdown and no lists. Keep intent "
    "under 12 words, return at most two steps of at most 12 words each, and "
    "keep confirm_question to one sentence of at most 18 words."
)


def make_plan(llm: LLMClient, goal: str) -> Plan:
    """Create a small, validated plan without allowing model output to break a session."""
    clean_goal = " ".join((goal or "").split())
    fallback = Plan(
        intent=clean_goal or "help with the user's request",
        steps=["Understand the most important detail", "Offer a practical next step"],
        confirm_question=(
            "Happy to help. What is the most important detail you want to start with?"
        ),
    )
    if not clean_goal or llm is None:
        return fallback

    messages = [
        {"role": "system", "content": _SYSTEM + " Reply with strict JSON only, using exactly "
         "these keys: intent, steps, confirm_question."},
        {"role": "user", "content": "The user said: %s" % clean_goal},
    ]
    try:
        # Some otherwise-valid models expand conversational wording until a
        # short JSON response is cut off mid-string.  The concise schema prompt
        # above keeps normal output tiny; this headroom makes the parse resilient
        # when a provider is a little more verbose than requested.
        data = llm.chat_json(messages, max_tokens=360)
        if not isinstance(data, dict):
            return fallback
        intent = _clean_text(data.get("intent"), fallback.intent)
        question = _clean_text(data.get("confirm_question"), fallback.confirm_question)
        steps = data.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        steps = [_clean_text(step, "") for step in steps]
        steps = [step for step in steps if step][:3]
        return Plan(intent=intent, steps=steps or fallback.steps, confirm_question=question)
    except Exception as exc:  # The conversation can still start without an LLM.
        # This appears in Render logs and makes a bad key/model/base URL
        # diagnosable without exposing provider details to the voice UI.
        print("[beacon] planner LLM fallback: %s" % exc)
        return fallback


def _clean_text(value, default: str) -> str:
    if not isinstance(value, str):
        return default
    value = " ".join(value.split()).strip()
    return value[:500] if value else default
