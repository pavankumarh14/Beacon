# Beacon — Voice-First Conversational Concierge (Hackathon Starter Kit)

> **Theme: Voice agents.** Beacon is a warm, voice-first concierge. A user
> **speaks** about anything they want help with — *"book a restaurant for four
> tonight"*, *"help me plan a weekend trip"*, *"pick a birthday gift for my dad"* —
> and Beacon **talks them through it**, turn by turn, until they're done.

**Beacon** listens, replies aloud in plain spoken language, asks the one or two
most useful questions, gives concrete suggestions, and keeps the conversation
moving. The user stays in control: they can end the conversation at any time with
a simple *"bye"* or *"stop"*, and the full transcript persists for audit.

You are given a **working foundation** — a dashboard that does **real speech in
the browser** (Web Speech API: STT + TTS, free, no install), a provider-agnostic
LLM client, data models, and a SQLite store. **You build the agent brain: 4 core
AI-logic files** (see [What YOU build](#what-you-build-4-core-ai-logic-files)).
Each is a **scaffold with `TODO` markers** sketching a suggested design — you may
follow it or restructure entirely.

---

## Table of contents
- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Request / data flow](#request--data-flow)
- [The conversation state machine](#the-conversation-state-machine)
- [What's PROVIDED (~50%, working)](#whats-provided-50-working)
- [What YOU build (4 core AI-logic files)](#what-you-build-4-core-ai-logic-files)
- [Scaffold map](#scaffold-map)
- [Using a different LLM](#using-a-different-llm)

---

## Quick start

**Requirements:** Python 3.8+ and **no `pip install`** for the core — the
foundation is standard-library only. Use **Chrome or Edge** for voice (the text
box works in any browser). A working prototype LLM key is pre-filled in `.env`
(shared quota — replace it with your own for heavy use; see "Using a different
LLM").

```bash
# 1) Point Beacon at an LLM (or just use the provided .env).
cp .env.example .env

# 2) Run the server (serves the dashboard + storage API).
python3 server.py           # -> http://localhost:8002
```

Open <http://localhost:8002>, click **Speak**, and just talk to Beacon. Say
*"bye"* when you're done.

Beacon records the conversation, plans an opening response, continues with the
full transcript as context, and closes deterministically when the user says
"bye", "stop", or a similar farewell.

---

## Deploy on Render (Docker)

Beacon is one web service: `server.py` serves both the browser frontend in
`web/` and the backend API. The included `Dockerfile` installs Python
dependencies and starts that single service; no separate frontend deployment is
needed.

1. Push this project, including `Dockerfile`, `.dockerignore`, and
   `render.yaml`, to GitHub.
2. In Render, select **New → Blueprint** and choose the repository. Render will
   read `render.yaml`, build the Docker image, and create the web service.
3. In Render's Environment settings, add your model configuration and API key
   using the table below. Keep the key out of Git and never place it in the
   Dockerfile.
4. Deploy and open the generated `onrender.com` URL. Use Chrome or Edge for
   microphone input; typed chat works in other browsers.

### Database

No database service or migration is required. Beacon uses SQLite and creates
the `beacon.db` file and its tables automatically on first request. The Blueprint
mounts a 1 GB persistent disk at `/var/data`, where that file is stored, so
transcripts survive restarts and deploys. Persistent disks require a Render plan
that supports them. If you intentionally deploy without a disk, set
`BEACON_DB=beacon.db`; the app still works, but its conversation history is
discarded when the instance is replaced.

Beacon retains the three most recently updated sessions by default
(`BEACON_MAX_HISTORY=3`). Each retained session includes its full transcript.
When a fourth session is saved, the oldest session and transcript are removed.

### Choose any supported model provider

Set `BEACON_LLM_PROVIDER`, `BEACON_LLM_MODEL`, and `BEACON_LLM_API_KEY` in
Render. The key is always stored in `BEACON_LLM_API_KEY`, regardless of the
provider. The model name can be any model that your provider makes available to
your account.

| Provider | `BEACON_LLM_PROVIDER` | Extra setting |
| --- | --- | --- |
| OpenAI | `openai` | None |
| Anthropic | `anthropic` | None |
| Groq | `groq` | None |
| DeepSeek | `deepseek` | None |
| Gemini | `gemini` | None |
| Grok / xAI | `xai` | None |
| Any OpenAI-compatible API | `openai_compatible` | Set `BEACON_LLM_BASE_URL` to its API base URL. |

For example, a Gemini deployment uses `gemini`, your Gemini API key, and a
Gemini model ID. An unsupported proprietary API needs a small adapter in
`beacon/llm.py`; it cannot be used only by supplying a key. Ollama is supported
for local development but is not appropriate for a standard Render web service
unless you run an Ollama server separately.

### If Beacon keeps saying it did not catch you

That response is the safe fallback when the model provider rejects or cannot
complete a request; it is not normally a microphone problem. Open your Render
service's **Logs** after trying a conversation. Beacon now logs the precise
provider error there.

For Groq, set only these model variables and remove `BEACON_LLM_BASE_URL` if it
was previously added for Gemini or another provider:

```text
BEACON_LLM_PROVIDER=groq
BEACON_LLM_MODEL=llama-3.3-70b-versatile
BEACON_LLM_API_KEY=your_groq_key
```

---

## Architecture

Beacon is split into a thin **transport/UI shell** (provided) and an **agent
brain** (you build).

```
Legend:  [PROVIDED] = ready to use      [YOU BUILD] = the 4 candidate files

        ┌──────────────────────────────────────────────────────────────┐
        │ 1. BROWSER   —   web/index.html              [PROVIDED]      │
        │    Web Speech API: speech-to-text + text-to-speech           │
        │    Speaks each reply aloud, re-opens the mic for your turn   │
        │    Text box + speaking-speed slider; polls the server ~1.2s  │
        └──────────────────────────────────────────────────────────────┘
        │  POST goal / reply (HTTP JSON)      ▲  JSON transcript
        ▼                                    │  (status + turns)
        ┌──────────────────────────────────────────────────────────────┐
        │ 2. HTTP SHELL   —   server.py                [PROVIDED]      │
        │    POST /api/sessions            create + run_agent()        │
        │    POST /api/sessions/<id>/respond  -> handle_reply()        │
        │    GET  /api/sessions[/<id>]      read saved state           │
        └──────────────────────────────────────────────────────────────┘
        │  run_agent() / handle_reply()       ▲  store.save / get
        ▼                                    │
        ┌──────────────────────────────────────────────────────────────┐
        │ 3. AGENT BRAIN   —   beacon/agent.py        [YOU BUILD]      │
        │    record turn -> plan -> reply -> (continue ⇄ end)          │
        │                                                              │
        │    helpers it calls:                                         │
        │      planner.py    goal  -> Plan            [YOU BUILD]      │
        │      narrator.py   history -> spoken reply  [YOU BUILD]      │
        │      navigator.py  utterance -> continue/end[YOU BUILD]      │
        └──────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
           ┌──────────────────┐  ┌────────────────────────────────────┐
           │ beacon/llm.py    │  │ beacon/store.py + beacon/models.py │
           │ chat / chat_json │  │ SQLite session + transcript store  │
           │ [PROVIDED]       │  │ [PROVIDED]                         │
           └──────────────────┘  └────────────────────────────────────┘
```

**Why this shape?** The LLM does the **understanding and talking**, but the small
decision *"is the user done?"* is **deterministic code** (`navigator.py`), never
the model. That keeps a clear trust boundary: a chatty model can never trap the
user in a conversation they asked to leave.

---

## Request / data flow

1. User speaks an opening request → browser STT → `POST /api/sessions {goal}`.
2. `server.py` creates a `Session` (status `new`), persists it, and starts
   `run_agent(session_id)` on a daemon thread.
3. The agent records the utterance, **plans** the conversation (LLM), and speaks
   an **opening reply**, setting status `conversing` and saving.
4. The browser polls `GET /api/sessions/<id>`, **speaks the reply aloud**, and
   re-opens the mic for the user's next turn.
5. User speaks again → `POST /api/sessions/<id>/respond {text}` → `handle_reply`.
6. The agent decides **continue vs end** (`navigator.py`); if continuing, it
   composes the next spoken reply (`narrator.py`) with the full history and stays
   `conversing`.
7. When the user says a farewell, the agent speaks a closing line, sets status
   `done`, and the full transcript persists in SQLite for audit.

---

## The conversation state machine

`SessionStatus` (in `beacon/models.py`) is the contract between agent and UI:

```
 new → planning → conversing ⇄ (user speaks) ⇄ conversing → done
                                                      └────► error  (unrecoverable)
```

The dashboard speaks turns of kind `narration` and `outcome`, and re-opens the
mic whenever status is `conversing`.

---

## What's PROVIDED (~50%, working)

| Component | File | What it does |
|---|---|---|
| **Voice dashboard** | `web/index.html` | Speaks each reply aloud, listens for the next thing you say (browser Web Speech API, Chrome/Edge), text fallback, speaking-speed slider, polls + renders the transcript |
| **Server shell** | `server.py` | Serves the UI + a stdlib storage API; spawns the agent on a thread; **delegates `run_agent`/`handle_reply` to `beacon/agent.py`** |
| **LLM client** | `beacon/llm.py` | Provider-agnostic chat. `chat()` → text, `chat_json()` → dict. OpenAI/Claude/Groq/DeepSeek/Ollama. Verified working. |
| **Data models** | `beacon/models.py` | `Session`, `Turn`, `Plan`, `SessionStatus`, `TurnKind` |
| **Persistence** | `beacon/store.py` | SQLite session + transcript store (auditable) |
| **Examples / config** | `examples/goals.txt`, `.env` | Sample spoken requests; a working prototype LLM key |

---

## What YOU build (4 core AI-logic files)

The **agent brain** — the AI intelligence and the conversational loop — in
exactly four files: `planner.py`, `narrator.py`, `navigator.py`, and `agent.py`.
A strong submission should:

1. **Understand the request** from the opening utterance (LLM, `planner.py`) and
   open with a warm, useful first reply.
2. **Talk like a concierge** (`narrator.py`): one to three short, spoken-friendly
   sentences per turn, with the full conversation history in context — and a
   **deterministic** closing line so the session always ends gracefully.
3. **Steer the flow** (`navigator.py`): after each user turn, decide **continue
   vs end** — with **deterministic** goodbye detection so the user can always stop.
4. **Orchestrate the loop** (`agent.py`): the `SessionStatus` state machine,
   recording every turn, and tying planner + narrator + navigator together. The
   full transcript is auditable.

### Where to build what (file by file)

Each file has `TODO`s at exactly the decision points. Build them roughly in this
order — you can test each against the dashboard as you go.

#### 1. `beacon/planner.py` → `make_plan(llm, goal) -> Plan`
Turn the opening utterance into a small `Plan` (`beacon/models.py`): a restated
`intent`, the one or two `steps`/questions worth covering, and a warm opening
line (`confirm_question`). Call `llm.chat_json(...)`. Fall back to a safe generic
`Plan` if the LLM output is malformed — never crash the session.

#### 2. `beacon/narrator.py` → `compose_reply(...)` + `closing_line(...)`
- `compose_reply(llm, history, plan)`: the next spoken reply (LLM) — one to three
  natural sentences, written for the ear; fall back to a friendly canned line on
  any LLM failure.
- `closing_line(history)`: **deterministic** — a warm farewell built without the
  LLM, so the conversation always ends gracefully.

#### 3. `beacon/navigator.py` → `next_move(text, history) -> "continue" | "end"`
Decide whether to keep chatting or wrap up. The goodbye/stop detection must be
**deterministic** (plain keyword/phrase check), never left to the LLM — an LLM may
only be an extra signal for genuinely ambiguous input.

#### 4. `beacon/agent.py` → `run_agent(session_id)` + `handle_reply(session_id, text)`
The orchestrator: record the opening utterance, plan it, and speak the opening
reply (`conversing`); then on each turn record what the user said, ask the
navigator continue-vs-end, and either reply (`narrator`) or close out (`done`).
Save after every state change; keep the turn graceful on any error.

### Design rule (graded)
Let the LLM **understand and talk** — but the decision *"is the user done?"* is
**deterministic code** (`navigator.py`), and the **closing line**
(`narrator.closing_line`) is deterministic too. That trust boundary is the heart
of this problem: the user must always be able to end the conversation, even if the
model misbehaves or is unreachable.

---

## Scaffold map

These files are a **suggested skeleton** — control flow is sketched and every
decision point is a `TODO`. Implement them, or delete and design your own. The
server runs as-is until you start filling them in.

| File | Status | Your job |
|---|---|---|
| `beacon/agent.py` | scaffold | Orchestrator: `run_agent()` + `handle_reply()`, the state machine, the record→plan→reply→(continue/end) loop |
| `beacon/planner.py` | scaffold | `make_plan(goal) → Plan` (LLM): intent, steps, opening line |
| `beacon/narrator.py` | scaffold | `compose_reply()` (LLM, plain spoken language) + `closing_line()` (deterministic) |
| `beacon/navigator.py` | scaffold | `next_move(text) → continue/end` (deterministic goodbye detection) |

Find every task quickly:

```bash
grep -rn "TODO" beacon/
```

---

## Using a different LLM (GPT / Claude / Groq / DeepSeek / local)

Everything goes through `LLMClient` in `beacon/llm.py` — for most providers you
change **only `.env`**:

```bash
BEACON_LLM_PROVIDER=openai     BEACON_LLM_API_KEY=sk-...      BEACON_LLM_MODEL=gpt-4o-mini
BEACON_LLM_PROVIDER=groq       BEACON_LLM_API_KEY=gsk_...     BEACON_LLM_MODEL=llama-3.3-70b-versatile
BEACON_LLM_PROVIDER=deepseek   BEACON_LLM_API_KEY=sk-...      BEACON_LLM_MODEL=deepseek-chat
BEACON_LLM_PROVIDER=ollama     BEACON_LLM_MODEL=llama3.1      # local, free, no key
BEACON_LLM_PROVIDER=anthropic  BEACON_LLM_API_KEY=sk-ant-...  BEACON_LLM_MODEL=claude-sonnet-4-6
```

- **OpenAI-compatible providers** (Groq, DeepSeek, Together, Ollama, vLLM): env
  vars only — no code changes.
- **Anthropic Claude**: built-in adapter (`_chat_anthropic`).
- **A brand-new provider**: add one entry to `PROVIDERS` in `llm.py`
  (`"format":"openai"` if OpenAI-compatible, else add a small `_chat_<name>()`).
- **Prefer an official SDK?** Fine — keep the same `chat` / `chat_json` entry
  points so your code stays provider-agnostic.
- **JSON-mode note:** `chat_json` requests `response_format=json_object` and also
  strips ```` ```json ```` fences; remove the field in `_chat_openai` if a
  provider rejects it.
