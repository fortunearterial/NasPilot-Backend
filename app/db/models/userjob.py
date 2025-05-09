from sqlalchemy import Column, String, BigInteger, BLOB, or_
from sqlalchemy.orm import Session

from app.db import db_query, db_id, Base


class UserJob(Base):
    """
    用户任务表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 需求用户名
    request_userid = Column(String(255), index=True)
    # 响应用户名
    response_userid = Column(String(255))
    # 配置键
    job_name = Column(String(255))
    # 值
    job_args = Column(BLOB)

    @staticmethod
    @db_query
    def get_by_user(db: Session, userid: int):
        return db.query(UserJob).filter(or_(UserJob.request_userid == userid, UserJob.request_userid == 0),
                                        UserJob.response_userid.is_(None)).all()
