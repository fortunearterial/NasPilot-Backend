import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bencode import bdecode, bencode

from app.core.config import settings
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.string import StringUtils


class TorrentFileTransfer(_PluginBase):
    # 插件名称
    plugin_name = "自动转移做种任务的文件"
    # 插件描述
    plugin_desc = "自动转移做种任务的文件从下载目录到存档目录。"
    # 插件图标
    plugin_icon = "Qbittorrent_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "fortunearterial"
    # 作者主页
    author_url = "https://github.com/fortunearterial"
    # 插件配置项ID前缀
    plugin_config_prefix = "torrentfiletransfer_"
    # 加载顺序
    plugin_order = 101
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _scheduler = None
    qb = None
    tr = None
    torrent = None
    # 开关
    _enabled = False
    _cron = None
    _onlyonce = False
    _downloader = None
    _frompath = None
    _topath = None
    _notify = False
    _nolabels = None
    _includelabels = None
    _nopaths = None
    _deletesource = False
    _autostart = False
    # 退出事件
    _event = Event()
    # 任务标签
    _torrent_tags = ["已整理", "转移做种"]

    def init_plugin(self, config: dict = None):
        self.torrent = TorrentHelper()
        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._nolabels = config.get("nolabels")
            self._includelabels = config.get("includelabels")
            self._frompath = config.get("frompath")
            self._topath = config.get("topath")
            self._downloader = config.get("downloader")
            self._deletesource = config.get("deletesource")
            self._nopaths = config.get("nopaths")
            self._autostart = config.get("autostart")

        # 停止现有任务
        self.stop_service()

        # 启动定时任务 & 立即运行一次
        if self.get_state() or self._onlyonce:
            self.qb = Qbittorrent()
            self.tr = Transmission()
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                logger.info(f"转移做种文件服务启动，周期：{self._cron}")
                try:
                    self._scheduler.add_job(self.transfer,
                                            CronTrigger.from_crontab(self._cron))
                except Exception as e:
                    logger.error(f"转移做种文件服务启动失败：{str(e)}")
                    self.systemmessage.put(f"转移做种文件服务启动失败：{str(e)}")
                    return
            if self._onlyonce:
                logger.info(f"转移做种文件服务启动，立即运行一次")
                self._scheduler.add_job(self.transfer, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(
                                            seconds=3))
                # 关闭一次性开关
                self._onlyonce = False
                self.update_config({
                    "enabled": self._enabled,
                    "onlyonce": self._onlyonce,
                    "cron": self._cron,
                    "notify": self._notify,
                    "nolabels": self._nolabels,
                    "includelabels": self._includelabels,
                    "frompath": self._frompath,
                    "topath": self._topath,
                    "downloader": self._downloader,
                    "deletesource": self._deletesource,
                    "nopaths": self._nopaths,
                    "autostart": self._autostart
                })
            if self._scheduler.get_jobs():
                # 启动服务
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self):
        return True if self._enabled \
                       and self._cron \
                       and self._downloader else False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

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
                                            'model': 'nolabels',
                                            'label': '不转移种子标签',
                                        }
                                    }
                                ]
                            }, {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'includelabels',
                                            'label': '转移种子标签',
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'downloader',
                                            'label': '下载器',
                                            'items': [
                                                {'title': 'Qbittorrent', 'value': 'qbittorrent'},
                                                {'title': 'Transmission', 'value': 'transmission'}
                                            ]
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'frompath',
                                            'label': '源数据文件根路径',
                                            'placeholder': '根路径，留空不进行路径转换'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'topath',
                                            'label': '目的数据文件根路径',
                                            'placeholder': '根路径，留空不进行路径转换'
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
                                            'model': 'deletesource',
                                            'label': '删除源种子',
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
            "nolabels": "",
            "includelabels": "",
            "frompath": "",
            "topath": "",
            "downloader": "",
            "todownloader": "",
            "deletesource": False,
            "nopaths": "",
            "autostart": True
        }

    def get_page(self) -> List[dict]:
        pass

    def __get_downloader(self, dtype: str):
        """
        根据类型返回下载器实例
        """
        if dtype == "qbittorrent":
            return self.qb
        elif dtype == "transmission":
            return self.tr
        else:
            return None

    def transfer(self):
        """
        开始转移做种
        """
        logger.info("开始转移做种任务 ...")

        # 下载器
        downloader = self._downloader

        # 获取下载器中已完成的种子
        downloader_obj = self.__get_downloader(downloader)
        torrents = downloader_obj.get_completed_torrents()
        if torrents:
            logger.info(f"下载器 {downloader} 已完成种子数：{len(torrents)}")
        else:
            logger.info(f"下载器 {downloader} 没有已完成种子")
            return

        # 过滤种子，记录保存目录
        trans_torrents = []
        for torrent in torrents:
            if self._event.is_set():
                logger.info(f"转移服务停止")
                return

            # 获取种子hash
            hash_str = self.__get_hash(torrent, downloader)
            # 获取保存路径
            save_path = self.__get_save_path(torrent, downloader)

            if self._nopaths and save_path:
                # 过滤不需要转移的路径
                nopath_skip = False
                for nopath in self._nopaths.split('\n'):
                    if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                        logger.info(f"种子 {hash_str} 保存路径 {save_path} 不需要转移，跳过 ...")
                        nopath_skip = True
                        break
                if nopath_skip:
                    continue

            # 获取种子标签
            torrent_labels = self.__get_label(torrent, downloader)
            # 排除含有不转移的标签
            if torrent_labels and self._nolabels:
                is_skip = False
                for label in self._nolabels.split(','):
                    if label in torrent_labels:
                        logger.info(f"种子 {hash_str} 含有不转移标签 {label}，跳过 ...")
                        is_skip = True
                        break
                if is_skip:
                    continue
            # 排除不含有转移标签的种子
            if torrent_labels and self._includelabels:
                is_skip = False
                for label in self._includelabels.split(','):
                    if label not in torrent_labels:
                        logger.info(f"种子 {hash_str} 不含有转移标签 {label}，跳过 ...")
                        is_skip = True
                        break
                if is_skip:
                    continue

            # 添加转移数据
            trans_torrents.append({
                "hash": hash_str,
                "save_path": save_path,
                "torrent": torrent
            })

        # 开始转移任务
        if trans_torrents:
            logger.info(f"需要转移的种子数：{len(trans_torrents)}")
            # 记数
            total = len(trans_torrents)
            # 总成功数
            success = 0
            # 总失败数
            fail = 0
            # 跳过数
            skip = 0

            for torrent_item in trans_torrents:
                # 转换保存路径
                save_path = torrent_item.get('save_path')
                sourcepath = self.__convert_save_path(save_path,
                                                        self._frompath,
                                                        "/volume2/downloads/qBittorrent/私人")
                destpath = self.__convert_save_path(save_path,
                                                        self._frompath,
                                                        self._topath)

                if not destpath:
                    logger.debug(f"转换保存路径失败：{torrent_item.get('save_path')}")
                    # 失败计数
                    fail += 1
                    continue

                logger.info(f"mkdir -p \"{destpath}\"")
                logger.info(f"mv \"{sourcepath}\" \"{Path(destpath).parent}\"")


                # 删除源种子，不能删除文件！
                if self._deletesource:
                    logger.debug(f"删除下载器任务：{torrent_item.get('hash')} ...")
                    downloader_obj.delete_torrents(delete_file=False, ids=[torrent_item.get('hash')])

                # 成功计数
                success += 1
                # 插入转种记录
                history_key = "%s-%s" % (self._downloader, torrent_item.get('hash'))
                self.save_data(key=history_key,
                                value={
                                    "delete_source": self._deletesource,
                                })
            # 发送通知
            if self._notify:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【转移做种文件任务执行完成】",
                    text=f"总数：{total}，成功：{success}，失败：{fail}，跳过：{skip}"
                )
        else:
            logger.info(f"没有需要转移的种子")
        logger.info("转移做种任务执行完成")

    @staticmethod
    def __get_hash(torrent: Any, dl_type: str):
        """
        获取种子hash
        """
        try:
            return torrent.get("hash") if dl_type == "qbittorrent" else torrent.hashString
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __get_label(torrent: Any, dl_type: str):
        """
        获取种子标签
        """
        try:
            return [str(tag).strip() for tag in torrent.get("tags").split(',')] \
                if dl_type == "qbittorrent" else torrent.labels or []
        except Exception as e:
            print(str(e))
            return []

    @staticmethod
    def __get_save_path(torrent: Any, dl_type: str):
        """
        获取种子保存路径
        """
        try:
            return torrent.get("save_path") if dl_type == "qbittorrent" else torrent.download_dir
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __convert_save_path(save_path: str, from_root: str, to_root: str):
        """
        转换保存路径
        """
        try:
            # 没有保存目录，以目的根目录为准
            if not save_path:
                return to_root
            # 没有设置根目录时返回save_path
            if not to_root or not from_root:
                return save_path
            # 统一目录格式
            save_path = os.path.normpath(save_path).replace("\\", "/")
            from_root = os.path.normpath(from_root).replace("\\", "/")
            to_root = os.path.normpath(to_root).replace("\\", "/")
            # 替换根目录
            if save_path.startswith(from_root):
                return save_path.replace(from_root, to_root, 1)
        except Exception as e:
            print(str(e))
        return None

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