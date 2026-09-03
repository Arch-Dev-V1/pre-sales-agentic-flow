# DemoForge (placeholder name)

Turns a Postman collection into a live, narrative-driven demo app for
pre-sales teams — instead of engineering hand-building a bespoke UI
for every prospect pitch.

## One-line pitch

Upload a Postman collection + environment. Three agents turn it into
a working, story-driven demo app that a salesperson can click through
live, hitting the real API, using the sample data the API
team already put in the collection.

## How it finds the collection

The user never types a Collection ID or Environment ID — those are
internal Postman UUIDs nobody has memorized. Instead:

1. Paste a Postman API key (found in Postman's own account settings —
   a normal "connect your account" step, same as any third-party
   integration)
2. The backend lists every workspace that key can see; pick one by name
3. The backend lists that workspace's collections and environments;
   pick each by name

The actual ids ride along invisibly once something's selected from a
dropdown — see `postman_client.list_workspaces` /
`list_workspace_contents` and `ConnectPostman.jsx`.

## Architecture

```
Postman Collection + Environment      Fixed pre-generation questions
            │                          (industry, emphasis, tone,
            ▼                           company name, theme, depth)
   ┌─────────────────┐                          │
   │  Analyst Agent   │                          │
   │   (read-only)    │                          │
   └────────┬─────────┘                          │
            │                                    │
            ▼                                    ▼
   ┌──────────────────────────────────────────────┐
   │              Sequencer Agent                  │  orders the endpoints,
   │           (no API calls, no tools)             │  threads values between
   └────────┬───────────────────────────────────────┘  steps, and uses the
            │                                           config to shape
            │                                           narration wording —
            │                                           never layout or
            │                                           structure.
            ▼
   ┌─────────────────┐
   │  Verifier Agent  │
   │  (calls the API) │
   └────────┬─────────┘
            │
            ▼
     Verified demo script
    (ready for the frontend)
```

### On the pre-generation questions specifically

This is a fixed, closed set of questions (`ConfigureDemo.jsx`) — not a
chat, not a freeform brief. The user picks from known options; there is
no field anywhere that lets someone say "make this button round" or
otherwise direct layout/structure. This is a deliberate boundary, not a
current limitation to be lifted later: it's what keeps this an "agent
that curates a sales story," not an open-ended app builder, which is a
much harder thing to demo reliably and isn't what this tool is for.

The answers reach the Sequencer Agent only — never the Analyst or the
Verifier, since narration wording is the Sequencer's job alone. Visual
theme (light/dark) never reaches any agent at all; it's handled entirely
in the frontend via a `data-theme` attribute and plain CSS.

Why only three agents, not more: an "agent" here means something that
plans, calls tools, and reacts to what it finds — not just a pipeline
step. Everything that's pure synthesis over data another agent already
gathered stays inside that agent's job rather than becoming its own
"agent" for the sake of the pitch deck.

## Security guardrails (baked into the design, not bolted on after)

These aren't optional flags — they're structural:

1. **The frontend never sees credentials.** It only ever talks to our
   own backend. The backend holds the Postman API key and the target
   API's username/password/base URL server-side, and proxies every
   real call. See `backend/session_store.py`.
2. **Session-scoped only.** Credentials live in memory for the
   duration of a session and are never written to disk, a database,
   or a log line. Restarting the backend clears everything.
3. **One way out to the network.** Every call to the target API goes
   through `backend/api_proxy.py` and nothing else, so response
   redaction can't be bypassed by a second code path. Which hosts are
   reachable is the operator's choice: `config.HOST_ALLOWLIST` is empty
   by default, meaning any base URL they supply — production included —
   is callable. Populate that list to restrict it to sandbox or staging
   hosts. Note that with no allow-list the Verifier agent decides which
   endpoints to call, so a production target can receive real writes.
4. **No new synthetic PII is generated.** We deliberately do not ask
   any agent to invent realistic-looking names, emails, or ID numbers.
   Only the example values already present in the collection (plain
   text or base64-encoded images) are ever reused. See the scoping
   note in `prompts/sequencer_agent.md`.
5. **Secrets are never echoed back.** Every agent prompt explicitly
   forbids repeating an actual secret value in its output — auth
   fields are referenced symbolically (`{{authToken}}`), never as the
   real string, even in the Verifier's error output.

## Repo layout

```
demoforge/
├── README.md
├── backend/
│   ├── main.py                 FastAPI app + routes
│   ├── config.py                Env/config loading
│   ├── session_store.py         In-memory, session-scoped credential store
│   ├── postman_client.py        Fetches collection + environment via Postman API
│   ├── variable_resolver.py     {{var}} substitution against an environment
│   ├── api_proxy.py             The only place that calls the real target API
│   ├── orchestrator.py          Runs Analyst → Sequencer → Verifier
│   ├── requirements.txt
│   └── tools/
│       └── tool_definitions.py  Anthropic tool-use schemas, one set per agent
├── prompts/
│   ├── analyst_agent.md
│   ├── sequencer_agent.md
│   └── verifier_agent.md
└── frontend/
    ├── package.json
    └── src/
        ├── App.jsx
        ├── api/client.js
        └── components/
            ├── ConnectPostman.jsx
            ├── AgentTrace.jsx     Live "what the agents are doing" feed
            └── DemoRunner.jsx     The actual clickable demo for the salesperson
```

## Running locally

Backend:
```
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in your own ANTHROPIC_API_KEY
uvicorn main:app --reload
```

Frontend:
```
cd frontend
npm install
npm run dev
```

## Status

Real, working code, not stubs: the three agents (`orchestrator.py`),
the Claude tool-use loop (`agent_runtime.py`), Postman collection
parsing (`postman_parser.py`), auth-block translation
(`auth_resolver.py`), variable resolution, the single-exit API proxy,
session storage, and CORS.

Still genuinely incomplete, in priority order:
- **Live agent trace** — `/generate-demo` still returns one big
  response at the end rather than streaming each agent's progress; the
  frontend's `AgentTrace.jsx` is built for streaming but has nothing
  feeding it live yet.
- **Auth-type-aware connect form** — `ConnectPostman.jsx` always shows
  username/password fields regardless of what auth type the collection
  actually uses.
- **Session expiry sweep** — noted in `session_store.py`, not
  implemented; sessions live until the process restarts.
- **OAuth2/Digest/AWS auth types** — `auth_resolver.py` raises
  `NotImplementedError` for these rather than silently sending an
  unauthenticated request; a real follow-up if a target API needs one.
- Visual theming CSS and error-state UX polish — deferred on purpose.

