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
    _scheduler = None
    # 开关
    _enabled = False
    _cron = None
    _onlyonce = False
    _notify = False
    _autostart = False
    # 属性
    _avs = None
    # 退出事件
    _event = Event()

    def init_plugin(self, config: dict = None):
        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._autostart = config.get("autostart")
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
                    "cron": self._cron,
                    "autostart": self._autostart,
                    "avs": self._avs,
                })
            if self._scheduler.get_jobs():
                # 启动服务
                self._scheduler.print_jobs()
            self._scheduler.start()

    def get_state(self):
        return True if self._enabled \
                       and self._cron \
                       and self._avs else False

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
        return list(set([{
            "tab": avinfo.split("：")[0],
            "title": avinfo.split("：")[0],
            "icon": ""
        } for avinfo in self._avs.split("\n")]))

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
                                    'md': 6
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
                                    'md': 6
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
                                            'placeholder': '0 0 0 ? *'
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
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
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
            "notify": False,
            "onlyonce": False,
            "cron": "",
            "avs": "",
            "autostart": True
        }

    def get_page(self) -> List[dict]:
        pass

    def subscribe(self):
        """
        开始订阅女优
        """
        logger.info("开始订阅女优任务 ...")
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
            "cron": self._cron,
            "autostart": self._autostart,
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
                                        best_version=1, # 洗板
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
                    cookies="list_mode=h; theme=auto; locale=zh; cf_clearance=8B.d8O8kLkWi7kv0vYe1PoTnQRZZsZas_rROR39GWMk-1702991486-0-1-25e5af4b.54bc817f.72e4f0ab-0.2.1702991486; over18=1; _ym_uid=1702991513933832321; _ym_d=1702991513; _ym_isad=2; _jdb_session=XijY3N9BFKAKbQt1IfioNMWcudqU8%2BBzyNm%2B4piF5VNvoJxP7s2oclmuODHbotSHTefrRd%2FstN%2BcMEN3v1zcONL3ZmpFYp8KyP9vKo%2FnotItRO5YpNSg6hI%2FbhYUZWrDl8L%2FwK7f3qcpHEnXOZerVOnS1%2FlxgvNEeM4D%2F%2FaU%2Fg5TYIzy%2BbmQriLUTEuaZQ1QNkhhueDFnQP6m0nPnk%2F8VREiYo6q2Emo%2Boz3KgJkssHI46mksGXtQjbm0bQJH6jLueyzj%2Bu9uFXZw9tO4aDrkJ7bHR3TfwRQ9UXoGRvh%2FLi%2FpzuBxEqGhpX6--OhWo6mihE9l9%2BQ7W--HaR9Uz1kQiWFLvDiGAJr%2BA%3D%3D",
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