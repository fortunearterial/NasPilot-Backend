import shutil
from pathlib import Path
from typing import Set, Tuple, Optional, Union, List

from aria2p.downloads import File
from torrentool.torrent import Torrent

from app import schemas
from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.aria2.aria2 import Aria2
from app.schemas import TransferTorrent, DownloadingTorrent
from app.schemas.types import TorrentStatus
from app.utils.string import StringUtils
from app.utils.system import SystemUtils


class Aria2Module(_ModuleBase):
    aria2: Aria2 = None

    def init_module(self) -> None:
        self.aria2 = Aria2()

    @staticmethod
    def get_name() -> str:
        return "Aria2"

    def stop(self):
        pass

    def test(self) -> Tuple[bool, str]:
        """
        测试模块连接性
        """
        return True, ""

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "DOWNLOADER", "aria2"

    def scheduler_job(self) -> None:
        """
        定时任务，每10分钟调用一次
        """
        # 定时重连
        if self.aria2.is_inactive():
            self.aria2.reconnect()

    def download(self, content: Union[Path, str], download_dir: Path, cookie: str,
                 episodes: Set[int] = None, category: str = None) -> Optional[Tuple[Optional[str], str]]:
        """
        根据种子文件，选择并添加下载任务
        :param content:  种子文件地址或者磁力链接
        :param download_dir:  下载目录
        :param cookie:  cookie
        :param episodes:  需要下载的集数
        :param category:  分类
        :return: 种子Hash，错误信息
        """

        def __get_torrent_info() -> Tuple[str, int]:
            """
            获取种子名称
            """
            try:
                if isinstance(content, Path):
                    torrentinfo = Torrent.from_file(content)
                else:
                    torrentinfo = Torrent.from_string(content)
                return torrentinfo.name, torrentinfo.total_size
            except Exception as e:
                logger.error(f"获取种子名称失败：{e}")
                return "", 0

        if not content:
            return
        if isinstance(content, Path) and not content.exists():
            return None, f"种子文件不存在：{content}"

        # 添加任务
        gids = self.aria2.add_torrent(
            content=content.read_bytes() if isinstance(content, Path) else content,
            download_dir=str(download_dir),
        )
        
        return gids[0], "添加下载成功"

    def list_torrents(self, status: TorrentStatus = None,
                      hashs: Union[list, str] = None) -> Optional[List[Union[TransferTorrent, DownloadingTorrent]]]:
        """
        获取下载器种子列表
        :param status:  种子状态
        :param hashs:  种子Hash
        :return: 下载器中符合状态的种子列表
        """
        ret_torrents = []
        if hashs:
            # 按Hash获取
            torrents, _ = self.aria2.get_torrents(ids=hashs)
            for torrent in torrents or []:
                content_path = torrent.root_files_paths[0]
                if content_path:
                    torrent_path = content_path
                else:
                    torrent_path = settings.SAVE_PATH / torrent.name
                ret_torrents.append(TransferTorrent(
                    title=torrent.name,
                    path=torrent_path,
                    hash=torrent.gid
                ))
        elif status == TorrentStatus.TRANSFER:
            # 获取已完成且未整理的
            torrents = self.aria2.get_completed_torrents()
            for torrent in torrents or []:
                # 内容路径
                content_path = torrent.root_files_paths[0]
                if content_path:
                    torrent_path = content_path
                else:
                    torrent_path = settings.SAVE_PATH / torrent.name
                ret_torrents.append(TransferTorrent(
                    title=torrent.name,
                    path=torrent_path,
                    hash=torrent.gid
                ))
        elif status == TorrentStatus.DOWNLOADING:
            # 获取正在下载的任务
            torrents = self.aria2.get_downloading_torrents()
            for torrent in torrents or []:
                meta = MetaInfo(torrent.name)
                ret_torrents.append(DownloadingTorrent(
                    hash=torrent.gid,
                    title=torrent.name,
                    name=meta.name,
                    year=meta.year,
                    season_episode=meta.season_episode,
                    progress=torrent.progress * 100,
                    size=torrent.piece_length,
                    state="paused" if torrent.get('state') == "waiting" else "downloading",
                    dlspeed=StringUtils.str_filesize(torrent.download_speed),
                    upspeed=StringUtils.str_filesize(torrent.upload_speed),
                    left_time=StringUtils.str_secends(torrent.eta.seconds)
                ))
        else:
            return None
        return ret_torrents

    def transfer_completed(self, hashs: Union[str, list],
                           path: Path = None) -> None:
        """
        转移完成后的处理
        :param hashs:  种子Hash
        :param path:  源目录
        """
        self.aria2.set_torrents_tag(ids=hashs, tags=['已整理'])
        # 移动模式删除种子
        if settings.TRANSFER_TYPE == "move":
            if self.remove_torrents(hashs):
                logger.info(f"移动模式删除种子成功：{hashs} ")
            # 删除残留文件
            if path and path.exists():
                files = SystemUtils.list_files(path, settings.RMT_MEDIAEXT)
                if not files:
                    logger.warn(f"删除残留文件夹：{path}")
                    shutil.rmtree(path, ignore_errors=True)

    def remove_torrents(self, hashs: Union[str, list]) -> bool:
        """
        删除下载器种子
        :param hashs:  种子Hash
        :return: bool
        """
        return self.aria2.delete_torrents(delete_file=True, ids=hashs)

    def start_torrents(self, hashs: Union[list, str]) -> bool:
        """
        开始下载
        :param hashs:  种子Hash
        :return: bool
        """
        return self.aria2.start_torrents(ids=hashs)

    def stop_torrents(self, hashs: Union[list, str]) -> bool:
        """
        停止下载
        :param hashs:  种子Hash
        :return: bool
        """
        return self.aria2.stop_torrents(ids=hashs)

    def torrent_files(self, tid: str) -> Optional[File]:
        """
        获取种子文件列表
        """
        return self.aria2.get_files(tid=tid)

    def downloader_info(self) -> schemas.DownloaderInfo:
        """
        下载器信息
        """
        # 调用Aria2 API查询实时信息
        info = self.aria2.transfer_info()
        if not info:
            return schemas.DownloaderInfo()
        return schemas.DownloaderInfo(
            download_speed=info.download_speed,
            upload_speed=info.upload_speed
        )
