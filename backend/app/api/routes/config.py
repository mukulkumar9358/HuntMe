from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings_dep
from app.core.game_rules import game_config

router = APIRouter(tags=["config"])


@router.get("/game-config")
async def get_game_config(settings: Settings = Depends(get_settings_dep)) -> dict:
    """Official limits and defaults. The frontend renders its forms from this, never from constants."""
    return game_config(settings)
