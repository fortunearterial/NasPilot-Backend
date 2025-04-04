from fastapi import APIRouter

from app.api.websockets import client

websocket_router = APIRouter()
websocket_router.include_router(client.router, prefix="/client", tags=["websocket"])
