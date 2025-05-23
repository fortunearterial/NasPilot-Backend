import json
import pickle
import time
import traceback
from typing import Optional, Union, Tuple, List, Any, Dict

from app.log import logger
from app.core.config import settings
from app.utils.string import StringUtils
from app.modules.thunder.apiv1 import RemoteClient, LoginFailed


class Thunder:
    _username: Optional[str] = None
    _password: Optional[str] = None
    _device_name: Optional[str] = None

    tdc: RemoteClient = None

    def __init__(self,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 device_name: Optional[str] = None,
                 **kwargs):
        """
        若不设置参数，则创建配置文件设置的下载器
        """
        self._username = username
        self._password = password
        self._device_name = device_name
        if self._username and self._password:
            self.tdc = self.__login_thunder()

    def is_inactive(self) -> bool:
        """
        判断是否需要重连
        """
        if not self._username or not self._password or not self._device_name:
            return False
        return True if not self.tdc else False

    def reconnect(self):
        """
        重连
        """
        self.tdc = self.__login_thunder()

    def __login_thunder(self) -> Optional[Any]:
        """
        连接thunder
        :return: thunder对象
        """
        try:
            # 登录
            tdc = RemoteClient(username=self._username,
                               password=self._password)
            try:
                tdc.auth_log_in()
            except LoginFailed as e:
                logger.error(f"thunder 登录失败：{str(e).strip() or '请检查用户名和密码是否正确'}")
                return None
            except Exception as e:
                stack_trace = "".join(traceback.format_exception(None, e, e.__traceback__))[:2000]
                logger.error(f"thunder 登录失败：{str(e)}\n{stack_trace}")
                return None
            return tdc
        except Exception as err:
            logger.error(f"thunder 连接出错：{str(err)}")
            return None

    def get_torrents(self, ids: Optional[Union[str, list]] = None,
                     status: Optional[str] = None,
                     tags: Optional[Union[str, list]] = None) -> Tuple[List[Any], bool]:
        """
        获取种子列表
        return: 种子列表, 是否发生异常
        """
        if not self.tdc:
            return [], True
        try:
            torrents = self.tdc.list_tasks(self._device_name)
            if tags:
                results = []
                if not isinstance(tags, list):
                    tags = [tags]
                for torrent in torrents:
                    torrent_tags = [str(tag).strip() for tag in torrent.get("tags").split(',')]
                    if set(tags).issubset(set(torrent_tags)):
                        results.append(torrent)
                return results, False
            return torrents or [], False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               tags: Union[str, list] = None) -> Optional[List[Any]]:
        """
        获取已完成的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.tdc:
            return None
        # completed会包含移动状态 改为获取seeding状态 包含活动上传, 正在做种, 及强制做种
        torrents, error = self.get_torrents(status="seeding", ids=ids, tags=tags)
        return None if error else torrents or []

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 tags: Union[str, list] = None) -> Optional[List[Any]]:
        """
        获取正在下载的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.tdc:
            return None
        torrents, error = self.get_torrents(ids=ids,
                                            status="downloading",
                                            tags=tags)
        return None if error else torrents or []

    def delete_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        """
        删除Tag
        :param ids: 种子Hash列表
        :param tag: 标签内容
        """
        if not self.tdc:
            return False
        try:
            # TODO: 迅雷不支持
            return True
        except Exception as err:
            logger.error(f"删除种子Tag出错：{str(err)}")
            return False

    def remove_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        """
        移除种子Tag
        :param ids: 种子Hash列表
        :param tag: 标签内容
        """
        if not self.tdc:
            return False
        try:
            # TODO: 迅雷不支持
            return True
        except Exception as err:
            logger.error(f"移除种子Tag出错：{str(err)}")
            return False

    def set_torrents_tag(self, ids: Union[str, list], tags: list):
        """
        设置种子状态为已整理，以及是否强制做种
        """
        if not self.tdc:
            return
        try:
            # TODO: 迅雷不支持
            pass
        except Exception as err:
            logger.error(f"设置种子Tag出错：{str(err)}")

    def is_force_resume(self) -> bool:
        """
        是否支持强制作种
        """
        return False

    def torrents_set_force_start(self, ids: Union[str, list]):
        """
        设置强制作种
        """
        if not self.tdc:
            return
        try:
            # TODO: 迅雷不支持
            pass
        except Exception as err:
            logger.error(f"设置强制作种出错：{str(err)}")

    def __get_last_add_torrentid_by_tag(self, tags: Union[str, list],
                                        status: Optional[str] = None) -> Optional[str]:
        """
        根据种子的下载链接获取下载中或暂停的钟子的ID
        :return: 种子ID
        """
        try:
            torrents, _ = self.get_torrents(status=status, tags=tags)
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return None
        if torrents:
            return torrents[0].get("hash")
        else:
            return None

    def get_torrent_id_by_tag(self, tags: Union[str, list],
                              status: Optional[str] = None) -> Optional[str]:
        """
        通过标签多次尝试获取刚添加的种子ID，并移除标签
        """
        torrent_id = None
        # QB添加下载后需要时间，重试10次每次等待3秒
        for i in range(1, 10):
            time.sleep(3)
            torrent_id = self.__get_last_add_torrentid_by_tag(tags=tags,
                                                              status=status)
            if torrent_id is None:
                continue
            else:
                self.delete_torrents_tag(torrent_id, tags)
                break
        return torrent_id

    def add_torrent(self,
                    content: Union[str, bytes],
                    is_paused: Optional[bool] = False,
                    download_dir: Optional[str] = None,
                    tag: Union[str, list] = None,
                    category: Optional[str] = None,
                    cookie: Optional[str] = None,
                    **kwargs
                    ) -> Tuple[bool, Optional[str]]:
        """
        添加种子
        :param content: 种子urls或文件内容
        :param is_paused: 添加后暂停
        :param tag: 标签
        :param category: 种子分类
        :param download_dir: 下载路径
        :param cookie: 站点Cookie用于辅助下载种子
        :param kwargs: 可选参数，如 ignore_category_check 以及 QB相关参数
        :return: bool
        """
        if not self.tdc or not content:
            return False

        # 下载内容
        if isinstance(content, str):
            # TODO：磁链转种子文件
            torrent_files = content
        else:
            torrent_files = settings.TEMP_PATH / (StringUtils.generate_random_str(8) + ".torrent")
            with open(torrent_files, 'wb') as f:
                f.write(content)

        # 保存目录
        if download_dir:
            save_path = download_dir
        else:
            save_path = None

        # 标签
        if tag:
            tags = tag
        else:
            tags = None

        try:
            # 添加下载
            ret = self.tdc.create_task(
                torrent_url=torrent_files,
                device_name=self._device_name,
                directory_path=save_path,
            )

            if ret:
                return True, ret
            return False, "添加种子失败"
        except Exception as err:
            logger.error(f"添加种子出错：{str(err)}")
            return False, str(err)

    def start_torrents(self, ids: Union[str, list]) -> bool:
        """
        启动种子
        """
        if not self.tdc:
            return False
        try:
            # TODO: 迅雷不支持
            return False
        except Exception as err:
            logger.error(f"启动种子出错：{str(err)}")
            return False

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        暂停种子
        """
        if not self.tdc:
            return False
        try:
            # TODO: 迅雷不支持
            return False
        except Exception as err:
            logger.error(f"暂停种子出错：{str(err)}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        删除种子
        """
        if not self.tdc:
            return False
        if not ids:
            return False
        try:
            # TODO: 迅雷不支持
            return False
        except Exception as err:
            logger.error(f"删除种子出错：{str(err)}")
            return False

    def get_files(self, tid: str) -> Optional[Any]:
        """
        获取种子文件清单
        """
        if not self.tdc:
            return None
        try:
            # TODO: 迅雷不支持 111
            return []
        except Exception as err:
            logger.error(f"获取种子文件列表出错：{str(err)}")
            return None

    def set_files(self, **kwargs) -> bool:
        """
        设置下载文件的状态，priority为0为不下载，priority为1为下载
        """
        if not self.tdc:
            return False
        if not kwargs.get("torrent_hash") or not kwargs.get("file_ids"):
            return False
        try:
            # TODO: 迅雷不支持
            return True
        except Exception as err:
            logger.error(f"设置种子文件状态出错：{str(err)}")
            return False

    def transfer_info(self) -> Optional[Any]:
        """
        获取传输信息
        """
        if not self.tdc:
            return None

        try:
            results = {
                "speed": 0,
                "downloaded_file_size": 0,
            }
            for task in self.tdc.list_tasks(self._device_name):
                results.update({
                    "speed": results.get("speed") + int(task.get("params").get("speed")),
                    "downloaded_file_size": results.get("downloaded_file_size") + int(task.get("file_size")) * task.get("progress") / 100.0,
                })
            return results
        except Exception as err:
            logger.error(f"获取传输信息出错：{str(err)}")
            return None

    def set_speed_limit(self, download_limit: float = None, upload_limit: float = None) -> bool:
        """
        设置速度限制
        :param download_limit: 下载速度限制，单位KB/s
        :param upload_limit: 上传速度限制，单位kB/s
        """
        if not self.tdc:
            return False
        download_limit = download_limit * 1024
        upload_limit = upload_limit * 1024
        # TODO: 迅雷不支持

    def get_speed_limit(self) -> Optional[Tuple[float, float]]:
        """
        获取QB速度
        :return: 返回download_limit 和upload_limit ，默认是0
        """
        if not self.tdc:
            return None

        download_limit = 0
        upload_limit = 0
        # TODO: 迅雷不支持

        return download_limit / 1024, upload_limit / 1024

    def recheck_torrents(self, ids: Union[str, list]) -> bool:
        """
        重新校验种子
        """
        if not self.tdc:
            return False
        try:
            # TODO: 迅雷不支持
            return True
        except Exception as err:
            logger.error(f"重新校验种子出错：{str(err)}")
            return False

    def update_tracker(self, hash_string: str, tracker_list: list) -> bool:
        """
        添加tracker
        """
        if not self.tdc:
            return False
        try:
            # TODO: 迅雷不支持
            return True
        except Exception as err:
            logger.error(f"修改tracker出错：{str(err)}")
            return False

    def get_content_layout(self) -> Optional[str]:
        """
        获取内容布局
        """
        if not self.tdc:
            return None
        # 获取种子内容布局: `Original: 原始, Subfolder: 创建子文件夹, NoSubfolder: 不创建子文件夹`
        return "Original"
