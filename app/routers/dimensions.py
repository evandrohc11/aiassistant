"""
app/routers/dimensions.py — CRUD for categories & labels; read-only for accounts/cards.
Used by the UI to populate dropdowns and the dimensions management page.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.supabase_client import get_client

router = APIRouter(prefix="/dimensions", tags=["dimensions"])
OWNER = settings.owner_user_id


# ── models ───────────────────────────────────────────────────────────────────

class CategoryIn(BaseModel):
    name: str
    kind: Optional[str] = None   # 'income' | 'expense' | 'transfer' | None


class LabelIn(BaseModel):
    name: str
    category_id: Optional[str] = None   # uuid string
    is_routine: bool = False
    active: bool = True


# ── read-only lookups (used by dropdowns) ────────────────────────────────────

@router.get("/categories")
async def list_categories() -> list[dict]:
    db = get_client()
    return db.table("categories").select("id,name,kind").eq("owner_id", OWNER).order("name").execute().data or []


@router.get("/accounts")
async def list_accounts() -> list[dict]:
    db = get_client()
    return db.table("accounts").select("id,name,kind,currency").eq("owner_id", OWNER).order("name").execute().data or []


@router.get("/labels")
async def list_labels() -> list[dict]:
    db = get_client()
    return db.table("labels").select("id,name,category_id,is_routine,active").eq("owner_id", OWNER).order("name").execute().data or []


@router.get("/cards")
async def list_cards() -> list[dict]:
    db = get_client()
    return db.table("cards").select("id,name,active").eq("owner_id", OWNER).order("name").execute().data or []


# ── category CRUD ─────────────────────────────────────────────────────────────

@router.post("/categories", status_code=201)
async def create_category(body: CategoryIn) -> dict:
    if body.kind and body.kind not in ("income", "expense", "transfer"):
        raise HTTPException(422, "kind must be income, expense, or transfer")
    db = get_client()
    res = db.table("categories").insert({"name": body.name, "kind": body.kind, "owner_id": OWNER}).execute()
    if not res.data:
        raise HTTPException(500, "Insert failed")
    return res.data[0]


@router.put("/categories/{cat_id}")
async def update_category(cat_id: str, body: CategoryIn) -> dict:
    if body.kind and body.kind not in ("income", "expense", "transfer"):
        raise HTTPException(422, "kind must be income, expense, or transfer")
    db = get_client()
    res = db.table("categories").update({"name": body.name, "kind": body.kind}).eq("id", cat_id).eq("owner_id", OWNER).execute()
    if not res.data:
        raise HTTPException(404, "Category not found")
    return res.data[0]


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(cat_id: str) -> None:
    db = get_client()
    db.table("categories").delete().eq("id", cat_id).eq("owner_id", OWNER).execute()


# ── label CRUD ────────────────────────────────────────────────────────────────

@router.post("/labels", status_code=201)
async def create_label(body: LabelIn) -> dict:
    db = get_client()
    payload = {"name": body.name, "category_id": body.category_id or None,
               "is_routine": body.is_routine, "active": body.active, "owner_id": OWNER}
    res = db.table("labels").insert(payload).execute()
    if not res.data:
        raise HTTPException(500, "Insert failed")
    return res.data[0]


@router.put("/labels/{label_id}")
async def update_label(label_id: int, body: LabelIn) -> dict:
    db = get_client()
    payload = {"name": body.name, "category_id": body.category_id or None,
               "is_routine": body.is_routine, "active": body.active}
    res = db.table("labels").update(payload).eq("id", label_id).eq("owner_id", OWNER).execute()
    if not res.data:
        raise HTTPException(404, "Label not found")
    return res.data[0]


@router.delete("/labels/{label_id}", status_code=204)
async def delete_label(label_id: int) -> None:
    db = get_client()
    db.table("labels").delete().eq("id", label_id).eq("owner_id", OWNER).execute()
