import pickle
import random
import time
from pathlib import Path
from threading import RLock
from typing import Optional

from app.core.config import settings
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.utils.singleton import Singleton
from app.schemas.types import MediaType

lock = RLock()

CACHE_EXPIRE_TIMESTAMP_STR = "cache_expire_timestamp"
EXPIRE_TIMESTAMP = settings.CACHE_CONF.get('meta')


class HtmlCache(metaclass=Singleton):
    """
    Html缓存数据
    """
    _meta_data: dict = {}
    # 缓存文件路径
    _meta_dir: Path = None
    _meta_path: Path = None
    # JavDB缓存过期
    _javdb_cache_expire: bool = False

    def __init__(self):
        self._meta_dir = settings.TEMP_PATH / "__html_cache__/javdb.com"
        self._meta_path = self._meta_dir / "__javdb_com__"
        if not self._meta_dir.exists():
            self._meta_dir.mkdir(parents=True, exist_ok=True)
        self._meta_data = self.__load(self._meta_path)

    def clear(self):
        """
        清空所有JavDB缓存
        """
        with lock:
            self._meta_data = {}

    @staticmethod
    def __get_key(url: str) -> str:
        """
        获取缓存KEY
        """
        return url.replace("/", "_")

    def get(self, url: str):
        """
        根据KEY值获取缓存值
        """
        key = self.__get_key(url)
        with lock:
            info: dict = self._meta_data.get(key)
            if info:
                expire = info.get(CACHE_EXPIRE_TIMESTAMP_STR)
                if not expire or int(time.time()) < expire:
                    info[CACHE_EXPIRE_TIMESTAMP_STR] = int(time.time()) + EXPIRE_TIMESTAMP
                    self._meta_data[key] = info
                elif expire and self._javdb_cache_expire:
                    self.delete(key)
                return self.__load_html(info.get("html_path"))
            return None

    def delete(self, key: str) -> dict:
        """
        删除缓存信息
        @param key: 缓存key
        @return: 被删除的缓存内容
        """
        with lock:
            return self._meta_data.pop(key, None)

    def delete_unknown(self) -> None:
        """
        清除未识别的缓存记录，以便重新搜索JavDB
        """
        for key in list(self._meta_data):
            if self._meta_data.get(key, {}).get("url") == "0":
                with lock:
                    self._meta_data.pop(key)

    @staticmethod
    def __load(path: Path) -> dict:
        """
        从文件中加载缓存
        """
        try:
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                return data
            return {}
        except Exception as e:
            print(str(e))
            return {}

    @staticmethod
    def __load_html(path: Path) -> str:
        """
        从文件中加载Html
        """
        try:
            if path.exists():
                with open(path, 'rb') as f:
                    data = f.read()
                return data.decode("utf-8")
            return None
        except Exception as e:
            print(str(e))
            return None

    def update(self, url: str, html: str) -> None:
        """
        新增或更新缓存条目
        """
        with lock:
            if html:
                html_path = self._meta_dir / url.replace("/", "_")
                with open(html_path, 'wb') as f:
                    f.write(html.encode("utf-8"))

                self._meta_data[self.__get_key(url)] = {
                        "url": url,
                        "html_path": html_path,
                        CACHE_EXPIRE_TIMESTAMP_STR: int(time.time()) + EXPIRE_TIMESTAMP
                    }
            elif html is not None:
                # None时不缓存，此时代表网络错误，允许重复请求
                self._meta_data[self.__get_key(url)] = {'url': "0"}
        self.save()

    def save(self, force: bool = False) -> None:
        """
        保存缓存数据到文件
        """

        meta_data = self.__load(self._meta_path)
        new_meta_data = {k: v for k, v in self._meta_data.items() if v.get("id")}

        if not force \
                and meta_data.keys() == new_meta_data.keys():
            return

        with open(self._meta_path, 'wb') as f:
            pickle.dump(new_meta_data, f, pickle.HIGHEST_PROTOCOL)


