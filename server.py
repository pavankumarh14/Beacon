#!/usr/bin/env python3
"""
Beacon — web server SHELL (provided, working).
===============================================

Part of the working foundation. Serves the VOICE dashboard (real speech-to-text
and text-to-speech via the browser's built-in Web Speech API) and a small
storage-backed API (stdlib http.server only). It runs as-is: open the UI, speak
a goal, and see a Session persisted.

What it does NOT contain: the agent. Two clearly marked spots ("BUILD YOUR AGENT
HERE") show where you plug in planning/narration/navigation and where you handle
the user's spoken reply. Change anything here — it is a starting point.

Run it (use Chrome/Edge for voice):
    python3 server.py            # -> http://localhost:8002
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from beacon.models import Session, TurnKind
from beacon.store import SessionStore

DB_PATH = os.environ.get("BEACON_DB", "beacon.db")
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run_agent(session_id: str) -> None:
    """
    ============================  BUILD YOUR AGENT HERE  ============================
    Entry point: your voice web-access agent starts working on a spoken goal
    (invoked on a background thread when a Session is created).

    The real implementation lives in beacon/agent.py (a CANDIDATE SCAFFOLD full of
    TODOs) so the server stays a thin shell. The flow you build there:
      1. Plan the steps from the goal with an LLM (beacon.planner).
      2. Confirm understanding via a CONFIRM turn and wait for the user's reply.
      3. Drive the site step by step (beacon/sites: MockSite now, a real
         PlaywrightSite later), narrating each page (beacon.narrator).
      4. BEFORE any consequential action, add a CONFIRM turn and wait for an
         explicit spoken "yes" (beacon.consequence — deterministic gate).
      5. Read back the outcome + confirmation number; persist with store.save(s).

    Restructure freely — beacon/agent.py is a suggested skeleton, not a contract.
    --------------------------------------------------------------------------------
    """
    from beacon.agent import run_agent as _run_agent
    try:
        _run_agent(session_id)
    except NotImplementedError as todo:
        # Scaffold default: server stays up and the goal is persisted; no agent
        # work happens until you implement beacon/agent.py. Remove once built.
        print("[beacon] run_agent not implemented yet:", todo)


def handle_reply(session_id: str, text: str) -> None:
    """
    ====================  BUILD YOUR AGENT HERE (spoken replies)  ===================
    Called when the user speaks/types a reply (e.g. "yes" / "no" / a correction).
    Delegates to beacon/agent.py:handle_reply, where your agent decides what the
    reply means — especially whether a pending consequential action is approved.

    Until you implement it, the fallback below just records the reply so the
    conversation isn't lost.
    --------------------------------------------------------------------------------
    """
    from beacon.agent import handle_reply as _handle_reply
    try:
        _handle_reply(session_id, text)
    except NotImplementedError as todo:
        print("[beacon] handle_reply not implemented yet:", todo)
        store = SessionStore(DB_PATH)
        try:
            s = store.get(session_id)
            if s:
                s.say(TurnKind.USER.value, text)
                store.save(s)
        finally:
            store.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
        if path == "/api/sessions":
            store = SessionStore(DB_PATH)
            try:
                return self._json([{"session_id": s.session_id, "status": s.status,
                                    "goal": s.goal, "updated_at": s.updated_at}
                                   for s in store.list()])
            finally:
                store.close()
        if path.startswith("/api/sessions/"):
            store = SessionStore(DB_PATH)
            try:
                s = store.get(path[len("/api/sessions/"):])
                return self._json(s.to_dict() if s else {"error": "not found"}, 200 if s else 404)
            finally:
                store.close()
        return self.send_error(404)

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/sessions":
            s = Session(goal=self._body().get("goal", ""))
            store = SessionStore(DB_PATH)
            store.save(s)
            store.close()
            threading.Thread(target=run_agent, args=(s.session_id,), daemon=True).start()
            return self._json({"session_id": s.session_id})
        if path.startswith("/api/sessions/") and path.endswith("/respond"):
            sid = path[len("/api/sessions/"):-len("/respond")]
            text = self._body().get("text", "")
            threading.Thread(target=handle_reply, args=(sid, text), daemon=True).start()
            return self._json({"ok": True})
        return self.send_error(404)


def main():
    load_dotenv()
    port = int(os.environ.get("PORT", "8002"))
    print("Beacon voice dashboard at http://localhost:%d  (use Chrome/Edge; Ctrl+C to stop)" % port)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
