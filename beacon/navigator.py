"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  navigator.py · next_move()                                — CANDIDATE TASK  ║
╚══════════════════════════════════════════════════════════════════════════════╝

OBJECTIVE
─────────
Steer the FLOW of the conversation. After each thing the user says, decide what
Beacon should do next: keep the conversation going, or wrap it up because the
user is done. This is the small, deterministic control layer around the chatty
LLM — the part that guarantees the user can always end the session.

WHAT TO BUILD
─────────────
next_move(text, history=None) -> str
  * Return "end"      if the user is saying goodbye / wants to stop ("bye",
                      "that's all", "thanks, I'm done", "stop", "exit").
  * Return "continue" otherwise (the normal case — Beacon should reply and keep
                      the conversation going).
  * The goodbye / stop detection MUST be DETERMINISTIC (a plain keyword/phrase
    check) — never left to the LLM. That is the graded trust boundary: a model
    must never be able to trap the user in a conversation they asked to leave. An
    LLM may ONLY be used as an extra signal for genuinely ambiguous input, and
    only to ADD an end, never to override a clear stop word.

EXAMPLE (no LLM needed for the core path)
─────────────────────
  _GOODBYE = ("bye", "goodbye", "see you", "that's all", "thats all",
              "that is all", "i'm done", "im done", "stop", "exit", "quit",
              "nothing else")

HOW TO WIRE IT IN
─────────────────
Called by beacon/agent.py:handle_reply() once per user turn:
    if next_move(text, history) == "end":
        s.say(TurnKind.OUTCOME.value, closing_line(history)); s.status = DONE
    else:
        s.say(TurnKind.NARRATION.value, compose_reply(llm, history, s.plan))
        s.status = CONVERSING

ACCEPTANCE CRITERIA
───────────────────
  [ ] Clear farewells ("bye", "that's all", "stop") -> "end", deterministically.
  [ ] Ordinary input -> "continue".
  [ ] The stop decision does not depend on the LLM being reachable.
  [ ] Reasonably robust to noisy speech-to-text ("thanks bye", "ok I'm done now").

STARTER / PLACEHOLDER CODE
──────────────────────────
  t = (text or "").strip().lower()
  if any(g in t for g in _GOODBYE):
      return "end"
  return "continue"
"""

import re
from typing import List, Dict, Optional

from .llm import LLMClient  # available if you want an LLM tie-breaker for ambiguity


# Phrases that deterministically end the conversation.
_GOODBYE = (
    "bye", "goodbye", "good bye", "see you", "that's all", "thats all",
    "that is all", "i'm done", "im done", "stop", "exit", "quit", "nothing else",
)


def next_move(text: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    # This intentionally does not call an LLM.  Speech transcription is noisy,
    # so match normalised phrases and standalone one-word exit commands.
    normalized = " ".join((text or "").lower().replace("’", "'").split())
    if any(re.search(r"(?<!\w)%s(?!\w)" % re.escape(phrase), normalized)
           for phrase in _GOODBYE):
        return "end"
    return "continue"
