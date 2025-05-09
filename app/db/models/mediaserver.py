from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, JSON, DateTime, BigInteger
from sqlalchemy.orm import Session

from app.db import db_query, db_update, db_id, Base


class MediaServerItem(Base):
    """
    媒体服务器媒体条目表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 服务器类型
    server = Column(String(255))
    # 媒体库ID
    library = Column(String(255))
    # ID
    item_id = Column(String(255), index=True)
    # 类型
    item_type = Column(String(255))
    # 标题
    title = Column(String(255), index=True)
    # 原标题
    original_title = Column(String(255))
    # 年份
    year = Column(String(255))
    # TMDBID
    tmdbid = Column(Integer, index=True)
    # IMDBID
    imdbid = Column(String(255), index=True)
    # TVDBID
    tvdbid = Column(String(255), index=True)
    # 路径
    path = Column(String(2000))
    # 季集
    seasoninfo = Column(JSON, default=dict)
    # 备注
    note = Column(JSON)
    # 同步时间
    lst_mod_date = Column(DateTime, default=datetime.now)

    @staticmethod
    @db_query
    def get_by_itemid(db: Session, item_id: str):
        return db.query(MediaServerItem).filter(MediaServerItem.item_id == item_id).first()

    @staticmethod
    @db_update
    def empty(db: Session, server: Optional[str] = None):
        if server is None:
            db.query(MediaServerItem).delete()
        else:
            db.query(MediaServerItem).filter(MediaServerItem.server == server).delete()

    @staticmethod
    @db_query
    def exist_by_tmdbid(db: Session, tmdbid: int, mtype: str):
        return db.query(MediaServerItem).filter(MediaServerItem.tmdbid == tmdbid,
                                                MediaServerItem.item_type == mtype).first()

    @staticmethod
    @db_query
    def exists_by_title(db: Session, title: str, mtype: str, year: str):
        return db.query(MediaServerItem).filter(MediaServerItem.title == title,
                                                MediaServerItem.item_type == mtype,
                                                MediaServerItem.year == str(year)).first()
