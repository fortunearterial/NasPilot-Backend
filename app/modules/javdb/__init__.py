import re
from pathlib import Path
from typing import List, Optional, Tuple, Union

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.javdb.apiv1 import JavDBApi
from app.modules.javdb.javdb_cache import JavDBCache
from app.modules.javdb.scraper import JavDBScraper
from app.schemas.types import MediaType
from app.utils.common import retry
from app.utils.system import SystemUtils


class JavDBModule(_ModuleBase):
    javdbapi: JavDBApi = None
    scraper: JavDBScraper = None
    cache: JavDBCache = None

    def init_module(self) -> None:
        self.javdbapi = JavDBApi()
        self.scraper = JavDBScraper()
        self.cache = JavDBCache()

    @staticmethod
    def get_name() -> str:
        return "JavDB"

    def stop(self):
        self.cache.save()

    def test(self) -> Tuple[bool, str]:
        """
        测试模块连接性
        """
        return True, ""

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    def recognize_media(self, meta: MetaBase = None,
                        mtype: MediaType = None,
                        javdbid: str = None,
                        **kwargs) -> Optional[MediaInfo]:
        """
        识别媒体信息
        :param meta:     识别的元数据
        :param mtype:    识别的媒体类型，与javdbid配套
        :param javdbid: JavDB ID
        :return: 识别的媒体信息，包括剧集信息
        """
        if settings.RECOGNIZE_SOURCE and not "javdb" in settings.RECOGNIZE_SOURCE:
            return None
        # 若type不为jav则跳过
        if meta:
            if meta.type != MediaType.JAV and mtype != MediaType.JAV and not javdbid:
                return None
        else:
            if mtype != MediaType.JAV and not javdbid:
                return None

        if not meta:
            cache_info = {}
        else:
            if mtype:
                meta.type = mtype
            cache_info = self.cache.get(meta)
        if not cache_info:
            # 缓存没有或者强制不使用缓存
            if javdbid:
                # 直接查询详情
                info = self.javdb_info(javdbid=javdbid, mtype=mtype or meta.type)
            elif meta:
                logger.info(f"正在识别 {meta.name} ...")
                # 匹配JavDB信息
                match_info = self.match(name=meta.name,
                                        mtype=mtype or meta.type,
                                        year=meta.year)
                if match_info:
                    # 匹配到JavDB信息
                    info = self.javdb_info(
                        javdbid=match_info.get("steam_appid"),
                        mtype=mtype or meta.type
                    )
                else:
                    logger.info(f"{meta.name if meta else javdbid} 未匹配到JavDB媒体信息")
                    return None
            else:
                logger.error("识别媒体信息时未提供元数据或JavDB ID")
                return None
            # 保存到缓存
            if meta:
                self.cache.update(meta, info)
        else:
            # 使用缓存信息
            if cache_info.get("title"):
                logger.info(f"{meta.name} 使用JavDB识别缓存：{cache_info.get('title')}")
                info = self.javdb_info(mtype=cache_info.get("type"),
                                        javdbid=cache_info.get("id"))
            else:
                logger.info(f"{meta.name} 使用JavDB识别缓存：无法识别")
                info = None

        if info:
            # 赋值JavDB信息并返回
            mediainfo = MediaInfo(javdb_info=info)
            if meta:
                logger.info(f"{meta.name} JavDB识别结果：{mediainfo.type.value} "
                            f"{mediainfo.title_year} "
                            f"{mediainfo.javdb_id}")
            else:
                logger.info(f"{javdbid} JavDB识别结果：{mediainfo.type.value} "
                            f"{mediainfo.title_year}")
            return mediainfo
        else:
            logger.info(f"{meta.name if meta else javdbid} 未匹配到JavDB媒体信息")

        return None

    def javdb_info(self, javdbid: str, mtype: MediaType = None) -> Optional[dict]:
        """
        获取JavDB信息
        :param javdbid: JavDB ID
        :param mtype:    媒体类型
        :return: JavDB信息
        """
        """
        {

        }
        """

        def __javdb_jav():
            """
            获取JavDB jav信息
            """
            return self.javdbapi.jav_detail(javdbid)
            
        if not javdbid:
            return None
        logger.info(f"开始获取JavDB信息：{javdbid} ...")
        if mtype == MediaType.JAV:
            return __javdb_jav()
        
        return None

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        搜索媒体信息
        :param meta:  识别的元数据
        :reutrn: 媒体信息
        """
        # 未启用JavDB搜索时返回None
        if settings.SEARCH_SOURCE and "javdb" not in settings.SEARCH_SOURCE:
            return None

        if not meta.org_string:
            return []
        result = self.javdbapi.search(meta.org_string)
        if not result:
            return []
        # 返回数据
        ret_medias = []
        for item_obj in result:
            ret_medias.append(MediaInfo(javdb_info=item_obj))

        return ret_medias

    @retry(Exception, 5, 3, 3, logger=logger)
    def match(self, name: str, 
                         mtype: MediaType = None, year: str = None) -> dict:
        """
        搜索和匹配JavDB信息
        :param name:  名称
        :param mtype:  类型
        :param year:  年份
        """
        # 搜索
        logger.info(f"开始使用名称 {name} 匹配JavDB信息 ...")
        result = self.javdbapi.search(f"{name}".strip())
        if not result:
            logger.warn(f"未找到 {name} 的JavDB信息")
            return {}
        for item in result:
            title = item.get("name")
            if not title:
                continue
            meta = MetaInfo(title)
            if meta.name == name:
                logger.info(f"{name} 匹配到JavDB信息：{item.get('steam_appid')} {item.get('title')}")
                return item
        return {}

    def scrape_metadata(self, path: Path, mediainfo: MediaInfo, transfer_type: str) -> None:
        """
        刮削元数据
        :param path: 媒体文件路径
        :param mediainfo:  识别的媒体信息
        :param transfer_type: 传输类型
        :return: 成功或失败
        """
        if not settings.SCRAP_SOURCE.__contains__("javdb"):
            return None
        
        # Jav目录
        logger.info(f"开始刮削游戏目录：{path} ...")
        meta = MetaInfo(path.stem)
        if not meta.name:
            return
        
        javdbinfo = self.javdb_info(javdbid=mediainfo.javdb_id,
                                            mtype=mediainfo.type)
        if not javinfo:
            logger(f"未获取到 {mediainfo.javdb_id} 的JavDB媒体信息，无法刮削！")
            return
        # JavDB媒体信息
        mediainfo = MediaInfo(javdb_info=javdbinfo)
        # 补充图片
        self.obtain_images(mediainfo)
        # 刮削路径
        scrape_path = path / path.name
        self.scraper.gen_scraper_files(meta=meta,
                                        mediainfo=mediainfo,
                                        file_path=scrape_path,
                                        transfer_type=transfer_type)

        logger.info(f"{path} 刮削完成")

    def scheduler_job(self) -> None:
        """
        定时任务，每10分钟调用一次
        """
        self.cache.save()

    def obtain_images(self, mediainfo: MediaInfo) -> Optional[MediaInfo]:
        """
        补充抓取媒体信息图片
        :param mediainfo:  识别的媒体信息
        :return: 更新后的媒体信息
        """
        if not "javdb" in settings.RECOGNIZE_SOURCE:
            return None
        if not mediainfo.javdb_id:
            return None
        if mediainfo.backdrop_path:
            # 没有图片缺失
            return mediainfo
        raise
        # return mediainfo

    def clear_cache(self):
        """
        清除缓存
        """
        logger.info("开始清除JavDB缓存 ...")
        self.javdbapi.clear_cache()
        self.cache.clear()
        logger.info("JavDB缓存清除完成")
