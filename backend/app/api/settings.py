from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ModelSelect(BaseModel):
    model: str


@router.get("/models")
async def list_models():
    """Return models currently loaded in LM Studio."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.LM_STUDIO_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
    except Exception as exc:
        logger.warning("Could not fetch LM Studio models: %s", exc)
        models = []

    return {"models": models, "active": settings.lm_studio_model}


@router.get("/active-model")
async def get_active_model():
    return {"model": settings.lm_studio_model}


@router.post("/model")
async def set_model(body: ModelSelect):
    """Switch the active LM Studio model for all agents this session."""
    settings.LM_STUDIO_MODEL = body.model
    logger.info("Active model switched to: %s", body.model)
    return {"model": settings.lm_studio_model, "status": "updated"}
