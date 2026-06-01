#!/usr/bin/env python3
"""
Import from CSV exports (item.csv, description.csv, cards.csv) into Supabase v2 schema.

Prereqs:
  1. Run supabase_schema.sql in Supabase SQL editor first (drop all + recreate).
  2. Set .env with SUPABASE_URL, SUPABASE_SERVICE_KEY, OWNER_USER_ID.
  3. CSVs must be in the project root: item.csv, description.csv, cards.csv

Run: python scripts/import_from_csv.py
"""
import os
import csv
import json
import datetime
import calendar
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

OWNER = os.environ["OWNER_USER_ID"]
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def nz(v: str) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("none", "nan", "") else None


def clean_date(v) -> str | None:
    """Parse and clamp any date-like string to YYYY-MM-DD; return None if invalid."""
    if not v:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("none", "nan", ""):
        return None
    # strip time part if present
    s = s.split(" ")[0].split("T")[0]
    if len(s) < 10 or s[4:5] != "-" or s[7:8] != "-":
        return None
    try:
        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    except ValueError:
        return None
    if not (1900 <= y <= 2100) or not (1 <= m <= 12):
        return None
    last_day = calendar.monthrange(y, m)[1]
    d = max(1, min(d, last_day))
    return f"{y:04d}-{m:02d}-{d:02d}"


def clean_date_parts(year, month, day) -> str | None:
    try:
        y, m, d = int(year), int(month), int(day)
    except (TypeError, ValueError):
        return None
    if not (1900 <= y <= 2100) or not (1 <= m <= 12):
        return None
    last_day = calendar.monthrange(y, m)[1]
    d = max(1, min(d, last_day))
    return datetime.date(y, m, d).isoformat()


def normalize_direction(type_val: str) -> str:
    """'Entrada' → income; everything else → expense."""
    return "income" if str(type_val).strip().lower() == "entrada" else "expense"


def normalize_routine(v: str) -> bool:
    return str(v).strip().upper() in ("YES", "X", "XXXX", "XXX")


def normalize_group(name: str) -> str:
    """Fix obvious encoding/typo duplicates in group names."""
    FIXES = {
        "ALIMENTACAO": "ALIMENTAÇÃO",
        "ALIMENTSSSS": "ALIMENTAÇÃO",
        "QUALIFICACAO": "QUALIFICAÇÃO",
        "ASSINATURA": "ASSINATURAS",
        "COMIDA": "ALIMENTAÇÃO",
    }
    return FIXES.get(name.strip().upper(), name.strip().upper())


def upsert_batch(table: str, rows: list, batch=500):
    for i in range(0, len(rows), batch):
        sb.table(table).upsert(rows[i:i+batch]).execute()
    print(f"  {table}: {len(rows):,} rows upserted")


# ──────────────────────────────────────────────
# Load CSVs
# ──────────────────────────────────────────────

def load_csv(filename: str) -> list[dict]:
    path = os.path.join(BASE, filename)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    desc_rows  = load_csv("description.csv")
    cards_rows = load_csv("cards.csv")
    item_rows  = load_csv("item.csv")
    print(f"Loaded: {len(desc_rows)} labels, {len(cards_rows)} cards, {len(item_rows):,} items")

    # ── 1. Cards ────────────────────────────────
    cards_data = []
    for r in cards_rows:
        cid = nz(r["id"])
        name = nz(r["card"])
        if not cid or not name:
            continue
        close = None
        try:
            close = int(float(r["day_close"])) if nz(r["day_close"]) else None
        except (ValueError, TypeError):
            pass
        cards_data.append({
            "id":        int(cid),
            "owner_id":  OWNER,
            "name":      name,
            "active":    str(r.get("active", "True")).strip().lower() == "true",
            "close_day": close,
        })
    upsert_batch("cards", cards_data)

    # ── 2. Accounts (from unique bank values in item.csv) ──
    ACCOUNT_KIND = {
        "CORRENTE":     "checking",
        "POUPANÇA":     "savings",
        "SANTANDER":    "card",
        "SANTANDER 2":  "card",
        "ITAU":         "card",
        "MERCADO PAGO": "card",
        "NUBANK":       "card",
        "CAIXA":        "checking",
        "FLUXO TOMAS":  "other",
        "Espiculas":    "other",
        "SA":           "other",
    }
    bank_names = {nz(r["bank"]) for r in item_rows if nz(r["bank"]) and nz(r["bank"]).lower() != "none"}
    accounts_data = []
    for name in sorted(bank_names):
        accounts_data.append({
            "owner_id": OWNER,
            "name":     name,
            "kind":     ACCOUNT_KIND.get(name, "other"),
            "currency": "BRL",
        })
    # upsert on (owner_id, name)
    for row in accounts_data:
        sb.table("accounts").upsert(row, on_conflict="owner_id,name").execute()
    print(f"  accounts: {len(accounts_data)} rows upserted")

    # Build account name → id map
    acc_map = {}
    res = sb.table("accounts").select("id,name").eq("owner_id", OWNER).execute()
    for row in res.data:
        acc_map[row["name"]] = row["id"]

    # ── 3. Categories (from description.group, normalized) ──
    groups = {normalize_group(r["group"]) for r in desc_rows if nz(r["group"])}
    # Determine kind from description types
    income_groups = set()
    for r in desc_rows:
        if normalize_direction(r.get("type", "")) == "income":
            income_groups.add(normalize_group(r["group"]) if nz(r["group"]) else "")
    cats_data = []
    for g in sorted(groups):
        kind = "income" if g in income_groups else "expense"
        cats_data.append({"owner_id": OWNER, "name": g, "kind": kind})
    for row in cats_data:
        sb.table("categories").upsert(row, on_conflict="owner_id,name").execute()
    print(f"  categories: {len(cats_data)} rows upserted")

    # Build category name → id map
    cat_map = {}
    res = sb.table("categories").select("id,name").eq("owner_id", OWNER).execute()
    for row in res.data:
        cat_map[row["name"]] = row["id"]

    # ── 4. Labels (description.csv) ──────────────
    labels_data = []
    label_id_map: dict[int, dict] = {}  # id → {label, category_id}
    for r in desc_rows:
        lid = nz(r["id"])
        name = nz(r["description"])
        if not lid or not name:
            continue
        grp = normalize_group(r["group"]) if nz(r["group"]) else None
        cat_id = cat_map.get(grp) if grp else None
        lid_int = int(lid)
        label_id_map[lid_int] = {"label": name, "category_id": cat_id}
        labels_data.append({
            "id":          lid_int,
            "owner_id":    OWNER,
            "name":        name,
            "category_id": cat_id,
            "is_routine":  normalize_routine(r.get("routine", "")),
            "active":      str(r.get("active", "True")).strip().lower() == "true",
        })
    upsert_batch("labels", labels_data)

    # ── 5. Transactions (item.csv) ───────────────
    tx = []
    skipped = 0
    for r in item_rows:
        # amount
        try:
            amount = float(r["total"])
        except (ValueError, TypeError):
            skipped += 1
            continue

        # label FK
        did = nz(r["description_id"])
        did_int = int(did) if did else None
        lbl_info = label_id_map.get(did_int, {}) if did_int else {}

        # account
        bank = nz(r["bank"])
        acc_id = acc_map.get(bank) if bank else None

        # card
        cid = nz(r["card_id"])
        card_id = int(cid) if cid else None

        # direction
        direction = normalize_direction(r.get("type", "Saída"))

        tx.append({
            "owner_id":        OWNER,
            "legacy_id":       int(r["id"]),
            "occurred_on":     clean_date_parts(r["year"], r["month"], r["day"]),
            "purchase_date":   clean_date(r.get("purchase_date")),
            "management_date": clean_date(r.get("data_gerencial")),
            "amount":          amount,
            "currency":        "BRL",
            "direction":       direction,
            "label_id":        did_int,
            "label":           lbl_info.get("label"),
            "category_id":     lbl_info.get("category_id"),
            "details":         nz(r.get("details")),
            "notes":           nz(r.get("operation")),
            "account_id":      acc_id,
            "account_raw":     bank,
            "card_id":         card_id,
            "bill_cycle":      nz(r.get("code_bill")),
            "installments":    nz(r.get("installments")),
            "cleared":         str(r.get("done", "FALSE")).strip().upper() == "TRUE",
            "cleared_on":      clean_date(r.get("done_date")),
            "created_at":      r.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at":      clean_date(r.get("last_update_at")),
        })

    print(f"  skipped {skipped} rows with unparseable amounts")

    # Upsert in batches (on_conflict = legacy_id unique)
    for i in range(0, len(tx), 500):
        sb.table("transactions").upsert(tx[i:i+500], on_conflict="legacy_id").execute()
        print(f"  transactions: upserted {min(i+500, len(tx)):,}/{len(tx):,}")

    print(f"\nDone. cards={len(cards_data)}, accounts={len(accounts_data)}, "
          f"categories={len(cats_data)}, labels={len(labels_data)}, "
          f"transactions={len(tx):,}, skipped={skipped}")


if __name__ == "__main__":
    main()
