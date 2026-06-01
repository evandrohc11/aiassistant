"""
app/routers/tasks.py — CRUD for tasks table.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.supabase_client import get_client

router = APIRouter(prefix="/tasks", tags=["tasks"])

OWNER = settings.owner_user_id


# ── models ─────────────────────────────────────────────────────────────────

class TaskIn(BaseModel):
    title: str
    due_date: Optional[date] = None
    notes: Optional[str] = None
    status: str = "open"


class TaskPatch(BaseModel):
    title: Optional[str] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class TaskOut(TaskIn):
    id: UUID
    created_at: str


# ── endpoints ──────────────────────────────────────────────────────────────

@router.post("/", response_model=TaskOut, status_code=201)
async def create_task(body: TaskIn) -> TaskOut:
    if body.status not in ("open", "done", "cancelled"):
        raise HTTPException(status_code=422, detail="status must be open | done | cancelled")

    db = get_client()
    payload = body.model_dump()
    payload["owner_id"] = OWNER
    if payload.get("due_date"):
        payload["due_date"] = str(payload["due_date"])

    res = db.table("tasks").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Insert failed")
    row = res.data[0]
    return TaskOut(**{**body.model_dump(), "id": row["id"], "created_at": row["created_at"]})


@router.get("/", response_model=list[dict])
async def list_tasks(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    db = get_client()
    q = (
        db.table("tasks")
        .select("id,title,status,due_date,notes,created_at")
        .eq("owner_id", OWNER)
        .order("due_date", desc=False, nullsfirst=False)
        .limit(limit)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


@router.patch("/{task_id}", response_model=dict)
async def update_task(task_id: UUID, body: TaskPatch) -> dict:
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")
    if "due_date" in changes:
        changes["due_date"] = str(changes["due_date"])
    if "status" in changes and changes["status"] not in ("open", "done", "cancelled"):
        raise HTTPException(status_code=422, detail="status must be open | done | cancelled")

    db = get_client()
    res = (
        db.table("tasks")
        .update(changes)
        .eq("id", str(task_id))
        .eq("owner_id", OWNER)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Task not found")
    return res.data[0]


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: UUID) -> None:
    db = get_client()
    db.table("tasks").delete().eq("id", str(task_id)).eq("owner_id", OWNER).execute()
