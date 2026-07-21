# **Beacon** 

### _A voice-first conversational concierge that thinks with you, not for you_ 

Suggested stack: LLM (any) · Web Speech API · FastAPI · SQLite · Python  ·  Optional MS: Azure Cognitive Services · Azure OpenAI · Cosmos DB 

## **Problem Statement** 

#### **Problem Background** 

People increasingly interact with AI assistants that respond to a single prompt and stop — generating a wall of text the user must parse, evaluate, and act on alone. Voice is the most natural interface humans have, yet most AI tools treat it as a thin wrapper over a text box. The result is one-shot answers that miss context, skip clarifying questions, and leave the user to drive every step themselves. There is no system that listens to a spoken goal, builds a shared mental model with the user turn by turn, and keeps talking until the task is actually done. 

#### **Why It Matters** 

Single-shot AI responses fail at open-ended tasks — booking, planning, choosing, drafting — because those tasks require iteration, clarification, and progressive narrowing of options. Users are forced to re-prompt repeatedly, copy-paste outputs into other tools, and stitch together a plan the AI abandoned after one turn. Voice is discarded as a novelty when the underlying model has no conversational memory or goal-tracking. This is exactly the kind of interaction poverty an AI-first assistant should eliminate: the user should be able to speak a goal and be walked through it, not handed a monologue and left alone. 

## **Solution Summary** 

#### **Why This Problem Was Chosen** 

An AI-first assistant should feel like talking to a knowledgeable friend, not querying a search engine. The gap between what voice AI promises and what it delivers is largest precisely at multi-step, open-ended tasks — the tasks that matter most to users. Beacon targets that gap directly: a conversational loop that plans, narrates, and navigates until the user says they are done. 

#### **Proposed Solution** 

Beacon is a voice-to-plan concierge. The user speaks a goal — “plan dinner for four tonight,” “plan a weekend trip,” “help me choose a birthday gift,” or “prepare for a Python interview” — and Beacon identifies the planning domain before collecting only the details that make the plan useful. It presents three clearly labelled demo recommendations, lets the user select one, and requires an explicit “yes” before saving the final plan receipt. Every exchange is persisted to SQLite so the decision is auditable. The user can end naturally — by saying “bye” or “stop” — because exit detection and the closing line are deterministic code, never delegated to the model. 

#### **Expected Impact** 

- Eliminate single-shot AI failure on multi-step tasks by sustaining a structured dialogue until the goal is reached. 

- Make voice a first-class interface, not a text-box wrapper — users speak naturally and hear practical, context-aware guidance. 

- Persist every conversation as an auditable transcript, giving users a record of what was decided and why. 

- A trust boundary that guarantees the user can always end the session — deterministic exit logic, never delegated to the model. 

## **Technical Approach & Implementation** 

#### **Solution Workflow** 

1. User speaks a goal in the browser. The Web Speech API transcribes it and POST /api/sessions is called. 

2. The server creates a Session record (status: new), spawns a background thread, and calls run_agent(session_id). 

3. The agent records the goal as a USER turn, calls make_plan(llm, goal) → Plan (intent, steps, confirm_question), and speaks an opening NARRATION turn. Status → conversing. 

4. The browser polls GET /api/sessions/<id>, speaks the NARRATION aloud via TTS, then re-opens the microphone for the next user turn. 

5. The user speaks a reply → POST /api/sessions/<id>/respond. handle_reply records the USER turn and calls next_move(text, history). 

6. If next_move returns “end” (goodbye keywords detected), the agent emits a deterministic closing OUTCOME turn and sets status done. 

7. If next_move returns “continue”, compose_reply(llm, history, plan) produces the next spoken reply and the loop repeats from step 4. 

8. Every turn is immediately persisted to SQLite. LLM or transport errors never crash the server — a _fail() handler records the error turn and keeps the session alive. 

#### **Key Features** 

**Domain-Aware Voice-to-Plan Workflow.** Beacon turns dining, travel, gifting, study, and open-ended goals into structured details, three transparent demo options, an explicit selection, and a saved plan receipt — not just a chat response. 

**Spoken-First Narration.** Replies are written for the ear: 1–3 sentences, no markdown, no bullet lists — warm, practical, and spoken-friendly. 

**Deterministic Exit Guard.** Stop words (“bye”, “stop”, “that’s all”) are detected with deterministic keyword matching, never delegated to the LLM. The user can always leave, even if the model is unreachable. 

**Persistent, Bounded History.** The full transcript and final plan receipt are written to SQLite, while only the three most recent sessions are retained. 

**Provider-Agnostic LLM Layer.** Switch between OpenAI, Anthropic Claude, Groq, DeepSeek, and Ollama by changing a single environment variable. No code change required. 

**Zero-Install Voice Interface.** The browser UI uses the Web Speech API for both speech-to-text and text-to-speech — free, zero-install, works in Chrome and Edge out of the box. 

## **Technology Stack** 

#### **Frontend** 

- HTML5 + Web Speech API (STT + TTS) — no third-party voice SDK required 

- Plain JavaScript with fetch-based polling (~200 lines) 

- Dark-themed responsive UI with speaking-speed slider and manual text fallback 

#### **Backend** 

- Python 3.8+ with stdlib foundation (http.server, threading, sqlite3, urllib) 

- FastAPI + Uvicorn (optional modern HTTP layer) 

- SQLite for session and transcript persistence 

- Background threading for non-blocking agent execution 

#### **AI / ML** 

- LLM via provider-agnostic LLMClient — chat() for text, chat_json() for structured output 

- Planner: LLM-based goal decomposition → Plan (intent, steps, confirm_question) 

- Narrator: LLM-based reply composer producing spoken-friendly 1–3 sentence turns 

- Navigator: deterministic keyword check with optional LLM tie-breaking for ambiguous phrasing 

#### **Data & Integrations** 

- SQLite session store with CRUD via SessionStore 

- Turn kinds: user, narration, confirm, action, outcome, system 

- Azure Cognitive Services (optional enhanced speech) 

- Supports OpenAI, Anthropic, Groq, DeepSeek, Ollama via environment config 

## **Models & Algorithms** 

**Goal Decomposition.** The LLM receives the raw spoken goal and produces a structured Plan object — intent, ordered steps, and a warm opening question — using chat_json() for deterministic schema compliance. Graceful fallback is applied on LLM failure. 

**History Reconstruction.** The full conversation history (OpenAI message format) is rebuilt from the persisted transcript on every turn, giving the LLM complete context without in-memory state. 

**Deterministic Navigation.** Keywords (“bye”, “stop”, “done”, “that’s all”, “goodbye”, “exit”, “quit”, “no more”) are matched first. The LLM is invoked only when the intent is genuinely ambiguous — and even then the deterministic check takes precedence. 

**Contextual Reply Composition.** The Narrator receives the full message history plus the Plan and is instructed to produce a single spoken reply that advances the goal by one step, never re-asking answered questions and always moving the conversation forward. 

## **Innovation** 

**Goal-tracking conversational loop.** Beacon is not a Q&A chatbot. Every session has a Plan with explicit steps, and every Narrator turn advances one of those steps — so the conversation has direction, not just flow. 

**Hard trust boundary at the exit.** The rule is simple and load-bearing: the LLM decides what to say, but the user decides when to stop. Exit detection is code, not prompt, so it cannot be hallucinated or refused. 

**Voice-native reply design.** Replies are composed as speech, not text — short, warm, no formatting — so the experience sounds natural rather than like a document being read aloud. 

**Minimal, composable agent architecture.** The entire agent brain is defined by four small, replaceable files (planner, narrator, navigator, agent). The infrastructure — transport, persistence, LLM client, voice UI — is pre-built and stable. 

## **Future Scope** 

#### **Near-term** 

- Tool-use integration — let Beacon call external APIs (restaurant booking, calendar, search) mid-conversation to take real actions, not just give advice 

- Streaming responses — emit partial TTS audio as the LLM generates tokens, reducing perceived latency between turns 

- Session resume — return to an in-progress conversation from a previous browser session by replaying the persisted transcript 

#### **Medium-term** 

- Multi-modal input — accept photos or file uploads alongside voice so Beacon can reason over visual context (e.g. a restaurant menu, a product image) 

- Personalisation layer — a lightweight user profile that remembers preferences across sessions (dietary restrictions, travel style, budget range) 

- Confidence-gated suggestions — when the Planner detects low certainty it asks a targeted clarifying question before committing to a step, reducing wrong-path conversations 

#### **Long-term** 

- Proactive nudges — Beacon re-opens a conversation when a time-sensitive step approaches (e.g. “Your reservation window is closing — shall I book now?”) 

- Org-wide deployment — shared Beacon instances for teams, with role-based goals (onboarding, incident triage, customer support) and team-level transcript analytics 

- Cross-session knowledge graph — link related sessions so Beacon can say “last time you planned a trip you preferred boutique hotels” without being told again 

## **Scalability & Larger Vision** 

#### **How It Scales** 

Beacon is designed to scale along three independent axes without re-architecting the core. 

**Technically** , each session is stateless between turns: the transcript is the only state, and it lives in SQLite (or any CRUD store). The agent thread is spawned per session and exits cleanly. Moving from SQLite to a distributed database like Cosmos DB requires changing one store adapter, not the agent logic. The HTTP layer is already framework-agnostic — the same routes work under stdlib http.server or FastAPI. Adding concurrent sessions is a matter of adding server capacity, not changing the design. 

**Across providers** , the LLMClient is provider-agnostic by design: every provider is a protocol adapter behind the same chat() / chat_json() interface. Migrating from GPT-4o to Claude or a locally hosted Ollama model is a one-line environment variable change. This means Beacon can be deployed in air-gapped environments, under strict data-residency requirements, or at zero inference cost with a local model — all without touching application code. 

**Across use cases** , the four-file agent brain (planner, narrator, navigator, agent) is the only thing that changes when Beacon is applied to a new domain. The transport, persistence, and voice UI are stable and reusable. A customer-support Beacon, an onboarding Beacon, and a travel-planning Beacon share the same infrastructure and differ only in their prompts and step definitions. 

#### **How It Expands** 

The roadmap deepens the same core loop rather than bolting on unrelated features. Near term, real tool-use calls let Beacon take actions — not just give advice — and streaming TTS closes the latency gap that makes voice feel clunky. In the medium term, a personalisation layer means Beacon remembers the user across sessions and stops asking questions it already knows the answer to. Long term, Beacon becomes the conversational front-end for an organisation’s knowledge and action layer — the interface through which employees, customers, and systems interact with institutional knowledge by simply speaking to it. 

#### **The Larger Vision** 

Voice should be the universal interface to AI assistance — not a gimmick layered over a text box, but a genuine conversational partner that plans, remembers, and acts. The end state is a world where any task that can be described in a sentence can be completed in a conversation: the user speaks, Beacon listens, asks exactly what it needs to know, and walks the user to the finish line. The session transcript is the receipt — a durable, auditable record of what was decided and done. Beacon is the proof that this kind of experience can be built on a simple, composable foundation that any team can own, extend, and trust. 

#### **Potential Impact** 

At one user’s scale, Beacon replaces the frustrating cycle of re-prompting, copy-pasting, and context-switching that single-shot AI assistants impose. A user who would have spent twenty minutes wrestling with three separate tools to plan a dinner and book a table instead speaks for three turns and is done. 

At team scale, shared Beacon instances reduce the load on senior staff who repeatedly answer the same onboarding, planning, and operational questions. The transcript log gives team leads visibility into what was asked and decided without attending every conversation. 

At org scale, the compounding effect is significant: a consistent, voice-first interface to institutional knowledge reduces friction across every function that relies on AI assistance — support, ops, sales, engineering. The intervention is architectural — a conversational loop with a trust boundary and a persistent record — but it shifts the entire experience from “prompt and hope” to “speak and complete.” 
