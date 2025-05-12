from typing import List, Optional

from app import schemas
from app.db.userconfig_oper import UserConfigOper
from app.schemas.types import UserConfigKey


class StorageHelper:
    """
    存储帮助类
    """

    def __init__(self):
        self.userconfig = UserConfigOper()

    def get_storagies(self, user_id: int) -> List[schemas.StorageConf]:
        """
        获取所有存储设置
        """
        storage_confs: List[dict] = self.userconfig.get(user_id, UserConfigKey.Storages)
        if not storage_confs:
            return []
        return [schemas.StorageConf(**s) for s in storage_confs]

    def get_storage(self, user_id: int, storage: str) -> Optional[schemas.StorageConf]:
        """
        获取指定存储配置
        """
        storagies = self.get_storagies(user_id)
        for s in storagies:
            if s.type == storage:
                return s
        return None

    def set_storage(self, user_id: int, storage: str, conf: dict):
        """
        设置存储配置
        """
        storagies = self.get_storagies(user_id)
        if not storagies:
            storagies = [
                schemas.StorageConf(
                    type=storage,
                    config=conf
                )
            ]
        else:
            for s in storagies:
                if s.type == storage:
                    s.config = conf
                    break
        self.userconfig.set(user_id, UserConfigKey.Storages, [s.dict() for s in storagies])

    def add_storage(self, user_id: int, storage: str, name: str, conf: dict):
        """
        添加存储配置
        """
        storagies = self.get_storagies(user_id)
        if not storagies:
            storagies = [
                schemas.StorageConf(
                    type=storage,
                    name=name,
                    config=conf
                )
            ]
        else:
            storagies.append(schemas.StorageConf(
                type=storage,
                name=name,
                config=conf
            ))
        self.userconfig.set(user_id, UserConfigKey.Storages, [s.dict() for s in storagies])

    def reset_storage(self, user_id: int, storage: str):
        """
        重置存储配置
        """
        storagies = self.get_storagies(user_id)
        for s in storagies:
            if s.type == storage:
                s.config = {}
                break
        self.userconfig.set(user_id, UserConfigKey.Storages, [s.dict() for s in storagies])
