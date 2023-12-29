import time
from typing import Optional, Union, Tuple, List

from types import SimpleNamespace
from app.core.config import settings
from app.log import logger
from app.utils.singleton import Singleton
from app.utils.string import StringUtils
from app.modules.nasxunlei.xunlei import Xunlei


class NasXunlei(metaclass=Singleton):
    _host: str = None
    _port: int = None
    _username: str = None
    _password: str = None

    nxc: Xunlei = None

    def __init__(self, host: str = None, port: int = None, username: str = None, password: str = None):
        """
        若不设置参数，则创建配置文件设置的下载器
        """
        if host and port:
            self._host, self._port = host, port
        else:
            self._host, self._port = StringUtils.get_domain_address(address=settings.NASXUNLEI_HOST, prefix=True)
        self._username = username if username else settings.NASXUNLEI_USER
        self._password = password if password else settings.NASXUNLEI_PASSWORD
        if self._host and self._port:
            self.nxc = self.__login_nasxunlei()

    def is_inactive(self) -> bool:
        """
        判断是否需要重连
        """
        if not self._host or not self._port:
            return False
        return True if not self.nxc else False

    def reconnect(self):
        """
        重连
        """
        self.nxc = self.__login_nasxunlei()

    def __login_nasxunlei(self) -> Optional[Xunlei]:
        """
        连接 NAS 迅雷
        :return: NAS 迅雷对象
        """
        nxc = Xunlei(host=self._host, port=self._port, username=self._username, password=self._password)
        try:
            nxc.check_server_now()
            return nxc
        except Exception as err:
            logger.error(f"nasxunlei 连接出错：{str(err)}")
            return None

    def get_torrents(self, ids: Union[str, list] = None,
                     status: Union[str, list] = None,
                     tags: Union[str, list] = None) -> Tuple[List[SimpleNamespace], bool]:
        """
        获取种子列表
        return: 种子列表, 是否发生异常
        """
        if not self.nxc:
            return [], True
        try:
            all_tasks = self.nxc.get_torrents(ids=ids, status=status)
            if not all_tasks:
                return [], False
            else:
                return all_tasks, False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               tags: Union[str, list] = None) -> Optional[List[SimpleNamespace]]:
        """
        获取已完成的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.nxc:
            return [], True
        try:
            all_tasks = self.nxc.get_complete_torrents(ids=ids, status=status)
            if not all_tasks:
                return [], False
            else:
                return all_tasks, False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 tags: Union[str, list] = None) -> Optional[List[SimpleNamespace]]:
        """
        获取正在下载的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.nxc:
            return [], True
        try:
            all_tasks = self.nxc.get_downloading_torrents(ids=ids)
            if not all_tasks:
                return None, True
            else:
                return all_tasks, False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def remove_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        pass

    def set_torrents_tag(self, ids: Union[str, list], tags: list):
        pass

    def torrents_set_force_start(self, ids: Union[str, list]):
        pass

    def get_torrent_id_by_tag(self, tags: Union[str, list],
                              status: Union[str, list] = None) -> Optional[str]:
        """
        通过标签多次尝试获取刚添加的种子ID，并移除标签
        """
        return None

    def add_torrent(self,
                    content: Union[str, bytes],
                    is_paused: bool = False,
                    download_dir: str = None,
                    tag: Union[str, list] = None,
                    category: str = None,
                    cookie=None,
                    **kwargs
                    ) -> bool:
        """
        添加种子
        :param content: 种子urls或文件内容
        :param is_paused: 添加后暂停
        :param tag: 标签
        :param category: 种子分类
        :param download_dir: 下载路径
        :param cookie: 站点Cookie用于辅助下载种子
        :return: bool
        """
        if not self.nxc or not content:
            return False

        # 下载内容
        if isinstance(content, str):
            urls = content
            torrent_files = None
        else:
            urls = None
            torrent_files = content

        # 保存目录
        if download_dir:
            save_path = download_dir
        else:
            save_path = None

        # 分类自动管理
        if category and settings.QB_CATEGORY:
            is_auto = True
        else:
            is_auto = False
            category = None

        try:
            # 添加下载
            nxc_ret = self.nxc.add_torrent(content=content, download_dir=download_dir)
            return True
        except Exception as err:
            logger.error(f"添加种子出错：{str(err)}")
            return False

    def start_torrents(self, ids: Union[str, list]) -> bool:
        """
        启动种子
        """
        if not self.nxc:
            return False
        try:
            self.nxc.start_torrents(ids=ids)
            return True
        except Exception as err:
            logger.error(f"启动种子出错：{str(err)}")
            return False

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        暂停种子
        """
        if not self.nxc:
            return False
        try:
            self.nxc.stop_torrents(ids=ids)
            return True
        except Exception as err:
            logger.error(f"暂停种子出错：{str(err)}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        删除种子
        """
        if not self.nxc:
            return False
        if not ids:
            return False
        try:
            self.nxc.delete_torrents(ids=ids, delete_file=delete_file)
            return True
        except Exception as err:
            logger.error(f"删除种子出错：{str(err)}")
            return False

    def get_files(self, tid: str) -> Optional[SimpleNamespace]:
        """
        获取种子文件清单
        """
        if not self.nxc:
            return None
        try:
            return self.nxc.get_files(tid)
        except Exception as err:
            logger.error(f"获取种子文件列表出错：{str(err)}")
            return None

    def set_files(self, **kwargs) -> bool:
        pass

    def transfer_info(self) -> Optional[any]:
        """
        获取传输信息
        """
        if not self.nxc:
            return None
        try:
            torrents = self.get_downloading_torrents()
            DispTorrents = []
            for torrent in torrents:
                if torrent.status == NasXunlei_Status.PHASE_TYPE_RUNNING:
                    state = "Downloading"
                    speed = "%s%sB/s" % (chr(8595), StringUtils.str_filesize(torrent.speed))
                else:
                    state = "Stoped"
                    speed = "已暂停"
                DispTorrents.append({
                    'id': torrent.id,
                    'name': torrent.name,
                    'speed': speed,
                    'state': state,
                    'progress': torrent.progress
                })
            return DispTorrents
        except Exception as err:
            logger.error(f"获取传输信息出错：{str(err)}")
            return None

    def set_speed_limit(self, download_limit: float = None, upload_limit: float = None) -> bool:
        """
        设置速度限制
        :param download_limit: 下载速度限制，单位KB/s
        :param upload_limit: 上传速度限制，单位kB/s
        """
        if not self.nxc:
            return False
        download_limit = download_limit * 1024
        try:
            self.nxc.set_speed_limit(download_limit)
            return True
        except Exception as err:
            logger.error(f"设置速度限制出错：{str(err)}")
            return False

    def recheck_torrents(self, ids: Union[str, list]) -> bool:
        """
        重新校验种子
        """
        pass

    def update_tracker(self, hash_string: str, tracker_list: list) -> bool:
        """
        添加tracker
        """
        pass
