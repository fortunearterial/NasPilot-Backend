from sqlalchemy import Column, String, UniqueConstraint, Index, JSON, BigInteger
from sqlalchemy.orm import Session

from app.db import db_query, db_update, db_id, Base


class UserConfig(Base):
    """
    用户配置表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 用户ID
    user_id = Column(BigInteger, index=True)
    # 配置键
    key = Column(String(255))
    # 值
    value = Column(JSON)

    __table_args__ = (
        # 用户名和配置键联合唯一
        UniqueConstraint('user_id', 'key'),
        Index('ix_userconfig_username_key', 'user_id', 'key'),
    )

    @staticmethod
    @db_query
    def get_by_key(db: Session, user_id: int, key: str):
        return db.query(UserConfig) \
                 .filter(UserConfig.user_id == user_id) \
                 .filter(UserConfig.key == key) \
                 .first()

    @db_update
    def delete_by_key(self, db: Session, user_id: int, key: str):
        userconfig = self.get_by_key(db=db, user_id=user_id, key=key)
        if userconfig:
            userconfig.delete(db=db, rid=userconfig.id)
        return True
