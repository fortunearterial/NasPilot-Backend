import asyncio
import uuid
from asyncio import Future, Task
from datetime import datetime

from fastapi import WebSocket
from app.utils.singleton import Singleton


class ConnectionManager(metaclass=Singleton):
    _active_connections: dict[int, set[WebSocket]] = {}
    _pending_requests: dict[int, dict[str, set[Future]]] = {}
    _pending_lock = asyncio.Lock()

    def __init__(self):
        super().__init__()

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if not self._active_connections.get(user_id):
            self._active_connections[user_id] = set()
        if not self._pending_requests.get(user_id):
            self._pending_requests[user_id] = {}
        self._active_connections.get(user_id).add(websocket)
        print("New Active connections are ", self._active_connections)

    async def disconnect(self, user_id: int, websocket: WebSocket):
        self._active_connections.get(user_id).remove(websocket)
        print("After disconnect active connections are: ", self._active_connections)
        async with self._pending_lock:
            for req_id, futures in self._pending_requests.get(user_id).items():
                for future in futures:
                    future.cancel()
                del self._pending_requests.get(user_id)[req_id]

    async def send(self, user_id: int, request_data: dict):
        loop = asyncio.get_running_loop()
        # 生成唯一请求ID
        request_id = str(uuid.uuid4())
        # 创建Future对象用于异步等待
        futures = []
        request_data.update({'_request_id': request_id})
        websockets = self._active_connections.get(user_id)
        if websockets:
            print(f"{request_id} {datetime.now()} Sending request...")
            for websocket in websockets:
                # 创建Future对象用于异步等待
                futures.append(loop.create_future())
                # 发送消息
                await websocket.send_json(request_data)
            async with self._pending_lock:
                self._pending_requests.get(user_id)[request_id] = set(futures)
            # 等待客户端响应
            # TODO：一直超时
            response_datas = await asyncio.wait_for(
                asyncio.gather(*[asyncio.shield(fut) for fut in futures], return_exceptions=True),
                timeout=5
            )
            # 继续执行后续逻辑
            print(f"{request_id} {datetime.now()} Received responses: {response_datas}")
            # 清理资源
            async with self._pending_lock:
                del self._pending_requests.get(user_id)[request_id]
            return response_datas
        return None

    async def broadcast(self, request_data: dict):
        for user_id in self._active_connections.keys():
            await self.send(user_id, request_data)

    async def receive(self, user_id: int, response_data: dict):
        request_id = response_data.get('_request_id')
        print(f"{request_id} {datetime.now()} Received response: {response_data}")
        async with self._pending_lock:
            futures = self._pending_requests.get(user_id).get(request_id, set())
        # 为每个关联的 Future 设置结果
        for future in futures:
            if not future.done():
                future.add_done_callback(lambda f: print(f"{request_id} {datetime.now()} Done response: {f.result()}"))
                future.set_result(response_data.get('data'))
