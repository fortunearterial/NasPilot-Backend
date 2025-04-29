import asyncio
import uuid
from asyncio import Future, Task
from datetime import datetime

import json
from fastapi import WebSocket
from pyhessian2 import Encoder
from starlette.websockets import WebSocketDisconnect

from app.utils.singleton import Singleton


class ConnectionManager(metaclass=Singleton):
    _active_connections: dict[int, WebSocket] = {}
    _active_requests: dict[str, dict] = {}

    def __init__(self):
        super().__init__()

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if self._active_connections.get(user_id):
            await self._active_connections.get(user_id).close(10001, "发起了重复的连接请求")
        self._active_connections[user_id] = websocket
        print("New Active connections are ", self._active_connections)
        try:
            while True:
                data = await websocket.receive_json()
                request_id = data.get('_request_id')
                del data['_request_id']
                print(f"{request_id} {datetime.now()} Received response: {data}")
                self._active_requests[request_id][websocket].update({'response_data': data})
        except WebSocketDisconnect as e:
            print("Got an exception ", e)
            await self.disconnect(user_id, websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket):
        del self._active_connections[user_id]
        print("After disconnect active connections are: ", self._active_connections)

    async def send(self, user_id: int, request_data: dict, timeout: int = 5):
        # 生成唯一请求ID
        request_id = str(uuid.uuid4())
        self._active_requests[request_id] = dict()

        websocket = self._active_connections.get(user_id)
        if not websocket:
            raise Exception("No active connection")

        results = None
        try:
            results = self._send(websocket, request_id, request_data, timeout)
        except WebSocketDisconnect as e:
            print("Got an exception ", e)
            await self.disconnect(user_id, websocket)
        del self._active_requests[request_id]
        return results

    async def broadcast(self, request_data: dict, timeout: int = 5):
        # 生成唯一请求ID
        request_id = str(uuid.uuid4())
        self._active_requests[request_id] = dict()

        if not self._active_connections.keys():
            raise Exception("No active connections")

        results = []
        for user_id, websocket in self._active_connections.items():
            try:
                results.extend(await self._send(websocket, request_id, request_data, timeout))
            except WebSocketDisconnect as e:
                print("Got an exception ", e)
                await self.disconnect(user_id, websocket)
        del self._active_requests[request_id]
        return results

    async def _send(self, websocket: WebSocket, request_id: str, request_data: dict, timeout: int = 5):
        print(
            f"Request({request_id}) {datetime.now()} at Client({websocket.headers.get('ClientId')}) Sending data... {request_data}")
        start = datetime.now()
        # 准备发送请求
        send_request_data = {'_request_id': request_id}
        send_request_data.update(**request_data)
        # 发送消息
        await websocket.send(Encoder().encode(send_request_data))
        self._active_requests[request_id][websocket] = {
            "request_data": request_data,
        }
        while True:
            now = datetime.now()
            if (now - start).seconds > timeout:
                raise Exception("Timeout")
            # 等待响应
            await asyncio.sleep(0.3)
            if self._active_requests[request_id].get(websocket):
                response_data = self._active_requests[request_id].get(websocket).get('response_data')
                if response_data:
                    print(
                        f"Request({request_id}) {datetime.now()} at Client({websocket.headers.get('ClientId')}) Received data... {request_data}")
                    del self._active_requests[request_id][websocket]
                    return response_data
