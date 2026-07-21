"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  narrator.py · compose_reply() + closing_line()            — CANDIDATE TASK  ║
╚══════════════════════════════════════════════════════════════════════════════╝

OBJECTIVE
─────────
This is Beacon's "voice". Given the conversation so far, produce the next thing
Beacon SAYS — warm, concrete, and written for the ear. And when the conversation
ends, produce a short, graceful closing line.

WHAT TO BUILD
─────────────
compose_reply(llm, history, plan=None) -> str          (LLM)
  * `history` is an OpenAI-style message list (system + alternating user/assistant
    turns) built by agent.py from the saved transcript.
  * Return ONE to THREE short, natural spoken sentences that move the request
    forward — ask the most useful next question, or give a concrete suggestion.
    No markdown, no bullet lists, no emoji. Use a small max_tokens.
  * `plan` (optional) is the Plan from planner.py — use plan.steps to stay on
    track if you like.
  * On ANY LLM failure, fall back to a deterministic, friendly line so the user
    is never left in silence (e.g. "Sorry, I didn't quite catch that — could you
    say it again?").

closing_line(history) -> str                           (DETERMINISTIC — no LLM!)
  * A short, warm farewell built WITHOUT calling the model, so the conversation
    always ends gracefully even if the LLM is unavailable. This is the same trust
    boundary as the rest of Beacon: the guaranteed-safe path is plain code, never
    left to chance. (See navigator.py — the DECISION to end is deterministic too.)

EXAMPLE SYSTEM PROMPT        (for compose_reply only)
─────────────────────
  "You are Beacon, a warm, proactive voice concierge. Reply in one to three short,
   natural spoken sentences. Write for the ear: no markdown, no lists, no emoji.
   Do NOT lead with disclaimers — focus on how you CAN help and keep moving the
   request forward. End with a brief follow-up question when it keeps things going."
  (closing_line uses NO prompt — it is deterministic string-building.)

HOW TO WIRE IT IN
─────────────────
In beacon/agent.py:
    s.say(TurnKind.NARRATION.value, compose_reply(llm, history, s.plan))   # each turn
    ...
    s.say(TurnKind.OUTCOME.value, closing_line(history))                   # on goodbye

ACCEPTANCE CRITERIA
───────────────────
  [ ] compose_reply returns 1–3 spoken sentences; NEVER raises (LLM down -> fallback).
  [ ] Output is plain spoken text — no markdown / lists / code fences.
  [ ] closing_line returns a warm farewell with NO LLM call.

STARTER / PLACEHOLDER CODE
──────────────────────────
  # compose_reply:
  try:
      txt = (llm.chat([{"role": "system", "content": _SYSTEM}] + history,
                      max_tokens=200, temperature=0.6) or "").strip()
      return txt or _FALLBACK
  except Exception:
      return _FALLBACK

  # closing_line (deterministic):
  return "Glad I could help — take care, and just say the word if you need me again."
"""

from typing import List, Dict, Optional

from .llm import LLMClient
from .models import Plan


_SYSTEM = (
    "You are Beacon, a warm, proactive voice concierge. Reply in one to three "
    "short, natural spoken sentences. Write for the ear: no markdown, no bullet "
    "lists, no code blocks, no emoji. Do NOT lead with disclaimers like 'I can't "
    "do that' — focus on how you CAN help and keep moving the request forward. End "
    "with a brief follow-up question when it keeps things going."
)

_FALLBACK = "Sorry, I didn't quite catch that — could you say it again?"


def compose_reply(llm: LLMClient, history: List[Dict[str, str]],
                  plan: Optional[Plan] = None) -> str:
    plan_context = ""
    if plan:
        steps = "; ".join(plan.steps[:3])
        plan_context = "\nConversation goal: %s. Useful remaining areas: %s." % (
            plan.intent, steps or "move the request forward")
    messages = [{"role": "system", "content": _SYSTEM + plan_context}] + list(history)
    try:
        reply = (llm.chat(messages, temperature=0.5, max_tokens=180) or "").strip()
        return _spoken_text(reply) or _FALLBACK
    except Exception as exc:
        # Keep speech graceful, but leave the actionable provider error in the
        # host logs (for example: invalid key, unavailable model, bad base URL).
        print("[beacon] narrator LLM fallback: %s" % exc)
        return _FALLBACK


def closing_line(history: List[Dict[str, str]]) -> str:
    # Deliberately independent of the model and transcript contents: this is the
    # guaranteed exit path for a voice session.
    return "You’re all set. Thanks for talking with me, and take care."


def _spoken_text(text: str) -> str:
    """Keep an otherwise useful model response suitable for speech output."""
    if not isinstance(text, str):
        return ""
    text = " ".join(text.replace("`", "").split())
    # Models occasionally return a prefixed Markdown list despite the prompt.
    text = text.lstrip("-• ")
    return text[:900].strip()
