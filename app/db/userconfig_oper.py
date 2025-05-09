import itertools
from typing import Any, Union, Dict, Optional

from app.db import DbOper
from app.db.models.userconfig import UserConfig
from app.schemas.types import UserConfigKey
from app.utils.singleton import Singleton


class UserConfigOper(DbOper, metaclass=Singleton):
    # 配置缓存
    __USERCONF: Dict[int, Dict[str, Any]] = {}

    def __init__(self):
        """
        加载配置到内存
        """
        super().__init__()
        for item in UserConfig.list(self._db):
            self.__set_config_cache(user_id=item.user_id, key=item.key, value=item.value)

    def set(self, user_id: int, key: Union[str, UserConfigKey], value: Any):
        """
        设置用户配置
        """
        if isinstance(key, UserConfigKey):
            key = key.value
        # 更新内存
        self.__set_config_cache(user_id=user_id, key=key, value=value)
        # 写入数据库
        conf = UserConfig.get_by_key(db=self._db, user_id=user_id, key=key)
        if conf:
            if value:
                conf.update(self._db, {"value": value})
            else:
                conf.delete(self._db, conf.id)
        else:
            conf = UserConfig(user_id=user_id, key=key, value=value)
            conf.create(self._db)

    def get(self, user_id: Optional[int] = None, key: Union[str, UserConfigKey] = None) -> Any:
        """
        获取用户配置
        """
        if isinstance(key, UserConfigKey):
            key = key.value
        if not user_id:
            if not key:
                return self.__USERCONF
            else:
                values = [kv.get(key) for uid, kv in self.__USERCONF.items() if kv.get(key) is not None]
                flattened = list(itertools.chain(*[v if isinstance(v, list) else [v] for v in values]))
                return flattened
        if not key:
            return self.__get_config_caches(user_id=user_id)
        return self.__get_config_cache(user_id=user_id, key=key)

    def __del__(self):
        if self._db:
            self._db.close()

    def __set_config_cache(self, user_id: int, key: str, value: Any):
        """
        设置配置缓存
        """
        if not user_id or not key:
            return
        cache = self.__USERCONF
        if not cache:
            cache = {}
        user_cache = cache.get(user_id)
        if not user_cache:
            user_cache = {}
            cache[user_id] = user_cache
        user_cache[key] = value
        self.__USERCONF = cache

    def __get_config_caches(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取配置缓存
        """
        if not user_id or not self.__USERCONF:
            return None
        return self.__USERCONF.get(user_id)

    def __get_config_cache(self, user_id: int, key: str) -> Any:
        """
        获取配置缓存
        """
        if not user_id or not key or not self.__USERCONF:
            return None
        user_cache = self.__get_config_caches(user_id)
        if not user_cache:
            return None
        return user_cache.get(key)
