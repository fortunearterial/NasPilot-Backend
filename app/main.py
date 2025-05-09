import multiprocessing
import os
import secrets
import socket
import sys
import threading
import asyncio
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import uvicorn as uvicorn
from PIL import Image
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
from uvicorn import Config

from app.factory import app
from app.utils.system import SystemUtils

# 禁用输出
if SystemUtils.is_frozen():
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

from app.core.config import settings
from app.db.init import init_db, update_db

# uvicorn服务
Server = uvicorn.Server(Config(app, host=settings.HOST, port=settings.PORT,
                               reload=settings.DEBUG, reload_dirs=[settings.APP_PATH],
                               log_level="debug" if settings.DEBUG else None, workers=multiprocessing.cpu_count(),
                               timeout_graceful_shutdown=5))


def start_tray():
    """
    启动托盘图标
    """

    if not SystemUtils.is_frozen():
        return

    if not SystemUtils.is_windows():
        return

    def open_web():
        """
        登录
        """
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # 解析回调中的 code 和 state
                query = urlparse(self.path).query
                params = parse_qs(query)
                code = params.get("code", [None])[0]
                state = params.get("state", [None])[0]

                # 验证 state 是否匹配
                if state != self.server.oauth.state:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Invalid state parameter")
                    return

                # 返回成功页面给用户
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorization successful! You can close this window.")

                # 将 code 传递给主线程
                self.server.authorization_code = code
                self.server.server_close()

        import os
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

        # 获取一个可用的端口
        def get_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))  # 绑定到所有接口的随机可用端口
                return s.getsockname()[1]  # 返回实际分配的端口号

        # 本地服务器用于接收回调
        def run_local_server(oauth, port=8080) -> int:
            server_address = ("", port)
            httpd = HTTPServer(server_address, CallbackHandler)
            httpd.oauth = oauth  # 传递 oauth 对象到 Handler
            httpd.authorization_code = None
            httpd.handle_request()  # 处理单个请求后自动停止
            return httpd.authorization_code

        code_verifier = secrets.token_urlsafe(64)
        port = get_free_port()
        redirect_uri = f"http://localhost:{port}/oauth/callback"

        # 创建 OAuth2Session 并生成授权 URL
        oauth = OAuth2Session(
            settings.CLIENT_ID,
            redirect_uri=redirect_uri,
            scope=["read"],
            state=secrets.token_urlsafe(16),  # 随机 state 防止 CSRF
        )
        authorization_url, _ = oauth.authorization_url(settings.APP_DOMAIN)
        # FIX authorization_url
        sch, net, path, par, query, fra = urlparse(authorization_url)
        authorization_url = f"{settings.APP_DOMAIN}/#/oauth/authorize?{query}"

        # 用浏览器打开授权页面
        print("请打开浏览器访问以下 URL 完成授权:")
        print(authorization_url)
        webbrowser.open(authorization_url)

        # 启动本地服务器等待回调
        print("等待授权回调...")
        code = run_local_server(oauth, port)

        if not code:
            print("未收到授权码")
            return

        # 使用授权码换取令牌
        token = oauth.fetch_token(
            f"{settings.APP_DOMAIN}/api/oauth/token",
            code=code,
            client_secret=settings.CLIENT_SECRET,
            code_verifier=code_verifier,  # PKCE 验证
            auth=HTTPBasicAuth(settings.CLIENT_ID, settings.CLIENT_SECRET),
        )

        # 使用令牌访问受保护资源
        response = oauth.get(f"{settings.APP_DOMAIN}/api/v1/user/current")
        print(f"用户信息: {response.json()}")
        settings.update_setting('CURRENT_USERID', response.json().get("id"))

        return token

    def quit_app():
        """
        退出程序
        """
        TrayIcon.stop()
        Server.should_exit = True

    import pystray

    # 托盘图标
    TrayIcon = pystray.Icon(
        settings.PROJECT_NAME,
        icon=Image.open(settings.ROOT_PATH / 'app.ico'),
        menu=pystray.Menu(
            pystray.MenuItem(
                '打开',
                open_web,
            ),
            pystray.MenuItem(
                '退出',
                quit_app,
            )
        )
    )
    # 启动托盘图标
    threading.Thread(target=TrayIcon.run, daemon=True).start()

if __name__ == '__main__':
    # 启动托盘
    start_tray()
    # 初始化数据库
    init_db()
    # 更新数据库
    update_db()
    # 启动API服务
    if settings.DEBUG:
        asyncio.run(Server.serve())
    else:
        Server.run()
