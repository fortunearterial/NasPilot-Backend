import pickle
from typing import Any

from app.db import DbOper, db_id
from app.db.models.userjob import UserJob


class UserJobOper(DbOper):

    def publish(self, user_id: int, name: str, *args, **kwargs):
        """
        发布用户任务
        """
        id = db_id()
        # 写入数据库
        userjob = UserJob(
            id=id,
            request_userid=user_id,
            job_name=name,
            job_args=pickle.dumps({
            "args": args,
            "kwargs": kwargs,
        }))
        userjob.create(self._db)
        return id

    def consume(self, userid: str) -> Any:
        """
        消费用户任务
        """
        return UserJob.get_by_user(self._db, userid)

    def done(self, jobid: int, userid: int):
        """
        删除用户任务
        """
        userjob = UserJob.get(self._db, jobid)
        userjob.update(self._db, jobid, {
            "response_userid": userid
        })
