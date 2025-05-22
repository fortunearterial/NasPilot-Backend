import datetime
import json
import time
import pickle
from typing import Optional, Dict
from urllib import parse

import requests
from playwright.sync_api import Request, Page

from app.log import logger
from app.helper.browser import PlaywrightHelper
from app.core.config import settings


class LoginFailed(BaseException):
    pass


class RemoteClient:
    __client_id: str = "Yd0uSVGrNJhCC2oE"

    _username: Optional[str] = None
    _password: Optional[str] = None
    _props: Optional[Dict] = None

    smscode: Optional[str] = None

    def __init__(self,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 ):
        self._username = username
        self._password = password

        self._load_props()

    def _save_props(self):
        """
        保存数据
        """
        try:
            (settings.CONFIG_PATH / "thunder").mkdir(parents=True, exist_ok=True)
            with open(settings.CONFIG_PATH / "thunder" / f'{self._username}.db', 'wb') as f:
                pickle.dump(self._props, f)  # noqa
        except Exception as err:
            logger.error(f"保存迅雷数据出错：{str(err)}")

    def _load_props(self):
        """
        保存数据
        """
        try:
            with open(settings.CONFIG_PATH / "thunder" / f'{self._username}.db', 'rb') as f:
                self._props = pickle.load(f)  # noqa
            logger.debug(f"读取迅雷数据成功：{self._props}")
        except Exception as err:
            self._props = {}

    def auth_log_in(self):
        # 登录
        try:
            if self._props and \
                    self._props.get("captcha.expires_at") and \
                    self._props.get("credentials.expires_at") and \
                    self._props.get("init.client_id"):
                return

            logger.info(f"正在连接 thunder：{self._username}")
            PlaywrightHelper().action(
                url="https://pan.xunlei.com/yc/home",
                headless=not settings.DEBUG,
                ua="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/136.0.0.0",
                callback=self.__login_callback,
                user_data_dir=str(settings.CONFIG_PATH / "thunder/browser_data" / self._username),
            )
            self._save_props()
        except Exception as err:
            logger.error(f"thunder 连接出错：{str(err)}")

    def __login_callback(self, page: Page):
        """
        登录回调
        """

        def request_handler(request: Request):
            if request.url == "https://xluser-ssl.xunlei.com/v1/shield/captcha/init":
                captcha_data = request.post_data_json
                self._props.update({
                    "init.client_id": captcha_data["client_id"],
                    "init.device_id": captcha_data["device_id"],
                    "init.meta": captcha_data.get("meta")
                })
                logger.debug(f"获取到init数据：{self._props}")

            try:
                authorization = request.header_value('authorization')
                if authorization:
                    token_type, access_token = authorization.split(' ')
                    self._props.update({
                        "credentials.token_type": token_type,
                        "credentials.access_token": access_token,
                    })
                    logger.debug(f"获取到credentials数据：{self._props}")
            except Exception:
                pass

        try:
            # 未登录
            if page.is_visible("span.button-login:has-text('立即登录')"):
                logger.info(f"开始登录")
                page.on("request", request_handler)
                # 跳转登录页面
                page.click("span.button-login:has-text('立即登录')")
                # 点击账号密码登录
                page.click("span:has-text('账号密码登录')")
                # 输入账号密码
                page.fill("input.xlubase-login-input[type='text']", self._username)
                page.fill("input.xlubase-login-input[type='password']", self._password)
                page.click("input.xlucommon-login-checkbox")
                # 点击登录
                page.click("button.xlucommon-login-button")
                # 检测是否有错误信息
                if page.is_visible("p.xlucommon-login-note"):
                    raise LoginFailed(page.query_selector("p.xlucommon-login-note").text_content())
                # 是否有短信验证
                if page.is_visible("h3:has-text('请进行短信验证')"):
                    page.click("span.get-validate-code")
                    while not self.smscode:
                        time.sleep(1)
                    page.fill("input.xlubase-login-input[type='text']", self.smscode)
                    page.click("button.xlucommon-login-button")

            logger.info(f"已登录，开始获取客户端信息")
            time.sleep(5)
            local_storage = None
            while not local_storage:
                try:
                    local_storage = page.evaluate('localStorage')
                except Exception:
                    time.sleep(1)

            logger.info(f"客户端信息： {local_storage}")
            for key in local_storage:
                if 'captcha_' + self.__client_id == key:
                    captcha = json.loads(local_storage[key])
                    captcha['expires_at'] = datetime.datetime.strptime(captcha['expires_at'],
                                                                       '%Y-%m-%dT%H:%M:%S.%fZ')
                    for k in captcha:
                        self._props.update({
                            "captcha." + k: captcha[k]
                        })
                    logger.debug(f"获取到captcha数据：{self._props}")
                if 'credentials_' + self.__client_id == key:
                    credentials = json.loads(local_storage[key])
                    credentials['expires_at'] = datetime.datetime.strptime(credentials['expires_at'],
                                                                           '%Y-%m-%dT%H:%M:%S.%fZ')
                    for k in credentials:
                        self._props.update({
                            "credentials." + k: credentials[k]
                        })
                    logger.debug(f"获取到credentials数据：{self._props}")
            self._refresh_props()
        except Exception as err:
            raise LoginFailed(f"thunder 登录出错：{str(err)}")

    def __headers(self):
        if not self._props.get('credentials.token_type') or \
                not self._props.get('credentials.access_token'):
            raise Exception("未取到credentials")
        return {
            'authorization': self._props.get('credentials.token_type') + ' ' + self._props.get(
                'credentials.access_token'),
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://pan.xunlei.com',
            'referer': 'https://pan.xunlei.com/',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/136.0.0.0',
            'x-captcha-token': self._props.get('captcha.token'),
            'x-client-id': self.__client_id,
            'x-device-id': self._props.get('init.device_id'),
        }

    def __request(self, method: str, url: str, **kwargs):
        """
        检查响应
        """
        response = requests.request(method, url, headers=self.__headers(), **kwargs)
        data = response.json()
        if data.get("error") == "unauthenticated":
            # 重新登录
            self._props = {
                "init.client_id": self._props.get("init.client_id"),
                "init.device_id": self._props.get("init.device_id"),
                "init.meta": self._props.get("init.meta"),
            }
            self._save_props()
            self.auth_log_in()
            return self.__request(method, url, **kwargs)
        if data.get("error") == "external_unknown_err":
            # 客户端离线
            raise RuntimeError(f"迅雷客户端不在线，请检查客户端状态！")
        if data.get("error_code"):
            raise Exception(f"thunder 请求出错：{data.get('error_description')}")
        if response.status_code != 200:
            raise Exception(f"thunder 请求出错：{response.text}")
        return data

    def _refresh_props(self):
        expire_time = self._props.get('captcha.expires_at')
        if expire_time:
            expire_time = int(expire_time.timestamp())
        if not expire_time or expire_time < int(time.time()):
            logger.info('[INFO]更新 captcha_token')
            url = "https://xluser-ssl.xunlei.com/v1/shield/captcha/init"
            device = {
                "action": "get:/drive/v1/tasks",
                "client_id": self.__client_id,
                "device_id": self._props.get('init.device_id'),
                "meta": self._props.get('init.meta', {}),
            }
            headers = {
                'content-type': 'application/json',
                'origin': 'https://pan.xunlei.com',
                'referer': 'https://pan.xunlei.com/',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/136.0.0.0',
            }
            response = requests.request("POST", url, headers=headers, data=json.dumps(device))
            response = json.loads(response.text)
            self._props.update({
                "captcha.token": response.get('captcha_token'),
                "captcha.expires_at": time.time() + response.get('expires_in', 0)
            })
            logger.info('[INFO]新的 captcha_token: ' + response.get('captcha_token'))
            self._save_props()

    # @cached(maxsize=1000, ttl=3600)
    def get_devices(self) -> list[Dict]:
        """
        {
            "tasks": [
                {
                    "kind": "drive#task",
                    "id": "VOQWrehqyejpfoTXfiIhPyilA1",
                    "name": "群晖-SynologyUat",
                    "type": "user#runner",
                    "user_id": "625200512",
                    "statuses": [],
                    "status_size": 0,
                    "params": {
                        "accept": "true",
                        "access": "user#app,user#download,user#download-url,user#nfo",
                        "arch": "amd64",
                        "client_id": "X9ibISwpIp8jQ4Ya",
                        "client_version": "3.21.0",
                        "device_config": "{\"device_space\":\"\",\"speed_limit\":-1,\"runner_count\":5,\"download_infos\":null,\"download_paths\":[\"/downloads/\"],\"access_task_type\":null,\"file_mount\":{},\"single_task_max_mb\":100,\"single_task_reserve_mb\":20,\"overall_share_max_mb\":200}",
                        "device_model": "geminilake dsm 7.2-64570",
                        "downloads": "[{\"name\":\"\",\"path\":\"/downloads/\",\"usage\":1838555496448,\"limit\":1908995522560,\"errmsg\":\"\",\"is_root_path\":false},{\"name\":\"\",\"path\":\"/data/\",\"usage\":17248247808,\"limit\":54609838080,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/usr/bin/\",\"usage\":17248247808,\"limit\":54609838080,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/usr/lib/\",\"usage\":17248247808,\"limit\":54609838080,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/run/\",\"usage\":17248247808,\"limit\":54609838080,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/tmp/\",\"usage\":17248247808,\"limit\":54609838080,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/usr/lib64/\",\"usage\":17248247808,\"limit\":54609838080,\"errmsg\":\"\",\"is_root_path\":true}]",
                        "ip": "58.48.105.9",
                        "os": "linux",
                        "package_name": "pan.xunlei.cli.synology",
                        "platform": "synology",
                        "plm": "syn",
                        "product_name": "群晖",
                        "round": "8",
                        "sleeper": "timer:10m0s<17m0s<20m0s",
                        "start_at": "2025/05/18 13:29:48",
                        "sync": "true",
                        "target": "device_id#94082a79c0fee7fef301911ae6769783",
                        "version": "3.21.0"
                    },
                    "file_id": "",
                    "file_name": "群晖-SynologyUat",
                    "file_size": "0",
                    "message": "已添加",
                    "created_time": "2025-05-18T13:29:48.662+08:00",
                    "updated_time": "2025-05-18T15:07:50.530+08:00",
                    "third_task_id": "",
                    "phase": "PHASE_TYPE_RUNNING",
                    "progress": 0,
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/05e4f2d4a751f1895746a15da2d391105418a66d",
                    "callback": "",
                    "reference_resource": null,
                    "space": ""
                },
                {
                    "kind": "drive#task",
                    "id": "VOGOriFNLxj91U50InTjwY7jA1",
                    "name": "极空间-T2-YZWN-18627176816",
                    "type": "user#runner",
                    "user_id": "625200512",
                    "statuses": [],
                    "status_size": 0,
                    "params": {
                        "accept": "true",
                        "access": "user#app,user#download,user#download-url",
                        "arch": "arm64",
                        "client_id": "X9ibISwpIp8jQ4Ya",
                        "client_version": "3.23.2",
                        "device_config": "{\"custom_device_name\":\"\",\"device_space\":\"18627176816\",\"speed_limit\":-1,\"runner_count\":5,\"download_infos\":[{\"name\":\"\",\"path\":\"/tmp/zfsv3/nvme11/18627176816/data\",\"usage\":0,\"limit\":3522571624448,\"errmsg\":\"\",\"is_root_path\":false}],\"download_paths\":[\"/tmp/zfsv3/nvme11/18627176816/data/\"],\"filter_paths\":null,\"access_task_type\":null,\"file_mount\":{\"/tmp/zfsv3/nvme11/18627176816/data\":\"M.2存储/\"},\"single_task_max_mb\":200,\"single_task_reserve_mb\":30,\"overall_share_max_mb\":500}",
                        "device_model": "zspace",
                        "downloads": "[{\"name\":\"\",\"path\":\"/tmp/zfsv3/nvme11/18627176816/data/\",\"usage\":0,\"limit\":3522571624448,\"errmsg\":\"\",\"is_root_path\":false},{\"name\":\"\",\"path\":\"/data_n001/\",\"usage\":275678674944,\"limit\":2022637375488,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/data_n002/\",\"usage\":277166198784,\"limit\":2022637375488,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/zspace/zsrp/\",\"usage\":18092032,\"limit\":20940668928,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/zspace/\",\"usage\":3394408448,\"limit\":12615557120,\"errmsg\":\"\",\"is_root_path\":true},{\"name\":\"\",\"path\":\"/zspace/applications/logs/\",\"usage\":115298304,\"limit\":1023303680,\"errmsg\":\"\",\"is_root_path\":true}]",
                        "ip": "122.188.50.251",
                        "last_patch_runner": "2025/01/14 10:02:11",
                        "os": "linux",
                        "package_name": "pan.xunlei.cli.zspace",
                        "platform": "zspace",
                        "plm": "jkj",
                        "product_name": "极空间",
                        "round": "43",
                        "sleeper": "timer:10m0s<20m0s<20m0s",
                        "start_at": "2025/01/12 17:36:07",
                        "sync": "true",
                        "sync_error": "<nil>",
                        "target": "device_id#eb831f54b59dc8b0534114246dd1713f",
                        "version": "3.23.2"
                    },
                    "file_id": "",
                    "file_name": "极空间-T2-YZWN-18627176816",
                    "file_size": "0",
                    "message": "任务超时，请重试",
                    "created_time": "2025-01-12T17:36:07.192+08:00",
                    "updated_time": "2025-01-14T10:32:34.910+08:00",
                    "third_task_id": "",
                    "phase": "PHASE_TYPE_ERROR",
                    "progress": 0,
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/05e4f2d4a751f1895746a15da2d391105418a66d",
                    "callback": "",
                    "reference_resource": null,
                    "space": "platform#zspace"
                }
            ],
            "next_page_token": "",
            "expires_in": 5,
            "expires_in_ms": 5000
        }
        """

        response = self.__request(
            method="GET",
            url="https://api-pan.xunlei.com/drive/v1/tasks?type=user%23runner&space=",
        )
        return response.get('tasks')

    def get_device(self, name: str):
        devices = self.get_devices()
        filter_devices = list(filter(lambda x: x.get('name') == name, devices))
        if len(filter_devices) == 0:
            raise Exception(f"无法找到名称为{name}的远程设备，请检查配置")
        return filter_devices[0]

    # @cached(maxsize=1000, ttl=3600)
    def _get_innerapi(self, device: dict):
        """
        {
            "id": "INNER_API",
            "name": "内部api",
            "access": [],
            "link": "https://vod3946-a02xllite-vip-lixian.xunlei.com/drive-reverse-proxy/v1/proxyToken/5adbe/1747552997/DFdnOzovvp33v9BXQ9kWFPdOxNQ=/625200512/94082a79c0fee7fef301911ae6769783/assets/apps/INNER_API/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
            "redirect_link": "",
            "vip_types": [],
            "need_more_quota": false,
            "icon_link": "",
            "is_default": false,
            "params": {
                "author": "",
                "description": "",
                "device_space": "",
                "is_buildin": "false",
                "is_local": "true",
                "pid": "0",
                "status": "running",
                "ui_port": "0",
                "version": "v1.0.0",
                "work_dir": ""
            },
            "category_ids": [],
            "ad_scene_type": 0,
            "space": "",
            "links": {
                "application/local-172.17.0.1": {
                    "url": "http://172.17.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.18.0.1": {
                    "url": "http://172.18.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.19.0.1": {
                    "url": "http://172.19.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.20.0.1": {
                    "url": "http://172.20.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.21.0.1": {
                    "url": "http://172.21.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.22.0.1": {
                    "url": "http://172.22.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.23.0.1": {
                    "url": "http://172.23.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.24.0.1": {
                    "url": "http://172.24.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.25.0.1": {
                    "url": "http://172.25.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.26.0.1": {
                    "url": "http://172.26.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.27.0.1": {
                    "url": "http://172.27.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.28.0.1": {
                    "url": "http://172.28.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.29.0.1": {
                    "url": "http://172.29.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.30.0.1": {
                    "url": "http://172.30.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-172.31.0.1": {
                    "url": "http://172.31.0.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.16.1": {
                    "url": "http://192.168.16.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.3.22": {
                    "url": "http://192.168.3.22:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.3.254": {
                    "url": "http://192.168.3.254:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.32.1": {
                    "url": "http://192.168.32.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.48.1": {
                    "url": "http://192.168.48.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.64.1": {
                    "url": "http://192.168.64.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                },
                "application/local-192.168.80.1": {
                    "url": "http://192.168.80.1:21603/?device_space=&plugin_app_id=INNER_API&plugin_app_token=Ua2QbE1FmyRJStFRUrl3s97bZeL5dKL_ygbNvzNAfgVVUePj069guptAxczr63-r",
                    "token": "",
                    "expire": "",
                    "type": "lan"
                }
            }
        }
        """
        response = self.__request(
            method="GET",
            url="https://api-pan.xunlei.com/drive/v1/apps/INNER_API?" + parse.urlencode({
                "space": device.get("params").get("target")
            })
        )
        return response.get("link")

    def __invoke_innerapi_with_url(self, device: dict, url: str, params: dict):
        inner_api = parse.urlparse(self._get_innerapi(device))
        inner_query = parse.parse_qs(inner_api.query)
        inner_query.update(**params)
        response = self.__request(
            method="GET",
            url=f"{inner_api.scheme}://{inner_api.netloc}{inner_api.path}{url}",
            params=inner_query
        )
        return response

    # @cached(maxsize=1000, ttl=3600)
    def get_directories(self, device_name: str):
        """
        {
            "kind": "drive#fileList",
            "next_page_token": "",
            "files": [
                {
                    "kind": "drive#folder",
                    "id": "b6a0ac45cc125bae2191888b547ad053",
                    "parent_id": "",
                    "name": "downloads",
                    "user_id": "625200512",
                    "size": "438",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T13:33:51.377+08:00",
                    "modified_time": "2025-05-18T13:36:12.883+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/downloads/",
                        "RealPath": "/downloads/",
                        "TaskID": "",
                        "category_id": "DownloadPath",
                        "category_name": "默认下载目录",
                        "client_version": "3.21.0",
                        "default": "true",
                        "is_write": "true",
                        "limit": "1908995522560",
                        "platform": "synology",
                        "source": "other",
                        "usage": "1855187542016",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                },
                {
                    "kind": "drive#folder",
                    "id": "defc12968dc16ed26e204acdf33ae30b",
                    "parent_id": "",
                    "name": "data",
                    "user_id": "625200512",
                    "size": "2402",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T15:19:51.798+08:00",
                    "modified_time": "2025-04-20T11:57:23.439+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/data/",
                        "RealPath": "/data/",
                        "TaskID": "",
                        "category_id": "DiskMountPath",
                        "category_name": "全部磁盘目录",
                        "client_version": "3.21.0",
                        "default": "false",
                        "is_write": "true",
                        "limit": "54609838080",
                        "platform": "synology",
                        "source": "other",
                        "usage": "17249857536",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                },
                {
                    "kind": "drive#folder",
                    "id": "0bae81c51c1978c3e31e5983f52142b0",
                    "parent_id": "",
                    "name": "bin",
                    "user_id": "625200512",
                    "size": "3716",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T15:19:51.844+08:00",
                    "modified_time": "2024-08-30T19:15:29.000+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/usr/bin/",
                        "RealPath": "/usr/bin/",
                        "TaskID": "",
                        "category_id": "DiskMountPath",
                        "category_name": "全部磁盘目录",
                        "client_version": "3.21.0",
                        "default": "false",
                        "is_write": "true",
                        "limit": "54609838080",
                        "platform": "synology",
                        "source": "other",
                        "usage": "17249857536",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                },
                {
                    "kind": "drive#folder",
                    "id": "ba47f67076a7fa86021fcabbcb1e26d7",
                    "parent_id": "",
                    "name": "lib",
                    "user_id": "625200512",
                    "size": "174",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T15:19:51.872+08:00",
                    "modified_time": "2024-05-30T10:06:56.000+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/usr/lib/",
                        "RealPath": "/usr/lib/",
                        "TaskID": "",
                        "category_id": "DiskMountPath",
                        "category_name": "全部磁盘目录",
                        "client_version": "3.21.0",
                        "default": "false",
                        "is_write": "true",
                        "limit": "54609838080",
                        "platform": "synology",
                        "source": "other",
                        "usage": "17249857536",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                },
                {
                    "kind": "drive#folder",
                    "id": "ec9864597d2d70d3c09b91e610e9af0a",
                    "parent_id": "",
                    "name": "run",
                    "user_id": "625200512",
                    "size": "40",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T15:19:51.897+08:00",
                    "modified_time": "2024-05-30T10:07:10.000+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/run/",
                        "RealPath": "/run/",
                        "TaskID": "",
                        "category_id": "DiskMountPath",
                        "category_name": "全部磁盘目录",
                        "client_version": "3.21.0",
                        "default": "false",
                        "is_write": "true",
                        "limit": "54609838080",
                        "platform": "synology",
                        "source": "other",
                        "usage": "17249857536",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                },
                {
                    "kind": "drive#folder",
                    "id": "686be3887129f92dcc3159aa66c5b97f",
                    "parent_id": "",
                    "name": "tmp",
                    "user_id": "625200512",
                    "size": "0",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T15:19:51.923+08:00",
                    "modified_time": "2024-05-30T10:07:10.000+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/tmp/",
                        "RealPath": "/tmp/",
                        "TaskID": "",
                        "category_id": "DiskMountPath",
                        "category_name": "全部磁盘目录",
                        "client_version": "3.21.0",
                        "default": "false",
                        "is_write": "true",
                        "limit": "54609838080",
                        "platform": "synology",
                        "source": "other",
                        "usage": "17249857536",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                },
                {
                    "kind": "drive#folder",
                    "id": "ee1755c0bfbb3dad41770ed64a79e01d",
                    "parent_id": "",
                    "name": "lib64",
                    "user_id": "625200512",
                    "size": "40",
                    "revision": "0",
                    "file_extension": "",
                    "mime_type": "folder",
                    "starred": false,
                    "web_content_link": "",
                    "created_time": "2025-05-18T15:19:51.957+08:00",
                    "modified_time": "2024-05-30T10:06:56.000+08:00",
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/36de21fd06b9ebdd5092b68652b6fc6118e23c2b",
                    "thumbnail_link": "",
                    "md5_checksum": "",
                    "hash": "",
                    "links": {},
                    "phase": "PHASE_TYPE_COMPLETE",
                    "audit": null,
                    "medias": [],
                    "trashed": false,
                    "delete_time": "",
                    "original_url": "",
                    "params": {
                        "AliasPath": "/usr/lib64/",
                        "RealPath": "/usr/lib64/",
                        "TaskID": "",
                        "category_id": "DiskMountPath",
                        "category_name": "全部磁盘目录",
                        "client_version": "3.21.0",
                        "default": "false",
                        "is_write": "true",
                        "limit": "54609838080",
                        "platform": "synology",
                        "source": "other",
                        "usage": "17249857536",
                        "vfs_id": "20250518133351889",
                        "vfs_type": "os"
                    },
                    "original_file_index": 0,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783",
                    "apps": [],
                    "writable": false,
                    "folder_type": "",
                    "collection": null,
                    "sort_name": "",
                    "user_modified_time": "",
                    "spell_name": [],
                    "file_category": "OTHER",
                    "tags": [],
                    "reference_events": []
                }
            ],
            "version": "",
            "version_outdated": false,
            "sync_time": ""
        }
        """
        device = self.get_device(device_name)
        response = self.__invoke_innerapi_with_url(
            device=device,
            url="drive/v1/files",
            params={
                "device_space": "",
                "space": device.get("params").get("target"),
                "parent_id": "",
                "limit": "20",
                "with_audit": "true",
                "filters": {
                    "trashed": {"eq": "false"},
                    "phase": {"eq": "PHASE_TYPE_COMPLETE"},
                    "kind": {"eq": "drive#folder"}
                },
                "page_token": "",
                "with": "withCategoryDiskMountPath",
                "with": "withCategoryHistoryDownloadPath",
                "order": "TYPE_DESC",
            })
        return response.get("files")

    def get_directory(self, device_name: str, path: str):
        directories = self.get_directories(device_name)
        filter_directories = list(filter(lambda x: x.get('params').get('RealPath') == path + "\\", directories))
        if len(filter_directories) == 0:
            raise Exception(f"无法找到远程设备名称为{device_name}的\"{path}\"目录，请检查配置")
        return filter_directories[0]

    def list_tasks(self, device_name: str):
        """
        {
            "tasks": [
                {
                    "kind": "drive#task",
                    "id": "VOQXtrcQLxRWj-tMVQV6GpirA1",
                    "name": "【高清剧集网发布 www.PTHDTV.com】爱，死亡和机器人.第四季[全10集][简繁英字幕].2025.Repack.1080p.NF.WEB-DL.x264.DDP5.1.Atmos-DeePTV",
                    "type": "user#download-url",
                    "user_id": "625200512",
                    "statuses": [],
                    "status_size": 0,
                    "params": {
                        "checked_size": "130818150",
                        "client_id": "Yd0uSVGrNJhCC2oE",
                        "ehc": "6",
                        "gcid_empty_count": "0",
                        "hc": "6",
                        "info_hash": "3393fdb952109e24c66c8b39e393f23dfd550084",
                        "ip": "58.48.105.9",
                        "package_name": "WEB",
                        "parent_folder_id": "b6a0ac45cc125bae2191888b547ad053",
                        "platform": "web",
                        "real_path": "/downloads/【高清剧集网发布 www.PTHDTV.com】爱，死亡和机器人.第四季[全10集][简繁英字幕].2025.Repack.1080p.NF.WEB-DL.x264.DDP5.1.Atmos-DeePTV",
                        "sleep": "timer:1s<1s<1m0s",
                        "spec": "{\"phase\":\"running\"}",
                        "speed": "12473137", ## 当前下载速速
                        "speed_limit": "-1",
                        "speedup": "{\"p2p\":\"started\",\"vip\":\"close\",\"super\":\"close\",\"trace_id\":\"WsDBU5M5\"}",
                        "speedup_count": "5",
                        "speedup_failed_count": "0",
                        "speedup_refresh": "1",
                        "speedup_speed": "0",
                        "speedup_status": "1",
                        "status": "{\"phase\":\"running\"}",
                        "sub_file_index": "0-11",
                        "super_speedup_isjoined": "false",
                        "target": "device_id#94082a79c0fee7fef301911ae6769783",
                        "team_isjoined": "false",
                        "total_file_count": "12",
                        "url": "magnet:?xt=urn:btih:3393fdb952109e24c66c8b39e393f23dfd550084"
                    },
                    "file_id": "29ac8903b130cd2a7b68a93dfe832cb9",
                    "file_name": "【高清剧集网发布 www.PTHDTV.com】爱，死亡和机器人.第四季[全10集][简繁英字幕].2025.Repack.1080p.NF.WEB-DL.x264.DDP5.1.Atmos-DeePTV",
                    "file_size": "4474046567",
                    "message": "已添加",
                    "created_time": "2025-05-18T18:19:03.067+08:00",
                    "updated_time": "2025-05-18T18:20:07.534+08:00",
                    "third_task_id": "",
                    "phase": "PHASE_TYPE_RUNNING",
                    "progress": 15,
                    "icon_link": "https://backstage-img-ssl.a.88cdn.com/65d616355857aef8af40b89f187a8cf2770cb0ce",
                    "callback": "",
                    "reference_resource": null,
                    "space": "device_id#94082a79c0fee7fef301911ae6769783"
                }
            ],
            "next_page_token": "",
            "expires_in": 5,
            "expires_in_ms": 5000
        }
        """
        device = self.get_device(device_name)
        response = self.__request(
            method="GET",
            url="https://api-pan.xunlei.com/drive/v1/tasks",
            params={
                "space": device.get("params").get("target"),
                "page_token": "",
                "filters": json.dumps({
                    "phase": {"in": "PHASE_TYPE_PENDING,PHASE_TYPE_RUNNING,PHASE_TYPE_ERROR,PHASE_TYPE_PAUSED"},
                    "type": {"in": "user#download,user#download-url"}
                }),
                "limit": "200",
            }
        )
        return response.get("tasks")

    def task_info(self, device_name: str, task_id: str):
        device = self.get_device(device_name)
        response = self.__request(
            method="GET",
            url="https://api-pan.xunlei.com/drive/v1/tasks/" + task_id,
            params={
                "space": device.get("params").get("target"),
            }
        )
        return response

    def create_task(self, torrent_url: str, device_name: str, directory_path: str):
        device = self.get_device(device_name)
        directory = self.get_directory(device_name, directory_path)
        # 获取种子的文件列表
        list_response = self.__request(
            method="POST",
            url="https://api-pan.xunlei.com/drive/v1/resource/list",
            json={"urls": torrent_url, "page_size": 2000}
        )
        resources = list_response.get("list").get("resources")[0]
        # 开始下载
        response = self.__request(
            method="POST",
            url="https://api-pan.xunlei.com/drive/v1/task",
            json={
                "file_name": resources.get("name"),
                "file_size": resources.get("file_size"),
                "space": device.get("params").get("target"),
                "type": "user#download-url",
                "params": {
                    "parent_folder_id": directory.get("id"),
                    "target": device.get("params").get("target"),
                    "platform": "web",
                    "total_file_count": str(resources.get("file_count")),
                    "url": torrent_url,
                    "sub_file_index": "0-" + str(int(resources.get("file_count")) - 1)
                }
            }
        )
        return response['task']['id']

    def remove_task(self, device_name: str, task_id: str):
        device = self.get_device(device_name)
        response = self.__request(
            method="PATCH",
            url="https://api-pan.xunlei.com/drive/v1/task",
            json={
                "space": device.get("params").get("target"),
                "type": "user#download-url",
                "id": task_id,
                "set_params": {"spec": "{\"phase\":\"delete\"}"}
            }
        )
        return response.status_code == 200

    def start_task(self, device_name: str, task_id: str):
        device = self.get_device(device_name)
        response = self.__request(
            method="PATCH",
            url="https://api-pan.xunlei.com/drive/v1/task",
            json={
                "space": device.get("params").get("target"),
                "type": "user#download-url",
                "id": task_id,
                "set_params": {"spec": "{\"phase\":\"running\"}"}
            }
        )
        return response.status_code == 200

    def pause_task(self, device_name: str, task_id: str):
        device = self.get_device(device_name)
        response = self.__request(
            method="PATCH",
            url="https://api-pan.xunlei.com/drive/v1/task",
            json={
                "space": device.get("params").get("target"),
                "type": "user#download-url",
                "id": task_id,
                "set_params": {"spec": "{\"phase\":\"pause\"}"}
            }
        )
        return response.status_code == 200

    def statistics(self, device_name: str):
        device = self.get_device(device_name)
        response = self.__invoke_innerapi_with_url(
            device=device,
            url="device/v1/try_speed/get_info",
            params={

            },
        )
        return response.get("statistic")


if __name__ == '__main__':
    api = RemoteClient(
        username="18627176816",
        password="ly2000281.",
    )
    api.auth_log_in()
    device_info = api.get_device("群晖-SynologyUat")
    print(device_info)
    directory_info = api.get_directory("群晖-SynologyUat", "/downloads/")
    print(directory_info)
    did = api.create_task("magnet:?xt=urn:btih:3393fdb952109e24c66c8b39e393f23dfd550084", "群晖-SynologyUat",
                          "/downloads/")
    print(did)
    api.pause_task("群晖-SynologyUat", did)
    api.start_task("群晖-SynologyUat", did)
    api.remove_task("群晖-SynologyUat", did)
    tasks = api.list_tasks("群晖-SynologyUat")
    print(tasks)
