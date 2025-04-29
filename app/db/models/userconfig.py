from sqlalchemy import Column, Integer, String, Sequence, UniqueConstraint, Index, JSON, BigInteger
from sqlalchemy.orm import Session

from app.db import db_query, db_update, db_id, Base


class UserConfig(Base):
    """
    用户配置表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 用户名
    username = Column(String(255), index=True)
    # 配置键
    key = Column(String(255))
    # 值
    value = Column(JSON)

    __table_args__ = (
        # 用户名和配置键联合唯一
        UniqueConstraint('username', 'key'),
        Index('ix_userconfig_username_key', 'username', 'key'),
    )

    @staticmethod
    @db_query
    def get_by_key(db: Session, username: str, key: str):
        return db.query(UserConfig) \
                 .filter(UserConfig.username == username) \
                 .filter(UserConfig.key == key) \
                 .first()

    @db_update
    def delete_by_key(self, db: Session, username: str, key: str):
        userconfig = self.get_by_key(db=db, username=username, key=key)
        if userconfig:
            userconfig.delete(db=db, rid=userconfig.id)
        return True
