import os
from typing import Optional

from app.helper.service import UserServiceBaseHelper
from app.schemas import DownloaderConf, ServiceInfo
from app.schemas.types import UserConfigKey, ModuleType


class DownloaderHelper(UserServiceBaseHelper[DownloaderConf]):
    """
    下载器帮助类
    """
    __sites: list[str] = ['【高清剧集网发布 www.PTHDTV.com】',
                          '【高清剧集网发布 www.DDHDTV.com】',
                          '【高清剧集网发布 www.BPHDTV.com】']
    __files: list[str] = ['【更多电视剧集下载请访问 www.PTHDTV.com】【更多剧集打包下载请访问 www.PTHDTV.com】',
                          '【更多高清剧集下载请访问 www.PTHDTV.com】【更多剧集打包下载请访问 www.PTHDTV.com】',
                          '【更多电视剧集下载请访问 www.DDHDTV.com】【更多剧集打包下载请访问 www.DDHDTV.com】',
                          '【更多高清剧集下载请访问 www.DDHDTV.com】【更多剧集打包下载请访问 www.DDHDTV.com】',
                          '【更多电视剧集下载请访问 www.BPHDTV.com】【更多剧集打包下载请访问 www.BPHDTV.com】',
                          '【更多高清剧集下载请访问 www.BPHDTV.com】【更多剧集打包下载请访问 www.BPHDTV.com】']

    def __init__(self):
        super().__init__(
            config_key=UserConfigKey.Downloaders,
            conf_type=DownloaderConf,
            module_type=ModuleType.Downloader
        )

    def is_downloader(
            self,
            service_type: Optional[str] = None,
            service: Optional[ServiceInfo] = None,
            user_id: Optional[int] = None,
            name: Optional[str] = None,
    ) -> bool:
        """
        通用的下载器类型判断方法
        :param service_type: 下载器的类型名称（如 'qbittorrent', 'transmission'）
        :param service: 要判断的服务信息
        :param name: 服务的名称
        :return: 如果服务类型或实例为指定类型，返回 True；否则返回 False
        """
        # 如果未提供 service 则通过 name 获取服务
        service = service or self.get_service(user_id=user_id, name=name)

        # 判断服务类型是否为指定类型
        return bool(service and service.type == service_type)

    def remove_torrent_name_sites(self, torrent_name: str) -> str:
        """
        移除种子名称中的下载站点信息
        """
        for site in self.__sites:
            torrent_name = torrent_name.replace(site, "")
        return torrent_name

    def is_ignore_torrent_file(self, file_path: str) -> bool:
        """
        忽略的种子文件
        """
        file_name, file_extension = os.path.splitext(file_path)
        return file_name in self.__files