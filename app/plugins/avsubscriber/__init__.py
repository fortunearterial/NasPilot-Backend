import os
import re
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bencode import bdecode, bencode
from lxml import etree

from app.core.config import settings
from app.helper.browser import PlaywrightHelper
from app.log import logger
from app.chain.subscribe import SubscribeChain
from app.schemas.types import MediaType
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.string import StringUtils
from app.utils.http import RequestUtils
from app.helper.cookiecloud import CookieCloudHelper
from app.db.site_oper import SiteOper


class AVSubscriber(_PluginBase):
    # 插件名称
    plugin_name = "女优订阅"
    # 插件描述
    plugin_desc = "自动订阅女优新番。"
    # 插件图标
    plugin_icon = "Whisparr_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "fortunearterial"
    # 作者主页
    author_url = "https://github.com/fortunearterial"
    # 插件配置项ID前缀
    plugin_config_prefix = "avsubscriber_"
    # 加载顺序
    plugin_order = 100
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _cookiecloud = None
    _siteoper = None
    __cookies = None
    _scheduler = None
    # 系统属性
    _enabled = False
    _onlyonce = False
    _notify = False
    _cron = None
    _username = None
    # 订阅属性
    _quality = None
    _resolution = None
    _effect = None
    _sites = None
    _save_path = None
    _best_version = True
    # 插件属性
    _avs = None
    # 常量
    # 质量选择框数据
    _qualityOptions = [
        {
            "title": '全部',
            "value": '',
        },
        {
            "title": '蓝光原盘',
            "value": 'Blu-?Ray.+VC-?1|Blu-?Ray.+AVC|UHD.+blu-?ray.+HEVC|MiniBD',
        },
        {
            "title": 'Remux',
            "value": 'Remux',
        },
        {
            "title": 'BluRay',
            "value": 'Blu-?Ray',
        },
        {
            "title": 'UHD',
            "value": 'UHD|UltraHD',
        },
        {
            "title": 'WEB-DL',
            "value": 'WEB-?DL|WEB-?RIP',
        },
        {
            "title": 'HDTV',
            "value": 'HDTV',
        },
        {
            "title": 'H265',
            "value": '[Hx].?265|HEVC',
        },
        {
            "title": 'H264',
            "value": '[Hx].?264|AVC',
        },
    ]
    # 分辨率选择框数据
    _resolutionOptions = [
        {
            "title": '全部',
            "value": '',
        },
        {
            "title": '4k',
            "value": '4K|2160p|x2160',
        },
        {
            "title": '1080p',
            "value": '1080[pi]|x1080',
        },
        {
            "title": '720p',
            "value": '720[pi]|x720',
        },
    ]
    # 特效选择框数据
    _effectOptions = [
        {
            "title": '全部',
            "value": '',
        },
        {
            "title": '杜比视界',
            "value": 'Dolby[\\s.]+Vision|DOVI|[\\s.]+DV[\\s.]+',
        },
        {
            "title": '杜比全景声',
            "value": 'Dolby[\\s.]*\\+?Atmos|Atmos',
        },
        {
            "title": 'HDR',
            "value": '[\\s.]+HDR[\\s.]+|HDR10|HDR10\\+',
        },
        {
            "title": 'SDR',
            "value": '[\\s.]+SDR[\\s.]+',
        },
    ]
    # 退出事件
    _event = Event()

    def init_plugin(self, config: dict = None):
        self._cookiecloud = CookieCloudHelper()
        self._siteoper = SiteOper()
        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._cron = config.get("cron")
            self._username = config.get("username")
            self._quality = config.get("quality")
            self._resolution = config.get("resolution")
            self._effect = config.get("effect")
            self._sites = config.get("sites")
            self._save_path = config.get("save_path")
            self._best_version = config.get("best_version")
            self._avs = config.get("avs")

        # 停止现有任务
        self.stop_service()

        # 启动定时任务 & 立即运行一次
        if self.get_state() or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                logger.info(f"女优订阅服务启动，周期：{self._cron}")
                try:
                    self._scheduler.add_job(self.subscribe,
                                            CronTrigger.from_crontab(self._cron))
                except Exception as e:
                    logger.error(f"女优订阅服务启动失败：{str(e)}")
                    self.systemmessage.put(f"女优订阅服务启动失败：{str(e)}")
                    return
            if self._onlyonce:
                logger.info(f"女优订阅服务启动，立即运行一次")
                self._scheduler.add_job(self.subscribe, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(
                                            seconds=3))
                # 关闭一次性开关
                self._onlyonce = False
                self.update_config({
                    "enabled": self._enabled,
                    "onlyonce": self._onlyonce,
                    "notify": self._notify,
                    "cron": self._cron,
                    "username": self._username,
                    "quality": self._quality,
                    "resolution": self._resolution,
                    "effect": self._effect,
                    "sites": self._sites,
                    "save_path": self._save_path,
                    "best_version": self._best_version,
                    "avs": self._avs,
                })
            if self._scheduler.get_jobs():
                # 启动服务
                self._scheduler.print_jobs()
            self._scheduler.start()

    def get_state(self):
        return True if self._enabled and self._cron and self._avs else False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/get_av_list", 
            "endpoint": self.api_get_av_list, 
            "methods": ["GET"],
            "summary": "获取女优列表",
            "description": "获取女优列表",
        }]

    def api_get_av_list(self) -> Any:
        return [dict({
            "tab": avinfo.split("：")[0],
            "title": avinfo.split("：")[0],
            "icon": ""
        }) for avinfo in self._avs.split("\n")]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '发送通知',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '执行周期',
                                            'placeholder': '0 0 * * *'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'username',
                                            'label': '订阅用户',
                                            'placeholder': '默认为`jav_user`'
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': False,
                                            'model': 'quality',
                                            'label': '质量',
                                            'hint': '订阅资源质量',
                                            'persistent-hint': True,
                                            'items': self._qualityOptions
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': False,
                                            'model': 'resolution',
                                            'label': '分辨率',
                                            'hint': '订阅资源分辨率',
                                            'persistent-hint': True,
                                            'items': self._resolutionOptions
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': False,
                                            'model': 'effect',
                                            'label': '特效',
                                            'hint': '订阅资源特效',
                                            'persistent-hint': True,
                                            'items': self._effectOptions
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'sites',
                                            'label': '订阅站点',
                                            'hint': '订阅的站点范围，不选使用系统设置',
                                            'persistent-hint': True,
                                            'items': [dict({
                                                "title": s.name,
                                                "value": s.id,
                                            }) for s in filter(lambda s: MediaType.JAV.name in s.types, self._siteoper.list_active())]
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 8
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'save_path',
                                            'label': '保存路径',
                                            'hint': '指定该订阅的下载保存路径，留空自动使用设定的下载目录',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'best_version',
                                            'label': '洗版',
                                            'hint': '根据洗版优先级进行洗版订阅',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'avs',
                                            'label': '女优列表',
                                            'hint': '格式为：\r\n女优名称：https://javdb.com/actors/女优地址',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    } 
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": False,
            "cron": None,
            "username": "jav_user",
            "quality": None,
            "resolution": None,
            "effect": None,
            "sites": None,
            "save_path": None,
            "best_version": True,
            "avs": None
        }

    def get_page(self) -> List[dict]:
        pass

    def subscribe(self):
        """
        开始订阅女优
        """
        logger.info("开始订阅女优任务 ...")
        cookies, msg = self._cookiecloud.download()
        self.__cookies = cookies
        _avs_new = []

        for avinfo in self._avs.split("\n"):
            name, url = avinfo.split("：")
            logger.info(f"开始订阅女优 {name} ...")

            # 初始化
            if "__init__" in url:
                for i in range(1, 999):
                    page_url = url.replace("__init__", str(i))
                    page_source = self.__get_html(page_url)
                    if "暫無內容" in page_source:
                        break
                    self.__subscribe(page_source, name)
                # 完成初始化后，仅订阅最新
                _avs_new.append(f"{name}：{url.replace('__init__', '1')}")
            else:
                page_source = self.__get_html(url)
                self.__subscribe(page_source, name)
                _avs_new.append(f"{name}：{url}")
        
        self._avs = "\n".join(_avs_new)
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "notify": self._notify,
            "cron": self._cron,
            "username": self._username,
            "quality": self._quality,
            "resolution": self._resolution,
            "effect": self._effect,
            "sites": self._sites,
            "save_path": self._save_path,
            "best_version": self._best_version,
            "avs": self._avs,
        })

    def __subscribe(self, page_source, av_name):
        html = etree.HTML(page_source)
        if html is not None:
            videos = html.xpath("//div[contains(@class, 'movie-list')]/div[@class='item']/a")
            for video in videos:
                javdbid = video.xpath("./@href")[0][3:]
                title = video.xpath("./@title")[0].strip()
                javid = video.xpath("./div[@class='video-title']/strong/text()")[0].strip()
                release_date = video.xpath("./div[@class='meta']/text()")[0].strip()

                sid, message = SubscribeChain().add(mtype=MediaType.JAV,
                                        title=f"{javid} {title}",
                                        javdbid=javdbid,
                                        year=release_date[:4],
                                        username=self.plugin_author,
                                        save_path=f"{settings.DOWNLOAD_JAV_PATH}/{av_name}/{javid}",
                                        keyword=javid, # 关键字
                                        best_version=1, # 洗版
                                        exist_ok=True)
                # 随机休眠30-60秒
                sleep_time = random.randint(30, 60)
                logger.info(f'订阅搜索随机休眠 {sleep_time} 秒 ...')
                time.sleep(sleep_time)

    def __get_html(self, url, params = None) -> str:
        logger.info(f"开始请求：{url}")
        # # 浏览器仿真
        # return PlaywrightHelper().get_page_source(
        #     url=url,
        #     cookies="list_mode=h; theme=auto; locale=zh; cf_clearance=8B.d8O8kLkWi7kv0vYe1PoTnQRZZsZas_rROR39GWMk-1702991486-0-1-25e5af4b.54bc817f.72e4f0ab-0.2.1702991486; over18=1; _ym_uid=1702991513933832321; _ym_d=1702991513; _ym_isad=2; _jdb_session=XijY3N9BFKAKbQt1IfioNMWcudqU8%2BBzyNm%2B4piF5VNvoJxP7s2oclmuODHbotSHTefrRd%2FstN%2BcMEN3v1zcONL3ZmpFYp8KyP9vKo%2FnotItRO5YpNSg6hI%2FbhYUZWrDl8L%2FwK7f3qcpHEnXOZerVOnS1%2FlxgvNEeM4D%2F%2FaU%2Fg5TYIzy%2BbmQriLUTEuaZQ1QNkhhueDFnQP6m0nPnk%2F8VREiYo6q2Emo%2Boz3KgJkssHI46mksGXtQjbm0bQJH6jLueyzj%2Bu9uFXZw9tO4aDrkJ7bHR3TfwRQ9UXoGRvh%2FLi%2FpzuBxEqGhpX6--OhWo6mihE9l9%2BQ7W--HaR9Uz1kQiWFLvDiGAJr%2BA%3D%3D",
        #     ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76",
        #     proxies=settings.PROXY_SERVER,
        #     headless=True,
        #     timeout=120
        # )
        ret = RequestUtils(
                    ua=settings.USER_AGENT,
                    cookies=self.__cookies.get('javdb.com'),
                    timeout=30,
                    proxies=settings.PROXY
                ).get_res(url, allow_redirects=True)
        if ret is not None:
            return ret.text

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            print(str(e))