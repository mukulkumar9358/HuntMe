from fastapi import APIRouter, Depends

from app.api.routes import auth, config, rooms, users
from app.core.dependencies import verify_origin

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_origin)])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(config.router)
api_router.include_router(rooms.router)
