import time
from pathlib import Path
from typing import Union
from xml.dom import minidom

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.log import logger
from app.schemas.types import MediaType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils
from app.utils.system import SystemUtils


class SteamScraper:

    def gen_scraper_files(self, meta: MetaBase, mediainfo: MediaInfo,
                          file_path: Path, transfer_type: str):
        """
        生成刮削文件
        :param meta: 元数据
        :param mediainfo: 媒体信息
        :param file_path: 文件路径或者目录路径
        :param transfer_type: 转输类型
        """

        # TODO: 接入Playnite
        pass
        