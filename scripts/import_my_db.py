#!/usr/bin/env python3
"""
Import my_db.db (legacy SQLite) into the new Supabase schema.

Prereqs:
  1. Run supabase_schema.sql in Supabase first.
  2. pip install supabase   (done by the venv setup in Phase 0)
  3. Set environment variables in .env:
       SUPABASE_URL          = https://<project>.supabase.co
       SUPABASE_SERVICE_KEY  = <service_role key>   (server-side only; bypasses RLS)
       OWNER_USER_ID         = the auth.users UUID these rows belong to
       SQLITE_PATH           = path to my_db.db  (default: ./my_db.db)

Run:  python scripts/import_my_db.py
"""
import os
import sqlite3
import datetime
import calendar
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SQLITE_PATH = os.getenv("SQLITE_PATH", "my_db.db")
OWNER = os.getenv("OWNER_USER_ID")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

KNOWN_ACCOUNTS = {
    "CORRENTE": "checking",
    "SANTANDER": "card",
    "ITAU": "checking",
    "POUPANÇA": "savings",
}


# ---------- cleaning helpers ----------
def to_date(y, m, d):
    try:
        y, m, d = int(y), int(m), int(d)
    except (TypeError, ValueError):
        return None
    if not (1900 <= y <= 2100) or not (1 <= m <= 12):
        return None
    # clamp day to the actual last day of that month
    last_day = calendar.monthrange(y, m)[1]
    d = max(1, min(d, last_day))
    return datetime.date(y, m, d).isoformat()


def clean_amount(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def clean_ts(v):
    if not v:
        return None
    s = str(v).strip()
    if not s or s.startswith("1900"):
        return None
    # reject anything that doesn't look like a date/timestamp
    if len(s) < 10 or s[4:5] != "-" or s[7:8] != "-":
        return None
    try:
        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    except ValueError:
        return None
    last_day = calendar.monthrange(y, m)[1]
    d = max(1, min(d, last_day))
    return f"{y:04d}-{m:02d}-{d:02d}" + s[10:]


def nz(v):
    return (str(v).strip() or None) if v is not None else None


# ---------- upsert a lookup table and return {name: id} ----------
def upsert_lookup(table, names, extra=lambda n: {}):
    rows = [{"owner_id": OWNER, "name": n, **extra(n)} for n in sorted(names) if n]
    if rows:
        sb.table(table).upsert(rows, on_conflict="owner_id,name").execute()
    got = sb.table(table).select("id,name").eq("owner_id", OWNER).execute().data
    return {r["name"]: r["id"] for r in got}


def main():
    if not OWNER:
        raise SystemExit("ERROR: OWNER_USER_ID is not set in .env")

    con = sqlite3.connect(SQLITE_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    src = [dict(r) for r in cur.execute("SELECT * FROM tb_event")]
    print(f"read {len(src):,} legacy events")

    cats = {nz(r["grouped"]) for r in src if nz(r["grouped"])}
    projs = {nz(r["operation"]) for r in src if nz(r["operation"])}
    cat_id = upsert_lookup("categories", cats)
    proj_id = upsert_lookup("projects", projs)
    acc_id = upsert_lookup(
        "accounts",
        KNOWN_ACCOUNTS.keys(),
        extra=lambda n: {"kind": KNOWN_ACCOUNTS[n], "currency": "BRL"},
    )

    tx = []
    skipped = 0
    for r in src:
        amt = clean_amount(r["total"])
        if amt is None:
            skipped += 1
            continue
        bank = nz(r["bank"])
        tx.append({
            "owner_id":    OWNER,
            "legacy_code": r["code"],
            "occurred_on":  to_date(r["year"], r["month"], r["day"]),
            "purchase_date": clean_ts(r["purchase_date"]),
            "amount":       amt,
            "currency":    "BRL",
            "direction":   "income" if amt > 0 else "expense",
            "category_id": cat_id.get(nz(r["grouped"])),
            "label":       nz(r["description"]),
            "merchant":    nz(r["details"]),
            "project_id":  proj_id.get(nz(r["operation"])),
            "account_id":  acc_id.get(bank) if bank in KNOWN_ACCOUNTS else None,
            "account_raw": bank,
            "card":        nz(r["code_card"]),
            "bill_cycle":  nz(r["code_bill"]),
            "installments":nz(r["installments"]),
            "cleared":     r["done"] == 1,
            "cleared_on":  clean_ts(r["done_date"]),
            "created_at":  clean_ts(r["created_at"]) or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at":  clean_ts(r["last_update_at"]),
        })

    print(f"skipped {skipped:,} rows with unparseable amounts")

    for i in range(0, len(tx), 500):
        sb.table("transactions").upsert(tx[i : i + 500], on_conflict="owner_id,legacy_code").execute()
        print(f"  upserted {min(i + 500, len(tx)):,}/{len(tx):,}")

    feelings = [
        {
            "feeling":   r["Sentimento"],
            "sensation": r["Sensacao"],
            "emotion":   r["Emocao"],
        }
        for r in cur.execute("SELECT * FROM tb_feelings")
    ]
    if feelings:
        sb.table("feelings_taxonomy").insert(feelings).execute()
        print(f"inserted {len(feelings)} feelings taxonomy rows")

    moods = [
        {
            "owner_id":    OWNER,
            "feeling":     r["sentimento"],
            "sensation":   r["sensacao"],
            "emotion":     r["emocao"],
            "occurred_at": clean_ts(r["datahora"]),
            "notes":       r["detalhes"],
        }
        for r in cur.execute("SELECT * FROM tb_records")
    ]
    if moods:
        sb.table("mood_entries").insert(moods).execute()

    print(f"\ndone. transactions={len(tx):,}, moods={len(moods):,}")
    con.close()


if __name__ == "__main__":
    main()
