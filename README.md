# Beacon — Voice-to-Plan Concierge

Beacon is a voice-first conversational concierge for multi-step goals. It keeps
the goal and the details gathered so far in context, asks only the information
needed to make a useful plan, presents choices, and saves the user's confirmed
decision. The user can end at any time with *"bye"* or *"stop"*; the full
transcript persists for audit.

Beacon is a single Python web service. Its browser dashboard uses the Web Speech
API for speech input and output, while the backend persists the structured plan,
selection, confirmation, and final receipt in SQLite.

## Code repository

https://github.com/pavankumarh14/Beacon

## How Codex and GPT-5.6 were used

Codex, powered by GPT-5.6, was used as a development collaborator throughout
the project. It helped inspect the initial proposal and implementation, map the
proposal into the voice-to-plan state machine, implement and review the Python,
browser, Docker, and Render configuration changes, and run focused end-to-end
checks of planning, confirmation, persistence, and deterministic exit behavior.

It was also used to diagnose provider configuration failures, improve the
structured LLM-planning prompt and fallback handling, refine the voice UI
behavior, and update this documentation. Design decisions, API keys, deployment
configuration, and final product choices remain under developer control; secrets
are never placed in the repository.

---

## Table of contents
- [Quick start](#quick-start)
- [Code repository](#code-repository)
- [How Codex and GPT-56 were used](#how-codex-and-gpt-56-were-used)
- [Architecture](#architecture)
- [Voice-to-plan workflow](#voice-to-plan-workflow)
- [Using a different LLM](#using-a-different-llm)

---

## Quick start

**Requirements:** Python 3.8+. Use **Chrome or Edge** for voice; the text box
works in any browser. An LLM key is optional for the current deterministic
outing workflow, and can be configured as described below for future
personalisation.

```bash
# Optional: add an LLM key for your chosen provider.
cp .env.example .env

# 2) Run the server (serves the dashboard + storage API).
python3 server.py           # -> http://localhost:8002
```

Open <http://localhost:8002>, click **Speak**, and just talk to Beacon. Say
*"bye"* when you're done.

### Best demo flows

Try any of these: **“Plan dinner for four tonight,” “Plan a weekend trip,” “Help
me choose a birthday gift,”** or **“Help me prepare for a Python interview.”**
Answer the short domain-specific questions, choose one of the three AI-generated option cards,
and say **“yes”** to save the final plan. The receipt clearly states that it is a
saved plan, not a live reservation or other external action.

Beacon is intentionally not a general-answer chatbot. For a broad request such
as “Explain quantum computing,” it will clarify the desired outcome, timeframe,
constraints, and preferences, then create a practical learning plan. This keeps
the experience faithful to Beacon’s goal-tracking design.

## Voice-to-plan workflow

1. Speak a goal, such as “Plan dinner for four tonight” or “Plan a weekend trip.”
2. Beacon detects the planning domain and collects its missing details.
3. It shows three **AI-generated planning suggestions**; it never claims live availability.
4. Choose an option by voice or button, then say **yes** to save the plan.
5. Beacon displays a final receipt with the chosen approach, plan details, and next steps.
6. Download the receipt as a PDF to share or keep as the record of the decision.

For dining goals, Beacon also attempts a live, no-key OpenStreetMap place search
after it has the area and preferences. Live cards identify OpenStreetMap as their
source and link to the place page; if the public service is unavailable, Beacon
uses clearly marked demo cards instead.

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
