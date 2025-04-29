from typing import Any, Union, Dict, Optional

from app.db import DbOper
from app.schemas.types import UserConfigKey
from app.utils.singleton import Singleton
from app.db.models.userjob import UserJob


class UserJobOper(DbOper, metaclass=Singleton):

    def publish(self, userid: str, name: str, *args, **kwargs):
        """
        发布用户任务
        """
        # 写入数据库
        conf = UserJob(request_userid=userid, job_name=name, job_args={
            "args": args,
            "kwargs": kwargs,
        })
        conf.create(self._db)

    def consume(self, userid: str) -> Any:
        """
        消费用户任务
        """
        return UserJob.get_by_user(self._db, userid)

    def __del__(self):
        if self._db:
            self._db.close()

