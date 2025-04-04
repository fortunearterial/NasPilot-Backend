from sqlalchemy import Column, Integer, String, Sequence, UniqueConstraint, Index, JSON
from sqlalchemy.orm import Session

from app.db import db_query, db_update, Base


class UserJob(Base):
    """
    用户任务表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    # 需求用户名
    request_userid = Column(String(255), index=True)
    # 响应用户名
    response_userid = Column(String(255))
    # 配置键
    job_name = Column(String(255))
    # 值
    job_args = Column(JSON)

    __table_args__ = (
        Index('ix_userjob_request_userid', 'request_userid'),
    )

    @staticmethod
    @db_query
    def get_by_user(db: Session, userid: str):
        return list(db.query(UserJob) \
                 .filter(UserJob.request_userid == userid or UserJob.request_userid == ''))
