"""
app/routers/transactions.py — CRUD + monthly summary for transactions.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.supabase_client import get_client

router = APIRouter(prefix="/transactions", tags=["transactions"])

OWNER = settings.owner_user_id


# ── request / response models ──────────────────────────────────────────────

class TransactionIn(BaseModel):
    occurred_on: date
    amount: float                        # always positive
    currency: str = "CAD"
    direction: str = "expense"           # 'income' | 'expense'
    label: Optional[str] = None          # human-readable label / merchant
    details: Optional[str] = None        # merchant / payee
    notes: Optional[str] = None          # free-text memo
    account_raw: Optional[str] = None
    category_id: Optional[UUID] = None
    label_id: Optional[int] = None
    account_id: Optional[UUID] = None
    card_id: Optional[int] = None
    cleared: bool = True


class TransactionOut(TransactionIn):
    id: UUID
    created_at: str


class SummaryRow(BaseModel):
    category: Optional[str]
    direction: str
    total: float
    count: int


# ── endpoints ──────────────────────────────────────────────────────────────

@router.post("/", response_model=TransactionOut, status_code=201)
async def create_transaction(body: TransactionIn) -> TransactionOut:
    if body.direction not in ("income", "expense"):
        raise HTTPException(status_code=422, detail="direction must be 'income' or 'expense'")

    db = get_client()
    payload = body.model_dump()
    payload["owner_id"] = OWNER
    payload["occurred_on"] = str(payload["occurred_on"])
    payload["category_id"] = str(payload["category_id"]) if payload.get("category_id") else None
    payload["account_id"] = str(payload["account_id"]) if payload.get("account_id") else None

    res = db.table("transactions").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Insert failed")
    row = res.data[0]
    return TransactionOut(**{**body.model_dump(), "id": row["id"], "created_at": row["created_at"]})


@router.get("/", response_model=list[dict])
async def list_transactions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    direction: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
) -> list[dict]:
    db = get_client()
    q = (
        db.table("transactions")
        .select("id,occurred_on,amount,currency,direction,label,details,notes,account_raw,cleared,created_at")
        .eq("owner_id", OWNER)
        .order("occurred_on", desc=True)
        .limit(limit)
        .offset(offset)
    )
    if direction:
        q = q.eq("direction", direction)
    if year and month:
        lo = f"{year:04d}-{month:02d}-01"
        hi = f"{year:04d}-{month:02d}-31"
        q = q.gte("occurred_on", lo).lte("occurred_on", hi)
    elif year:
        q = q.gte("occurred_on", f"{year:04d}-01-01").lte("occurred_on", f"{year:04d}-12-31")

    return q.execute().data or []


@router.get("/summary", response_model=list[SummaryRow])
async def monthly_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> list[SummaryRow]:
    """Return income vs expense totals per category for a given month."""
    db = get_client()
    lo = f"{year:04d}-{month:02d}-01"
    hi = f"{year:04d}-{month:02d}-31"

    rows = (
        db.table("transactions")
        .select("direction,amount,categories(name)")
        .eq("owner_id", OWNER)
        .gte("occurred_on", lo)
        .lte("occurred_on", hi)
        .execute()
        .data
    ) or []

    # aggregate in Python (Supabase free tier has no RPC group-by via REST)
    totals: dict[tuple, dict] = {}
    for r in rows:
        cat = (r.get("categories") or {}).get("name")
        key = (cat, r["direction"])
        if key not in totals:
            totals[key] = {"category": cat, "direction": r["direction"], "total": 0.0, "count": 0}
        totals[key]["total"] = round(totals[key]["total"] + abs(float(r["amount"])), 2)
        totals[key]["count"] += 1

    return sorted(totals.values(), key=lambda x: (-x["total"], x["direction"]))


@router.get("/{transaction_id}", response_model=dict)
async def get_transaction(transaction_id: UUID) -> dict:
    db = get_client()
    res = (
        db.table("transactions")
        .select("*")
        .eq("id", str(transaction_id))
        .eq("owner_id", OWNER)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return res.data
