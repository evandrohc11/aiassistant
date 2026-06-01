# Personal Assistant — Project Status & Decisions Log
_Last updated: 2026-05-31 | Hand-off file for Claude / other agents_

---

## What this project is

A private WhatsApp-based personal assistant for one user (Evandro, Vancouver CA).
- Tracks spending/earnings via free-text WhatsApp messages (PT or EN)
- Manages tasks with due dates
- Sends daily nudges for overdue tasks and over-budget categories
- Remembers every decision so it never re-asks (anti-loop memory)
- Optional: mood journaling against a feelings taxonomy
- Historical data: ~23,000 transactions imported from legacy SQLite (BRL)
- New data: defaults to CAD

---

## Hard constraints (do not change)

| Constraint | Value |
|---|---|
| Backend | Python 3.14.5 + FastAPI |
| Database | Supabase (Postgres) — project: **personalai**, region: Canada Central |
| Messaging | Twilio WhatsApp sandbox |
| LLM parsing | OpenAI SDK — one call → strict JSON |
| Hosting | Fly.io (free tier) |
| Interface | WhatsApp only — no web frontend |
| Languages | Portuguese + English interchangeably |
| Legacy currency | BRL (all imported data) |
| New currency default | CAD |

---

## Repository layout

```
C:\Projects\Assistant\
├── .env                         ← secrets (never commit)
├── .env.example                 ← template
├── .gitignore
├── requirements.txt
├── supabase_schema.sql          ← v2 schema — executed in Supabase ✓
├── app/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI entry point, /health route
│   ├── config.py                ← pydantic-settings, loads .env
│   ├── routers/
│   │   └── webhook.py           ← Twilio inbound stub (Phase 3 wires real logic)
│   └── services/
│       └── supabase_client.py   ← singleton get_client()
├── raw_files/                   ← original source data (do not modify)
│   ├── item.csv                 ← 24,036 transactions (Power BI export)
│   ├── description.csv          ← 974 labels
│   ├── cards.csv                ← 27 cards
│   ├── audit_log.csv            ← 2,237 rows (reference only — not imported)
│   ├── feelings_taxonomy.csv    ← imported via schema seed
│   └── _PAINEL_V1.pbix          ← original Power BI file (reference)
├── scripts/
│   ├── verify_env.py            ← sanity check: prints SUPABASE_URL
│   ├── import_from_csv.py       ← ACTIVE: v2 CSV import (run this) ✓ done
│   ├── import_legacy.py         ← old SQLite → Supabase migration (superseded)
│   ├── import_my_db.py          ← old SQLite migration (superseded)
│   ├── _analyse_csv.py          ← temp diagnostic (safe to delete)
│   ├── _check_tenis.py          ← temp diagnostic (safe to delete)
│   └── _read_pbix.py            ← temp diagnostic (safe to delete)
├── memories/                    ← hand-off docs for AI agents (always keep updated)
│   ├── CLAUDE.md                ← standing context / hard constraints
│   ├── PROJECT_STATUS.md        ← this file
│   └── personal_agent_build_prompts.md  ← phased build guide
└── _pbix_extract/               ← temp PBI extraction (safe to delete)
```

---

## Installed packages (venv: .venv\Scripts\activate.bat)

| Package | Version | Notes |
|---|---|---|
| fastapi | 0.136.3 | |
| uvicorn | 0.48.0 | |
| supabase | 2.30.1 | needs pyiceberg stub — see known issues |
| twilio | 9.10.9 | |
| groq | 0.9.0+ | Free hosted LLM API — model: llama-3.3-70b-versatile |
| httpx | 0.28.1 | |
| pydantic | 2.13.4 | |
| pydantic-settings | 2.14.1 | |
| APScheduler | 3.11.2 | v3 API — use BackgroundScheduler, NOT AsyncScheduler |
| python-dotenv | 1.2.2 | |
| python-multipart | 0.0.29 | required for Twilio form-encoded webhooks |

### Known issue: pyiceberg stub (RESOLVED)
supabase → storage3 → storage3._async.analytics → pyiceberg (no wheel for Python 3.14)
Fix: created stub at `.venv\Lib\site-packages\pyiceberg\catalog\rest.py`:
```python
class RestCatalog:
    pass
```
Plus empty `__init__.py` in `pyiceberg\` and `pyiceberg\catalog\`.
DO NOT run `pip install pyiceberg` — it will fail. Stub is sufficient.

### Known issue: datetime.utcnow() (RESOLVED)
Deprecated on Python 3.12+. All code uses `datetime.now(datetime.timezone.utc)`.

---

## Supabase database v2 — tables (all created ✓, data imported ✓)

| Table | Rows | Purpose | RLS |
|---|---|---|---|
| cards | 27 | Credit/debit cards (integer PK from legacy) | owner-scoped |
| accounts | 10 | Bank accounts (normalized from legacy "bank" field) | owner-scoped |
| categories | 25 | Spending categories (from Power BI group field, normalized) | owner-scoped |
| labels | 974 | Transaction descriptions/labels (from description.csv) | owner-scoped |
| transactions | 24,036 | Core ledger — direction+amount, currency, FK to above | owner-scoped |
| transaction_audit | auto | Trigger-based audit log (INSERT/UPDATE/DELETE, JSONB snapshots) | owner-scoped |
| tasks | 0 | Reminders with due dates | owner-scoped |
| feelings_taxonomy | seeded | Reference list: feeling / sensation / emotion | public read |
| mood_entries | 0 | User's mood journal entries | owner-scoped |
| agent_memory | 0 | Durable decisions/preferences (anti-loop) | owner-scoped |
| category_rules | 0 | Learned merchant→category mappings (personal) | owner-scoped |
| shared_category_rules | 0 | Cross-user learned rules — confidence-weighted | all authenticated |

### Key schema decisions
- `cards` and `labels` use **integer primary keys** from legacy IDs (not UUID)
- `labels` has NO unique(owner_id, name) constraint — duplicate names exist with different IDs
- `cards` has NO unique(owner_id, name) constraint — 3 cards share the name "01_NO" with different IDs
- `transactions.direction` = 'income' | 'expense' (not signed amount); `amount` is always positive
- `transactions.legacy_id` (integer UNIQUE) enables safe re-import dedupe
- `transaction_audit` is trigger-only — `fn_audit_transactions()` fires on INSERT/UPDATE/DELETE
- `projects` table removed — legacy "operation" field becomes free-text `notes` on transactions

### shared_category_rules — multi-agent memory design
- Stores: `pattern` (e.g. "uber") → `category_name` (e.g. "Transporte") + `confidence` count
- Any authenticated user reads it; any user can increment confidence
- Agent decision flow:
  1. Check personal `category_rules` → match? use silently
  2. Check `shared_category_rules` (confidence > 3) → match? use silently
  3. Ask user → on answer: write personal rule + upsert shared (confidence++)
- No PII — merchant/keyword patterns only

---

## .env variables required

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=<service_role key — from Supabase Dashboard → Settings → API>
OWNER_USER_ID=<UUID from auth.users — see Phase 1 Step 2>
SQLITE_PATH=my_db.db

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=<from Twilio Console>
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
MY_WHATSAPP_NUMBER=whatsapp:+1xxxxxxxxxx

GROQ_API_KEY=gsk_...       # from console.groq.com → API Keys
GROQ_MODEL=llama-3.3-70b-versatile

LOG_LEVEL=INFO
```

---

## Phase progress

### ✅ Phase 0 — Scaffolding (COMPLETE)
- Project folder, git repo, venv created
- All packages installed (with pyiceberg stub workaround)
- FastAPI app boots: `GET /health` → `{"status":"ok"}`
- Git commit: `413baca` "chore: Phase 0 scaffold"

### ✅ Phase 1 — Database + Migration (COMPLETE — 2026-05-31)
- [x] supabase_schema.sql v2 executed — 12 tables created (cards, accounts, categories, labels,
      transactions, transaction_audit, tasks, feelings_taxonomy, mood_entries, agent_memory,
      category_rules, shared_category_rules)
- [x] OWNER_USER_ID: `ddc418d6-6dc4-405f-b6e1-492627bb218e` (evandrocavalheri@gmail.com) — set in .env
- [x] Power BI CSV exports placed in raw_files/ (item.csv, description.csv, cards.csv, audit_log.csv)
- [x] import_from_csv.py written and executed — zero rows skipped
  - cards: 27 | accounts: 10 | categories: 25 | labels: 974 | transactions: 24,036
- [x] Trigger fn_audit_transactions confirmed firing on transaction writes
- [x] Constraint fixes: dropped unique(owner_id,name) on both cards and labels tables

### ✅ Phase 2 — FastAPI CRUD endpoints (COMPLETE — 2026-05-31)
- [x] `app/routers/transactions.py`: POST /transactions/, GET /transactions/, GET /transactions/summary?year&month, GET /transactions/{id}
- [x] `app/routers/tasks.py`: POST /tasks/, GET /tasks/, PATCH /tasks/{id}, DELETE /tasks/{id}
- [x] `app/config.py`: switched to GROQ_API_KEY/GROQ_MODEL; Twilio fields optional (default empty)
- [x] Smoke tested: /health ✔, /transactions/summary?year=2024&month=1 returns 14 categories from real data
- [x] Git commit: 9a9b041

### ⏳ Phase 3 — WhatsApp webhook + LLM parsing + category rules engine (NEXT)
- Twilio inbound webhook stub exists at app/routers/webhook.py
- Wire to: LLM parse → category_rules lookup → ask/save loop
- ngrok for local dev tunnel

### ⏳ Phase 4 — Memory + anti-loop engine + daily nudges
- remember(topic_key, value) / recall(topic_key) helpers
- agent_memory read before every question
- APScheduler daily job: tasks due ≤2 days + over-budget categories → one WhatsApp

### ⏳ Phase 5 — Mood journal (optional)
- "feeling: stressed" → LLM maps to taxonomy → mood_entries row
- "how was my week" → emotion distribution summary

### ⏳ Phase 6 — Audit log endpoints
- Schema + trigger already done (part of Phase 1)
- 6a: GET /transactions/{id}/history — audit trail endpoint
- 6b: WhatsApp "show history" intent handler
- 6c: "undo last change" intent handler
- 6d: Admin audit summary

---

## Architecture decisions made

| Decision | Choice | Reason |
|---|---|---|
| Hosting | Fly.io free tier | Always-on, HTTPS URL for Twilio webhook, simple deploy |
| LLM | Groq free tier (Llama 3.3-70b-versatile) | Free hosted API; `groq` SDK; OpenAI-compatible |
| Scheduler | APScheduler 3.x BackgroundScheduler | Runs inside FastAPI process; v4 API not compatible |
| Twilio auth | RequestValidator in middleware | Every inbound POST validated before processing |
| RLS | Enabled + auto-enable trigger | Belt-and-suspenders; service_role key bypasses for jobs |
| Currency | Legacy=BRL, new=CAD | Explicit per-row currency column, no global setting |
| Shared memory | shared_category_rules confidence table | Cross-user learning without PII |
| Phone access | WhatsApp only | No HTTP client needed; Twilio is the interface |

---

## How to run locally

```powershell
# Activate venv
C:\Projects\Assistant\.venv\Scripts\activate.bat

# Start server (with auto-reload)
uvicorn app.main:app --reload

# Test health
curl http://127.0.0.1:8000/health
```

## Next immediate action

Phase 2 complete. Start Phase 3 — WhatsApp webhook + LLM parsing.
See: `memories/personal_agent_build_prompts.md` → ## Phase 3

Phase 3 needs:
- Real `GROQ_API_KEY` in `.env` (get from console.groq.com → API Keys)
- Real Twilio sandbox credentials in `.env`
- ngrok (or similar) for local webhook tunnel
