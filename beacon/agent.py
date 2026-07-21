"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  agent.py · the orchestrator (run / reply)                 — CANDIDATE TASK  ║
╚══════════════════════════════════════════════════════════════════════════════╝

OBJECTIVE
─────────
Run the whole conversation. Beacon is a voice-first concierge: the user speaks an
opening request, Beacon talks them through it turn by turn, and the session ends
when the user says they're done. This file drives the SessionStatus state machine
and ties together planner (understand), narrator (speak), and navigator (flow).

    new → planning → CONVERSING ⇄ (user speaks) ⇄ CONVERSING → done
                                                          └→ error (unrecoverable)

WHAT TO BUILD        (2 entry points — each marked with a TODO below)
─────────────
run_agent(session_id)             first turn: record the opening utterance, plan
                                  it, and speak Beacon's opening reply.
handle_reply(session_id, text)    every later turn: record what the user said,
                                  decide continue-vs-end (navigator), then either
                                  reply (narrator) or close out.

The two helpers below — _history() and _fail() — are PROVIDED. Use them.

EXAMPLE SYSTEM PROMPT
─────────────────────
  N/A — the orchestrator does not prompt the LLM directly. It passes `llm` and the
  message history to narrator/planner (which own their prompts), and uses the
  DETERMINISTIC navigator to decide when to end. Keeping the "should we stop?"
  decision out of the LLM's hands is the graded design rule: the user must always
  be able to end the conversation.

HOW TO WIRE IT IN
─────────────────
server.py already delegates here (you do not touch server.py):
    run_agent(session_id)            on a new Session (background thread)
    handle_reply(session_id, text)   on each spoken/typed reply
Call store.save(s) after EVERY state change so the dashboard speaks new turns.
The dashboard speaks NARRATION + OUTCOME turns and, while status is CONVERSING,
re-opens the mic for the next thing the user says.

ACCEPTANCE CRITERIA
───────────────────
  [ ] Opening utterance is recorded as a USER turn; Beacon produces ONE spoken
      reply and status becomes CONVERSING.
  [ ] Each user turn appends a USER turn + a spoken Beacon reply; history grows
      and is passed to the LLM so replies stay in context.
  [ ] A farewell ("bye", "that's all", "stop") ends the session: OUTCOME turn +
      status DONE.
  [ ] Every turn persisted via store.save(s); an LLM/transport error never crashes
      the turn — _fail() (or narrator's fallback) keeps the session graceful.

STARTER / PLACEHOLDER CODE
──────────────────────────
  # run_agent core:
  if s.goal and not _has_user_turn(s):
      s.say(TurnKind.USER.value, s.goal)
  s.status = SessionStatus.PLANNING.value; store.save(s)
  s.plan = make_plan(llm, s.goal)
  s.say(TurnKind.NARRATION.value, s.plan.confirm_question)   # opening reply
  s.status = SessionStatus.CONVERSING.value; store.save(s)

  # handle_reply core:
  s.say(TurnKind.USER.value, text); store.save(s)
  history = _history(s)
  if next_move(text, history) == "end":
      s.say(TurnKind.OUTCOME.value, closing_line(history))
      s.status = SessionStatus.DONE.value
  else:
      s.say(TurnKind.NARRATION.value, compose_reply(llm, history, s.plan))
      s.status = SessionStatus.CONVERSING.value
  store.save(s)
"""

import os

from .llm import LLMClient
from .models import SessionStatus, TurnKind
from .narrator import closing_line, compose_reply
from .navigator import next_move
from .planner import make_plan
from .store import SessionStore

# Reuse the same DB the server uses, so the dashboard sees your updates.
DB_PATH = os.environ.get("BEACON_DB", "beacon.db")


# ---------------------------------------------------------------------------
# Entry point 1 — the opening utterance (the goal field holds what was said).
# Called on a background thread by server.py for a brand-new Session.
# ---------------------------------------------------------------------------
def run_agent(session_id: str) -> None:
    store = SessionStore(DB_PATH)
    try:
        s = store.get(session_id)
        if not s:
            return

        if s.is_terminal():
            return
        if s.goal and not _has_user_turn(s):
            s.say(TurnKind.USER.value, s.goal)
        s.status = SessionStatus.PLANNING.value
        store.save(s)

        # make_plan catches both unavailable providers and malformed model output.
        s.plan = make_plan(_llm_or_none(), s.goal)
        s.say(TurnKind.NARRATION.value, s.plan.confirm_question)
        s.status = SessionStatus.CONVERSING.value
        store.save(s)
    except Exception as exc:  # noqa: BLE001
        _fail(store, session_id, exc)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Entry point 2 — every subsequent thing the user says.
# ---------------------------------------------------------------------------
def handle_reply(session_id: str, text: str) -> None:
    store = SessionStore(DB_PATH)
    try:
        s = store.get(session_id)
        if not s:
            return

        if s.is_terminal():
            return

        # Always record what the user said so the transcript is auditable.
        s.say(TurnKind.USER.value, (text or "").strip())
        store.save(s)

        history = _history(s)
        if next_move(text, history) == "end":
            s.say(TurnKind.OUTCOME.value, closing_line(history))
            s.status = SessionStatus.DONE.value
        else:
            s.say(TurnKind.NARRATION.value,
                  compose_reply(_llm_or_none(), history, s.plan))
            s.status = SessionStatus.CONVERSING.value
        store.save(s)
    except Exception as exc:  # noqa: BLE001
        _fail(store, session_id, exc)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Provided helpers — use these as-is.
# ---------------------------------------------------------------------------
def _history(s):
    """Build an OpenAI-style message list from the saved transcript.

    Pass this to narrator.compose_reply so each reply has the full context.
    (The narrator prepends its own system prompt — this returns only the
    user/assistant turns.)
    """
    msgs = []
    for t in s.transcript:
        if t.kind == TurnKind.USER.value:
            msgs.append({"role": "user", "content": t.text})
        elif t.kind in (TurnKind.NARRATION.value, TurnKind.OUTCOME.value):
            msgs.append({"role": "assistant", "content": t.text})
    return msgs


def _has_user_turn(s) -> bool:
    return any(t.kind == TurnKind.USER.value for t in s.transcript)


def _llm_or_none():
    """Keep deterministic fallbacks available when configuration is missing."""
    try:
        return LLMClient()
    except Exception:
        return None


def _fail(store: SessionStore, session_id: str, exc: Exception) -> None:
    s = store.get(session_id)
    if not s:
        return
    s.status = SessionStatus.ERROR.value
    s.say(TurnKind.OUTCOME.value, "Sorry — something went wrong and I had to stop.")
    s.say(TurnKind.SYSTEM.value, "error: %s" % exc)
    store.save(s)
