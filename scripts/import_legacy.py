"""
scripts/import_legacy.py
Migrates my_db.db (legacy SQLite) → Supabase Postgres.

What it does
------------
1. Reads tb_event (and tb_feelings / tb_records if present).
2. Rebuilds one DATE from the split day/month/year integer columns.
3. Converts comma-decimal Brazilian amounts ("1.234,56") → Python Decimal.
4. Upserts unique accounts / categories / projects as dimension rows first.
5. Inserts transactions, linking FK ids; preserves messy "bank" text in
   account_raw; tags all legacy money as BRL.
6. Uses legacy_code (tb_event.code) for dedupe — safe to re-run.

Usage (from project root, venv active)
---------------------------------------
    python scripts/import_legacy.py --db my_db.db --owner <YOUR_OWNER_USER_ID>

Flags
-----
    --db       path to the SQLite file        (default: my_db.db)
    --owner    your Supabase auth.users UUID  (required)
    --dry-run  print stats without writing anything
    --batch    rows per Supabase insert call  (default: 200)
"""

import argparse
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from app.services.supabase_client import get_client  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_br_decimal(raw) -> Optional[Decimal]:
    """Turn Brazilian comma-decimal strings into Decimal.

    Handles: '1.234,56'  →  1234.56
             '234,56'    →  234.56
             '-1.234,56' → -1234.56
             1234.56     → 1234.56  (already numeric)
             None / ''   → None
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        # Already a plain number (no comma)
        if "," not in s:
            return Decimal(s.replace(".", "").replace(" ", "") or "0")
        # Brazilian format: dots are thousands separators, comma is decimal
        s = s.replace(".", "").replace(",", ".")
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_date(day, month, year) -> Optional[date]:
    """Build a date from three nullable int columns."""
    try:
        d = int(day or 1)
        m = int(month or 1)
        y = int(year or 2000)
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _col_names(cursor, table: str) -> set:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1].lower() for row in cursor.fetchall()}


def _inspect(con) -> dict:
    """Return {table_name: set_of_lowercase_column_names}."""
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    return {t: _col_names(cur, t) for t in tables}


# ---------------------------------------------------------------------------
# dimension upsert helpers (return id map: name → uuid)
# ---------------------------------------------------------------------------

def _upsert_dimensions(sb, owner_id: str, table: str, names: set) -> dict:
    """Insert missing dimension rows and return {name: uuid} map."""
    if not names:
        return {}

    # Fetch existing
    resp = sb.table(table).select("id, name").eq("owner_id", owner_id).execute()
    existing = {r["name"]: r["id"] for r in (resp.data or [])}

    # Insert missing
    missing = [
        {"owner_id": owner_id, "name": n, "currency": "BRL"}
        if table == "accounts"
        else {"owner_id": owner_id, "name": n}
        for n in names
        if n and n not in existing
    ]
    if missing:
        inserted = (
            sb.table(table)
            .insert(missing, returning="representation")
            .execute()
        )
        for r in inserted.data or []:
            existing[r["name"]] = r["id"]

    return existing


# ---------------------------------------------------------------------------
# main migration
# ---------------------------------------------------------------------------

def migrate(db_path: str, owner_id: str, dry_run: bool, batch_size: int):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    schema = _inspect(con)
    print(f"SQLite tables found: {sorted(schema.keys())}")

    # Locate the main event table (tb_event is canonical name from spec)
    event_table = None
    for candidate in ("tb_event", "event", "events", "transactions"):
        if candidate in schema:
            event_table = candidate
            break
    if event_table is None:
        sys.exit("ERROR: Could not find a transactions table (tried tb_event, event, events, transactions).")

    cols = schema[event_table]
    print(f"Using table '{event_table}' with columns: {sorted(cols)}")

    cur.execute(f"SELECT COUNT(*) FROM {event_table}")
    total = cur.fetchone()[0]
    print(f"Total legacy rows: {total:,}")

    if dry_run:
        print("[dry-run] Inspected schema. Pass without --dry-run to import.")
        con.close()
        return

    sb = get_client()

    # -----------------------------------------------------------------------
    # Pass 1: collect distinct dimension values
    # -----------------------------------------------------------------------
    # Map legacy column name variants
    col = lambda *alts: next((a for a in alts if a in cols), None)

    c_account  = col("bank", "account", "conta")
    c_category = col("grouped", "category", "categoria", "group")
    c_project  = col("operation", "project", "projeto", "operacao")
    c_code     = col("code", "codigo", "id")
    c_day      = col("day", "dia")
    c_month    = col("month", "mes")
    c_year     = col("year", "ano")
    c_amount   = col("amount", "value", "valor", "quantia")
    c_label    = col("label", "descricao", "description")
    c_merchant = col("details", "merchant", "comerciante", "detail")
    c_card     = col("card", "cartao")
    c_cycle    = col("bill_cycle", "cycle", "ciclo", "competencia")
    c_install  = col("installments", "parcelas", "parcelamento")
    c_cleared  = col("cleared", "liquidado", "confirmado")

    print(f"\nColumn mapping:")
    for name, val in [
        ("account",c_account),("category",c_category),("project",c_project),
        ("code",c_code),("day",c_day),("month",c_month),("year",c_year),
        ("amount",c_amount),("label",c_label),("merchant",c_merchant),
    ]:
        print(f"  {name:12s} → {val}")

    cur.execute(f"SELECT DISTINCT {c_account} FROM {event_table} WHERE {c_account} IS NOT NULL" if c_account else "SELECT 1 WHERE 0=1")
    account_names  = {r[0].strip() for r in cur.fetchall() if r[0] and str(r[0]).strip()}

    cur.execute(f"SELECT DISTINCT {c_category} FROM {event_table} WHERE {c_category} IS NOT NULL" if c_category else "SELECT 1 WHERE 0=1")
    category_names = {r[0].strip() for r in cur.fetchall() if r[0] and str(r[0]).strip()}

    cur.execute(f"SELECT DISTINCT {c_project} FROM {event_table} WHERE {c_project} IS NOT NULL" if c_project else "SELECT 1 WHERE 0=1")
    project_names  = {r[0].strip() for r in cur.fetchall() if r[0] and str(r[0]).strip()}

    print(f"\nDimensions to upsert:")
    print(f"  accounts   : {len(account_names)}")
    print(f"  categories : {len(category_names)}")
    print(f"  projects   : {len(project_names)}")

    acc_map  = _upsert_dimensions(sb, owner_id, "accounts",   account_names)
    cat_map  = _upsert_dimensions(sb, owner_id, "categories", category_names)
    proj_map = _upsert_dimensions(sb, owner_id, "projects",   project_names)
    print("Dimensions upserted ✓")

    # -----------------------------------------------------------------------
    # Pass 2: fetch already-imported legacy codes (dedupe)
    # -----------------------------------------------------------------------
    resp = sb.table("transactions").select("legacy_code").eq("owner_id", owner_id).execute()
    already_imported = {r["legacy_code"] for r in (resp.data or []) if r["legacy_code"] is not None}
    print(f"Already imported: {len(already_imported):,} rows (will skip)")

    # -----------------------------------------------------------------------
    # Pass 3: stream + insert in batches
    # -----------------------------------------------------------------------
    select_cols = "*"
    cur.execute(f"SELECT {select_cols} FROM {event_table}")

    inserted_count = 0
    skipped_count  = 0
    error_count    = 0
    batch = []

    def flush(batch):
        nonlocal inserted_count, error_count
        if not batch:
            return
        try:
            sb.table("transactions").insert(batch).execute()
            inserted_count += len(batch)
            print(f"  ... inserted {inserted_count:,} / {total:,}", end="\r")
        except Exception as e:
            error_count += len(batch)
            print(f"\nBatch error: {e}")

    for row in cur:
        r = dict(row)

        # Dedupe by legacy_code
        legacy_code = int(r[c_code]) if c_code and r.get(c_code) is not None else None
        if legacy_code is not None and legacy_code in already_imported:
            skipped_count += 1
            continue

        # Date
        occurred_on = None
        if c_day and c_month and c_year:
            occurred_on = _parse_date(r.get(c_day), r.get(c_month), r.get(c_year))

        # Amount — legacy BRL, comma-decimal
        raw_amount = r.get(c_amount) if c_amount else None
        amount = _parse_br_decimal(raw_amount)
        if amount is None:
            error_count += 1
            continue

        direction = "expense" if amount < 0 else "income"

        # FK lookups
        account_raw  = r.get(c_account, "").strip() if c_account else None
        category_raw = r.get(c_category, "").strip() if c_category else None
        project_raw  = r.get(c_project, "").strip() if c_project else None

        account_id  = acc_map.get(account_raw)  if account_raw  else None
        category_id = cat_map.get(category_raw) if category_raw else None
        project_id  = proj_map.get(project_raw) if project_raw  else None

        tx = {
            "owner_id":    owner_id,
            "legacy_code": legacy_code,
            "occurred_on": occurred_on.isoformat() if occurred_on else None,
            "amount":      str(amount),
            "currency":    "BRL",
            "direction":   direction,
            "category_id": category_id,
            "label":       str(r[c_label]).strip() if c_label and r.get(c_label) else None,
            "merchant":    str(r[c_merchant]).strip() if c_merchant and r.get(c_merchant) else None,
            "project_id":  project_id,
            "account_id":  account_id,
            "account_raw": account_raw,
            "card":        str(r[c_card]).strip() if c_card and r.get(c_card) else None,
            "bill_cycle":  str(r[c_cycle]).strip() if c_cycle and r.get(c_cycle) else None,
            "installments":str(r[c_install]).strip() if c_install and r.get(c_install) else None,
            "cleared":     bool(r[c_cleared]) if c_cleared and r.get(c_cleared) is not None else True,
        }

        batch.append(tx)
        if len(batch) >= batch_size:
            flush(batch)
            batch = []

    flush(batch)  # remainder

    print(f"\n\nMigration complete:")
    print(f"  Inserted : {inserted_count:,}")
    print(f"  Skipped  : {skipped_count:,}  (already imported)")
    print(f"  Errors   : {error_count:,}")

    # -----------------------------------------------------------------------
    # Migrate feelings taxonomy + mood entries if tables exist
    # -----------------------------------------------------------------------
    if "tb_feelings" in schema:
        print("\nMigrating feelings_taxonomy …")
        cur.execute("SELECT * FROM tb_feelings")
        rows = [dict(r) for r in cur.fetchall()]
        feelings_cols = schema["tb_feelings"]
        c_feel = col2 = lambda *a: next((x for x in a if x in feelings_cols), None)
        taxonomy = [
            {
                "feeling":   str(r.get("feeling") or r.get("sentimento") or "").strip() or None,
                "sensation": str(r.get("sensation") or r.get("sensacao") or "").strip() or None,
                "emotion":   str(r.get("emotion") or r.get("emocao") or "").strip() or None,
            }
            for r in rows
        ]
        if taxonomy:
            sb.table("feelings_taxonomy").insert(taxonomy).execute()
            print(f"  Inserted {len(taxonomy)} taxonomy rows ✓")

    if "tb_records" in schema:
        print("Migrating mood_entries …")
        cur.execute("SELECT * FROM tb_records")
        rec_cols = schema["tb_records"]
        mood_rows = []
        for r in cur.fetchall():
            r = dict(r)
            # Try to find a date field
            occ = None
            for df in ("date","data","occurred_at","created_at"):
                if df in rec_cols and r.get(df):
                    try:
                        occ = datetime.fromisoformat(str(r[df])).isoformat()
                    except Exception:
                        pass
                    break
            mood_rows.append({
                "owner_id":    owner_id,
                "occurred_at": occ or datetime.utcnow().isoformat(),
                "feeling":     str(r.get("feeling") or r.get("sentimento") or "").strip() or None,
                "sensation":   str(r.get("sensation") or r.get("sensacao") or "").strip() or None,
                "emotion":     str(r.get("emotion") or r.get("emocao") or "").strip() or None,
                "notes":       str(r.get("notes") or r.get("notas") or r.get("description") or "").strip() or None,
            })
        if mood_rows:
            sb.table("mood_entries").insert(mood_rows).execute()
            print(f"  Inserted {len(mood_rows)} mood entries ✓")

    con.close()


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate my_db.db → Supabase")
    parser.add_argument("--db",      default="my_db.db", help="Path to SQLite file")
    parser.add_argument("--owner",   required=True,      help="Your Supabase auth.users UUID")
    parser.add_argument("--dry-run", action="store_true", help="Inspect only, no writes")
    parser.add_argument("--batch",   type=int, default=200, help="Rows per insert batch")
    args = parser.parse_args()

    migrate(args.db, args.owner, args.dry_run, args.batch)
