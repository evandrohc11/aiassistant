# CLAUDE.md — Personal Agent

Standing context for this project. Read this before any task and respect it across every phase.

## What we're building
A private personal assistant I talk to over WhatsApp to track spending/earnings, manage small tasks, and optionally journal mood. It must remember decisions so it never re-asks the same thing. I message in Portuguese or English interchangeably. Historical money is BRL; new entries default to CAD.

## Tech stack — HARD CONSTRAINTS (do not substitute)
- Backend: Python + FastAPI, always run inside the project virtual environment (`.venv`)
- Database: Supabase (Postgres) via the `supabase-py` client
- Messaging: Twilio WhatsApp sandbox (inbound webhook + outbound messages)
- Parsing: a single LLM SDK call returning strict JSON
- Migration: legacy data imported from Power BI CSV exports via `scripts/import_from_csv.py` (24,036 transactions — DONE ✓)
- Hosting: Fly.io
No web frontend — WhatsApp is the interface. Do not introduce other web frameworks, ORMs, or databases.

## Data model (authoritative file: `supabase_schema.sql`) — v2 schema
- `cards(id integer PK, name, active, close_day)` — credit/debit cards from legacy Power BI
- `accounts(id uuid PK, name, kind, currency)` — normalized from the legacy "bank" field
- `categories(id uuid PK, name, kind)` — from Power BI description.group (normalized)
- `labels(id integer PK, name, category_id, is_routine, active)` — from description.csv; transaction FK
- `transactions(id uuid PK, legacy_id integer UNIQUE, occurred_on, amount NUMERIC, currency, direction, label_id→labels, category_id→categories, account_id→accounts, card_id→cards, details, notes, bill_cycle, installments, cleared, ...)` — core ledger
- `transaction_audit` — Postgres trigger-based audit log (INSERT/UPDATE/DELETE, JSONB before/after)
- `tasks`, `mood_entries`, `feelings_taxonomy`, `agent_memory`, `category_rules`, `shared_category_rules` — unchanged
NOTE: `projects` table removed — the legacy "operation" field is free-text `notes` on transactions.
NOTE: `direction` is 'income' or 'expense' (not a signed amount).

## Core behaviors
- Parse amount/currency/category from PT or EN free text; default currency CAD.
- Auto-categorize via `category_rules` first; only ask me when no rule matches, then SAVE my answer as a new rule so it never asks again.
- MEMORY / anti-loop: before asking me anything, check `agent_memory` for a settled decision on that `topic_key` and act on it instead of re-asking. Store new decisions/preferences as `settled`; only overwrite when I explicitly say to change it (mark the old row `superseded`).
- Daily nudge only if there are open tasks due within 2 days OR a category is over its monthly limit.
- Reply in the language I used.

## Conventions
- Secrets live ONLY in `.env` (git-ignored, deny-listed in `.claude/settings.json`). NEVER read `.env`, never print secret values in output, logs, or commands. Use Fly.io secrets in production.
- Keep dependencies in `requirements.txt`; install inside `.venv`.
- Build phase by phase (see `personal_agent_build_prompts.md`). Finish and verify one phase before starting the next; review each file edit as a diff before accepting.

## Privacy
Never store full card numbers, bank/account numbers, or government IDs — amounts, categories, and merchant names only.
