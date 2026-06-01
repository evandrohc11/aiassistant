# Personal Agent

A private assistant I talk to over WhatsApp to track spending/earnings, manage small tasks, and optionally journal mood. Remembers decisions so it never re-asks. Bilingual (PT/EN). Legacy money is BRL; new entries default to CAD.

**Stack (locked):** Python + FastAPI · Supabase (Postgres) · Twilio WhatsApp · one LLM call for parsing · hosted on Fly.io. No web frontend — WhatsApp is the interface. Do not substitute the stack. Full rules in `CLAUDE.md`.

---

## Always updated the .md files inside memories folder!!! And keep the project folder organized, place file in proper folder and don't let these changes broke the wire inside the project.


## ▶️ Current status — start here

- ✅ Phase 0 done: venv, dependencies, FastAPI `/health` endpoint.
- ✅ Phase 1 done: v2 schema executed in Supabase (12 tables + audit trigger). Power BI CSV data imported — 24,036 transactions, 974 labels, 27 cards, 10 accounts, 25 categories.
- ⏳ **Phase 2 next:** FastAPI CRUD endpoints (monthly summary, add transaction, list tasks).

See `memories/PROJECT_STATUS.md` for full detail and `memories/personal_agent_build_prompts.md` for the Phase 2 prompt.

---

## Files

| File | Purpose |
|------|---------|
| `memories/CLAUDE.md` | Standing context — hard constraints, stack, conventions. |
| `memories/PROJECT_STATUS.md` | Current phase, schema facts, architecture decisions. |
| `memories/personal_agent_build_prompts.md` | Phased build prompts. Feed one phase at a time. |
| `supabase_schema.sql` | v2 database schema (12 tables + audit trigger). Executed ✓. |
| `scripts/import_from_csv.py` | Power BI CSV → Supabase import. Run once. Done ✓. |
| `scripts/import_legacy.py` | Old SQLite → Supabase migration. Superseded. |
| `raw_files/` | Source CSVs from Power BI (item, description, cards, audit_log). |
| `.env` | Secrets only. Never committed. |

## Run order

0. **Phase 0 — Environment** ✔ done: venv + `requirements.txt` + `.env`.
1. **Phase 1 — Schema + import** ✔ done:
   - v2 `supabase_schema.sql` executed (12 tables + audit trigger)
   - `scripts/import_from_csv.py` run — 24,036 transactions imported from Power BI CSVs
2. **Phase 2 — Backend API** ⏳ next: FastAPI CRUD + monthly summaries.
3. **Phase 3 — WhatsApp ingestion + smart categorization** (learns rules so it stops asking).
4. **Phase 4 — Memory + follow-ups** (anti-loop recall; daily nudges).
5. **Phase 5 — Mood journal** *(optional)*.
6. **Phase 6 — Audit log endpoints** (schema/trigger already done in Phase 1).

Exact prompts for each phase live in `memories/personal_agent_build_prompts.md`.

## Secrets & safety
- All secrets live only in `.env` (git-ignored, deny-listed). Never read or print them.
- In production use Fly.io secrets: `fly secrets set SUPABASE_SERVICE_KEY=...` (injected at runtime, never on disk).
- Never store full card numbers, bank/account numbers, or government IDs — amounts, categories, merchants only.

## Using this with Claude Code
Open the Claude Code panel (it loads `CLAUDE.md` automatically). Read this README and `CLAUDE.md`, confirm the status above, then resume at the current step. Build one phase at a time and review each diff before accepting.
