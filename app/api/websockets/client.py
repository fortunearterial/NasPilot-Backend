from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from requests import Session

from db import get_db
from db.user_oper import get_current_websocket_user
from schemas import User
from app.api.websockets import ConnectionManager

router = APIRouter()


@router.websocket("/event", name="S2P事件")
async def client_event(
        websocket: WebSocket,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_websocket_user),
) -> Any:
    """
    P2S事件
    """
    await ConnectionManager().connect(current_user.id, websocket)
    # try:
    #     while True:
    #         data = await websocket.receive_json()
    #         await ConnectionManager().receive(current_user.id, data)
    # except WebSocketDisconnect as e:
    #     print("Got an exception ", e)
    #     await ConnectionManager().disconnect(current_user.id, websocket)
