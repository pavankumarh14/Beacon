"""
Core data models for Beacon.
============================

The unit of work is a *Session*: a spoken goal pursued on the web through a
narrated, confirmation-gated conversation. Everything serialises to/from JSON so
it can be persisted (store.py) — the local stand-in for Cosmos DB.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class SessionStatus(str, Enum):
    NEW = "new"
    PLANNING = "planning"
    CONFIRMING_INTENT = "confirming_intent"     # "you want to pay your bill — right?"
    NAVIGATING = "navigating"
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # consequential action: spoken yes?
    CONVERSING = "conversing"   # chat mode: Beacon replied, it's the user's turn to speak
    DONE = "done"
    ABANDONED = "abandoned"
    ERROR = "error"


class TurnKind(str, Enum):
    USER = "user"             # what the user said/typed
    NARRATION = "narration"   # Beacon describing a page / step  (spoken)
    CONFIRM = "confirm"       # Beacon asking for spoken consent  (spoken)
    ACTION = "action"         # internal log of a browser action taken
    OUTCOME = "outcome"       # final read-back (confirmation numbers etc.)  (spoken)
    SYSTEM = "system"


# kinds the voice UI should speak aloud
SPOKEN_KINDS = {TurnKind.NARRATION.value, TurnKind.CONFIRM.value, TurnKind.OUTCOME.value}


@dataclass
class Turn:
    kind: str
    text: str
    ts: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """One control the agent can operate on the current page."""
    id: str
    label: str
    target: str = ""             # page id this leads to (mock site)
    consequential: bool = False  # site-declared hint; classifier also infers
    effect: str = ""             # plain-language effect, e.g. "Pay ₹1,240 to ..."


@dataclass
class PageState:
    """What the agent perceives on the current page (the grounding input)."""
    page_id: str
    title: str
    description: str = ""
    fields: Dict[str, str] = field(default_factory=dict)   # label -> value
    actions: List[Action] = field(default_factory=list)
    terminal: bool = False
    outcome: Dict[str, str] = field(default_factory=dict)   # final read-back data

    def action_by_id(self, action_id: str) -> Optional[Action]:
        for a in self.actions:
            if a.id == action_id:
                return a
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    """Output of the Planner agent."""
    intent: str = ""                 # one-line restatement of the goal
    steps: List[str] = field(default_factory=list)
    confirm_question: str = ""       # "You want to pay your electricity bill — is that right?"


@dataclass
class Session:
    goal: str
    site_name: str = "bill_pay"
    session_id: str = field(default_factory=lambda: "sess_" + uuid.uuid4().hex[:10])
    status: str = SessionStatus.NEW.value
    plan: Optional[Plan] = None
    transcript: List[Turn] = field(default_factory=list)
    current_page: Optional[Dict[str, Any]] = None      # snapshot of PageState
    pending_action: Optional[Dict[str, Any]] = None    # Action awaiting confirmation
    action_log: List[str] = field(default_factory=list)
    outcome: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def say(self, kind: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Turn:
        t = Turn(kind=kind, text=text, meta=meta or {})
        self.transcript.append(t)
        self.updated_at = time.time()
        return t

    def is_terminal(self) -> bool:
        return self.status in (SessionStatus.DONE.value, SessionStatus.ABANDONED.value,
                               SessionStatus.ERROR.value)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Session":
        d = dict(d)
        if d.get("plan"):
            d["plan"] = Plan(**d["plan"])
        d["transcript"] = [Turn(**t) for t in d.get("transcript", [])]
        known = {f for f in Session.__dataclass_fields__}  # type: ignore[attr-defined]
        return Session(**{k: v for k, v in d.items() if k in known})
