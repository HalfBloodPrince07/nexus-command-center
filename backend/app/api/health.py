from fastapi import APIRouter

from backend.config import settings
from backend.core.personality import get_active_personality_config
from backend.core.system_metrics import get_system_metrics

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/personality")
def get_personality():
    config = get_active_personality_config()
    if config is None:
        return {
            "name": "supervisor",
            "display_name": "Nexus",
            "tagline": "Supervisor Agent",
            "ui_config": {"color": "#3498db", "icon": "sparkles"},
            "loaded_at": None,
            "app_name": settings.APP_NAME,
        }
    return {
        "name": config.name,
        "display_name": config.display_name,
        "tagline": config.tagline,
        "ui_config": config.ui,
        "loaded_at": config.loaded_at,
        "app_name": settings.APP_NAME,
    }


@router.get("/system/metrics")
def system_metrics():
    return get_system_metrics()
