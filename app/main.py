"""
app/main.py — FastAPI application entry point.
"""
import logging

from fastapi import FastAPI

from app.config import settings
from app.routers import webhook, transactions, tasks, ui, dimensions

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(title="Personal Assistant", version="0.3.0")

app.include_router(webhook.router)
app.include_router(transactions.router)
app.include_router(tasks.router)
app.include_router(dimensions.router)
app.include_router(ui.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
