# Personal Agent — Phased Build Prompts (Pro-Code, GitHub Copilot)

**Stack (locked):** Python (FastAPI) backend + Supabase (Postgres) + Twilio WhatsApp + an LLM SDK for parsing. Built in VS Code with GitHub Copilot. Historical data is migrated from a legacy SQLite file (`my_db.db`).
**Why this WhatsApp route:** Twilio's WhatsApp **sandbox** is the maintainable, terms-compliant way to connect a personal flow without a business number. The unofficial `whatsapp-web.js` / `Baileys` libraries also work but mimic WhatsApp Web and can break or violate Meta's terms — use only if you accept that risk.

**Companion files in this folder:** `supabase_schema.sql` (the redesigned database) and `import_my_db_to_supabase.py` (loads your 23k legacy records). Cleaned CSVs are provided as a backup import path.

**How to use:** paste the Master Context into GitHub Copilot Chat (or Cursor/Claude), let it confirm the plan, then feed Phase 0. One phase at a time; advance only when the verification passes.

---

## Master Context prompt

## Always updated the .md files inside memories folder!!! And keep the project folder organized, place file in proper folder and don't let these changes broke the wire inside the project. ##



```
You are an expert Python full-stack developer. You will help me build a personal assistant, step by step, in VS Code with GitHub Copilot.

TECH STACK (hard constraint — do not substitute):
- Backend: Python + FastAPI, run inside a project virtual environment (venv)
- Database: Supabase (Postgres) via the Python client
- Messaging: Twilio WhatsApp sandbox (inbound webhook + outbound messages)
- Parsing: one LLM SDK call returning strict JSON
- Migration: import historical data from a legacy SQLite file (my_db.db)
Local dev first; no web frontend — WhatsApp is the interface.

SPEC (read-only context — do not write code yet):

# Personal Agent — Spec
## Goal
A private assistant I talk to over WhatsApp to track spending and earnings, manage small tasks, and (optionally) journal my mood. It must remember decisions so it never re-asks the same thing. I message in Portuguese or English interchangeably. Historical money is in BRL; new entries default to CAD.

## Core capabilities
- I text "spent $15 on coffee" / "gastei 15 no café" and it logs a transaction, auto-categorizing from learned rules.
- I text reminders ("remind me to pay rent Friday") and it logs a task with a due date.
- A daily job pings me on WhatsApp with pending tasks and any budget threshold I've crossed.
- MEMORY (anti-loop): every categorization rule, preference, or decision I make is stored, and the agent applies/recalls it instead of asking again. If I once say "Uber is Transporte," it never asks again; if a topic was already settled, it tells me what we decided instead of re-opening it.
- (Optional) I journal a feeling and it records it against a feelings taxonomy.

## Data model (Supabase — see supabase_schema.sql)
Redesigned from the legacy SQLite (which split dates across day/month/year ints, stored money as comma-text, and had no currency). New structure:
- accounts (name, kind, currency) — normalized from the legacy "bank" field
- categories (name, kind) — from legacy "grouped"
- projects (name) — from legacy "operation" context tags
- transactions — one DATE, NUMERIC amount, currency, direction, FKs to category/account/project, label, merchant, card, bill_cycle, installments, cleared, legacy_code (for dedupe)
- feelings_taxonomy + mood_entries — the journaling domain
- agent_memory (kind, topic_key, value, status) — durable decisions/preferences for the anti-loop behavior
- category_rules (match_type, pattern, category_id) — learned merchant/keyword → category mappings

## Business rules
- Parse currency + amount + category from free text in PT or EN; default currency CAD; negative amount = expense.
- On a new transaction, try category_rules first; only ask me if no rule matches, then SAVE my answer as a new rule.
- Before asking me anything, check agent_memory for a settled decision on that topic_key; if found, act on it and don't ask.
- Daily nudge only if there are open tasks due within 2 days OR a category is over its monthly limit.
- Reply in the language I used.

## Privacy
- Personal data: never store full card numbers, bank account numbers, or government IDs. Amounts, categories, and merchant names only.

## Out of scope for v1
- A web dashboard, multi-user support, receipt-image OCR.

Instructions: Acknowledge the stack, constraints, and spec. Reply with a short summary of the 6 phases, then wait for me to say "start Phase 0." No code yet.
```

---

## Phase 0 — Project setup (venv + libraries)

```
Phase 0: Environment.

1. Give me the exact terminal commands to create a project folder, initialize git, create a Python virtual environment (python -m venv .venv), and activate it on macOS/Linux and on Windows.
2. Create a requirements.txt with: fastapi, uvicorn, supabase, twilio, python-dotenv, and the LLM SDK we'll use. Show the pip install command (inside the venv).
3. Create a .env.example with placeholders: SUPABASE_URL, SUPABASE_SERVICE_KEY, OWNER_USER_ID, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, LLM_API_KEY. Add .env and .venv to .gitignore.

Verify before we continue: the venv activates, `pip list` shows the libraries, and a one-line script that loads .env prints the SUPABASE_URL.
```

---

## Phase 1 — Database schema + import historical data

```
Phase 1: Schema + migration.

1. I will run the provided supabase_schema.sql in the Supabase SQL editor to create all tables. Walk me through doing that and confirming the tables exist.
2. Help me find my OWNER_USER_ID (my row in auth.users) and set it in .env.
3. Using the provided import_my_db_to_supabase.py, walk me through running it against my_db.db to load the legacy records. Explain what it does: cleans the split day/month/year into a real date, fixes comma-decimal amounts, normalizes accounts/categories/projects into the lookup tables, preserves the messy original "bank" text in account_raw, and tags imported money as BRL.

Verify before we continue: transactions has ~23,000 rows for my OWNER_USER_ID, categories/accounts/projects are populated, and a sample query (sum of amount grouped by category for one year) returns sensible numbers.
```

---

## Phase 2 — Backend API

```
Phase 2: FastAPI backend.

1. Scaffold a FastAPI app that loads .env and creates the Supabase client.
2. Add a /health route and CRUD endpoints for transactions and tasks (create a tasks table first if not already present: id, owner_id, title, status, due_date, notes).
3. Add a read endpoint for monthly summaries (income vs expense per category for a given month/year).

Verify before we continue: I can run the app locally, hit /health, create a transaction via the API, and read back a correct monthly summary that includes the imported history.
```

---

## Phase 3 — WhatsApp ingestion + smart categorization

```
Phase 3: WhatsApp in.

1. Add a POST /whatsapp webhook that accepts Twilio's inbound payload, and give me the steps to connect the Twilio WhatsApp sandbox to my local webhook (with a tunneling tool like ngrok).
2. Send the message to one LLM call that returns STRICT JSON only: type (transaction|task|mood|unknown), language (pt|en), and the fields for that type (transaction: amount, currency, merchant, suggested_category; task: title, due_date). Must handle PT and English.
3. For a transaction, FIRST check category_rules (merchant/keyword match) for the category. If a rule matches, use it silently. If none matches, reply asking which category, and when I answer, INSERT a new row in category_rules so it never asks for that merchant again.
4. Write the record to the right table and reply confirming what was logged, in my language.

Verify before we continue: "gastei 15 no café" with no rule asks me the category once; after I answer, repeating it auto-categorizes with no question.
```

---

## Phase 4 — Memory + follow-up engine

```
Phase 4: Memory + nudges.

1. MEMORY API — add helper functions to read/write agent_memory: remember(topic_key, value, kind), recall(topic_key). Before the agent asks me anything (budgets, recurring rules, preferences), it must call recall() first and skip the question if a settled value exists.
2. LOOP-BREAK — when I state a decision or preference over WhatsApp, store it (status = settled). If I later raise the same topic_key, reply with the stored decision and the date instead of re-asking; only overwrite when I explicitly say to change it (mark the old row superseded).
3. NUDGES — a daily scheduled job (APScheduler or cron) that finds open tasks due within 2 days and any category over its monthly limit, and sends ONE consolidated WhatsApp message in my main language; otherwise stays silent.

Verify before we continue: setting a rule once makes the agent stop asking; re-raising a settled topic returns the saved decision; and a task due tomorrow plus an over-limit category produce exactly one nudge.
```

---

## Phase 5 — Mood journal (optional)

```
Phase 5: Mood journal (optional, after the core works).

1. Texting "feeling: <text>" / "sentindo: <texto>" sends the text to an LLM call that maps it onto the feelings_taxonomy (emotion / sensation / feeling) and writes a mood_entries row with my notes.
2. A weekly summary command ("how was my week" / "como foi minha semana") returns the distribution of emotions logged that week.

Keep it text-only and private. Verify: logging a feeling stores a correctly mapped mood_entries row, and the weekly summary reflects it.
```

## Phase 6 — Transaction audit log

### Context
The legacy system (Power BI file `_PAINEL_V1.pbix`) tracked all changes to the `item` table in an `audit_log` table with columns:
`log_id`, `table_name`, `operation_type` (INSERT/UPDATE/DELETE), `previous_data` (JSON), `new_data` (JSON), `operation_timestamp`, `user_id`.

We replicate this pattern in `transaction_audit` using a Postgres trigger (already in `supabase_schema.sql`).

### What's already done (schema)
- `transaction_audit` table stores every INSERT/UPDATE/DELETE on `transactions` with full JSONB before/after snapshots.
- `fn_audit_transactions()` trigger function fires automatically — no application code needed for writes.
- RLS: owner can read their own audit rows; writes are trigger-only (no API insert path needed).

### Phase 6 implementation tasks

**6a — Audit query endpoint**
Add `GET /transactions/{id}/history` in a new router `app/routers/transactions.py`:
- Query `transaction_audit` where `transaction_id = id`, ordered by `operated_at desc`.
- Return list of `{operation, operated_at, previous_data, new_data}`.
- Only expose to the owner (verify `owner_id` matches `OWNER_USER_ID` from config).

**6b — WhatsApp "show history" command**
Detect intent `show_history` in the LLM parser. When user asks something like:
- "o que mudou nessa transação?" / "history of item 1234"
Parse the `legacy_id` from the message, fetch from `transaction_audit`, and reply with a
human-readable diff: what changed (old → new) for each UPDATE, or INSERT/DELETE events.

**6c — Undo last change**
Detect intent `undo_last`. Find the most recent UPDATE in `transaction_audit` for the given
transaction, restore `previous_data` fields onto `transactions`, and reply confirming the rollback.
Use `updated_at = now()` on the restored row so the trigger records the revert as a new UPDATE event.

**6d — Admin summary**
Weekly or on-demand: count changes by operation type in the last 7 days:
```sql
select operation, count(*) from transaction_audit
where operated_at > now() - interval '7 days'
group by operation;
```

### Key schema facts
- `transaction_audit.previous_data` is NULL on INSERT.
- `transaction_audit.new_data` is NULL on DELETE.
- `transaction_audit.transaction_id` is the UUID from `transactions.id`.
- `transaction_audit.legacy_id` is the integer from `transactions.legacy_id` for easy cross-reference.
- The trigger runs as `security definer` so it bypasses RLS — audit rows are always written even when RLS is on.