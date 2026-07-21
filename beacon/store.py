"""
Session store (SQLite).
=======================

Simplified local stand-in for Azure Cosmos DB: each Session (goal, full narration
+ action log, outcome) persisted as JSON keyed by session_id, so the auditable
log survives the process exiting and can be reviewed by the user or a trusted
helper later. Stdlib `sqlite3` only.
"""

import json
import time
from typing import List, Optional
import sqlite3

from .models import Session


class SessionStore:
    def __init__(self, path: str = "beacon.db"):
        self.path = path
        self._conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=8000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                status     TEXT,
                goal       TEXT,
                updated_at REAL,
                data       TEXT
            )
            """
        )
        self._conn.commit()

    def save(self, s: Session) -> None:
        s.updated_at = time.time()
        self._conn.execute(
            "REPLACE INTO sessions (session_id, status, goal, updated_at, data) VALUES (?,?,?,?,?)",
            (s.session_id, s.status, s.goal, s.updated_at, json.dumps(s.to_dict())),
        )
        self._conn.commit()

    def get(self, session_id: str) -> Optional[Session]:
        row = self._conn.execute(
            "SELECT data FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return Session.from_dict(json.loads(row[0])) if row else None

    def list(self) -> List[Session]:
        rows = self._conn.execute(
            "SELECT data FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [Session.from_dict(json.loads(r[0])) for r in rows]

    def close(self) -> None:
        self._conn.close()
