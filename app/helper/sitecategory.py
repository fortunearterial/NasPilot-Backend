import shutil
from pathlib import Path

import ruamel.yaml

from app.core.config import settings
from app.log import logger
from app.utils.singleton import Singleton
from app.schemas.types import MediaType
from app.utils.string import StringUtils


class SiteCategoryHelper(metaclass=Singleton):
    """
    Site分类
    """
    _categorys = {}
    
    def __init__(self):
        self._category_path: Path = settings.CONFIG_PATH / "sitecategory.yaml"
        self.init()

    def init(self):
        """
        初始化
        """
        try:
            if not self._category_path.exists():
                shutil.copy(settings.INNER_CONFIG_PATH / "sitecategory.yaml", self._category_path)
            with open(self._category_path, mode='r', encoding='utf-8') as f:
                try:
                    yaml = ruamel.yaml.YAML()
                    self._categorys = yaml.load(f)
                except Exception as e:
                    logger.warn(f"Site分类策略配置文件格式出现严重错误！请检查：{str(e)}")
                    self._categorys = {}
        except Exception as err:
            logger.warn(f"Site分类策略配置文件加载出错：{str(err)}")

        logger.info(f"已加载Site分类策略 sitecategory.yaml")

    def get_media_type(self, domain: str, category: str) -> MediaType:
        """
        获得分类的媒体类型
        :param domain: 域名
        :param category: item.category
        :return: 媒体类型
        """
        _, netloc = StringUtils.get_url_netloc(domain)
        return self.get_category(self._categorys.get(netloc), category)

    @staticmethod
    def get_category(categorys: dict, category: dict) -> MediaType:
        if not category:
            return MediaType.UNKNOWN
        if not categorys:
            return MediaType.UNKNOWN

        _movie_categorys = categorys.get('movie') or []
        _tv_categorys = categorys.get('tv') or []
        _anime_categorys = categorys.get('anime') or []
        _game_categorys = categorys.get('game') or []
        _music_categorys = categorys.get('music') or []
        _jav_categorys = categorys.get('jav') or []
        _comic_categorys = categorys.get('comic') or []

        if category in _movie_categorys:
            return MediaType.MOVIE
        if category in _tv_categorys:
            return MediaType.TV
        if category in _anime_categorys:
            return MediaType.ANIME
        if category in _game_categorys:
            return MediaType.GAME
        if category in _music_categorys:
            return MediaType.MUSIC
        if category in _jav_categorys:
            return MediaType.JAV
        if category in _comic_categorys:
            return MediaType.COMIC
        
        return MediaType.UNKNOWN
