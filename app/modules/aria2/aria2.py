import time
from typing import Optional, Union, Tuple, List

import aria2p
from aria2p import Client, API
from aria2p.downloads import Download, File
from aria2p.stats import Stats

from app.core.config import settings
from app.log import logger
from app.utils.singleton import Singleton
from app.utils.string import StringUtils


class Aria2(metaclass=Singleton):
    _host: str = None
    _port: str = None
    _secert: str = None

    ac: API = None

    def __init__(self, host: str = None, port: int = None, secert: str = None):
        """
        若不设置参数，则创建配置文件设置的下载器
        """
        if host and port:
            self._host, self._port = host, port
        else:
            self._host, self._port = StringUtils.get_domain_address(address=settings.ARIA2_RPC_HOST, prefix=True)
        self._secert = secert if secert else settings.ARIA2_SECERT
        if self._host and self._port:
            self.ac = self.__login_aria2()

    def is_inactive(self) -> bool:
        """
        判断是否需要重连
        """
        if not self._host or not self._port:
            return False
        return True if not self.ac else False

    def reconnect(self):
        """
        重连
        """
        self.ac = self.__login_aria2()

    def __login_aria2(self) -> Optional[Client]:
        """
        连接qbittorrent
        :return: qbittorrent对象
        """
        try:
            # 登录
            ac = API(
                Client(
                    host=self._host,
                    port=self._port,
                    secret=self._secert
                )
            )
            try:
                ac.get_downloads()
            except Exception() as e:
                logger.error(f"Aria2 登录失败：{str(e)}")
            return ac
        except Exception as err:
            logger.error(f"Aria2 连接出错：{str(err)}")
            return None

    def get_torrents(self, ids: Union[str, list] = None,
                     status: Union[str, list] = None,
                     **kwargs) -> Tuple[List[Download], bool]:
        """
        获取种子列表
        return: 种子列表, 是否发生异常
        """
        if not self.ac:
            return [], True
        try:
            torrents = self.ac.get_downloads(gids=ids)
            if status:
                results = []
                for torrent in torrents:
                    if torrent.status in status:
                        results.append(torrent)

                return results, False
            return torrents or [], False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               **kwargs) -> Optional[List[Download]]:
        """
        获取已完成的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.ac:
            return None
        torrents, error = self.get_torrents(ids=ids, status=["complete"])
        return None if error else torrents or []

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 **kwargs) -> Optional[List[Download]]:
        """
        获取正在下载的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.ac:
            return None
        torrents, error = self.get_torrents(ids=ids, status=["active"])
        return None if error else torrents or []

    def remove_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        pass

    def set_torrents_tag(self, ids: Union[str, list], tags: list):
        pass

    def torrents_set_force_start(self, ids: Union[str, list]):
        pass

    def get_torrent_id_by_tag(self, tags: Union[str, list],
                              status: Union[str, list] = None) -> Optional[str]:
        pass

    def add_torrent(self,
                    content: Union[str, bytes],
                    download_dir: str = None,
                    **kwargs
                    ) -> bool:
        """
        添加种子
        :param content: 种子urls或文件内容
        :param is_paused: 添加后暂停
        :param category: 种子分类
        :param download_dir: 下载路径
        :param cookie: 站点Cookie用于辅助下载种子
        :return: bool
        """
        if not self.ac or not content:
            return False

        # 保存目录
        if download_dir:
            save_path = download_dir
        else:
            save_path = None

        try:
            # 添加下载
            ac_rets = self.ac.add(uri=content, options={
                "dir": save_path
            })
            return [ac_ret.gid for ac_ret in ac_rets]
        except Exception as err:
            logger.error(f"添加种子出错：{str(err)}")
            return False

    def start_torrents(self, ids: Union[str, list]) -> bool:
        """
        启动种子
        """
        if not self.ac:
            return False
        try:
            self.ac.resume(downloads=[self.ac.get_download(id) for id in ids])
            return True
        except Exception as err:
            logger.error(f"启动种子出错：{str(err)}")
            return False

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        暂停种子
        """
        if not self.ac:
            return False
        try:
            self.ac.pause(downloads=[self.ac.get_download(id) for id in ids])
            return True
        except Exception as err:
            logger.error(f"暂停种子出错：{str(err)}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        删除种子
        """
        if not self.ac:
            return False
        if not ids:
            return False
        try:
            self.ac.remove(downloads=[self.ac.get_download(id) for id in ids], files=delete_file)
            return True
        except Exception as err:
            logger.error(f"删除种子出错：{str(err)}")
            return False

    def get_files(self, tid: str) -> Optional[File]:
        """
        获取种子文件清单
        """
        if not self.ac:
            return None
        try:
            return self.ac.get_download(gid=tid).files
        except Exception as err:
            logger.error(f"获取种子文件列表出错：{str(err)}")
            return None

    def set_files(self, **kwargs) -> bool:
        pass

    def transfer_info(self) -> Optional[Stats]:
        """
        获取传输信息
        """
        if not self.ac:
            return None
        try:
            return self.ac.get_stats()
        except Exception as err:
            logger.error(f"获取传输信息出错：{str(err)}")
            return None

    def set_speed_limit(self, download_limit: float = None, upload_limit: float = None) -> bool:
        """
        设置速度限制
        :param download_limit: 下载速度限制，单位KB/s
        :param upload_limit: 上传速度限制，单位kB/s
        """
        if not self.ac:
            return False
        pass

    def recheck_torrents(self, ids: Union[str, list]) -> bool:
        pass

    def update_tracker(self, hash_string: str, tracker_list: list) -> bool:
        pass
