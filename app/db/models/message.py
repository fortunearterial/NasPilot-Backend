from typing import Optional

from sqlalchemy import Column, Integer, String, Sequence, JSON, Text, DateTime
from sqlalchemy.orm import Session

from app.db import db_query, Base


class Message(Base):
    """
    消息表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    # 消息渠道
    channel = Column(String(255))
    # 消息来源
    source = Column(String(255))
    # 消息类型
    mtype = Column(String(255))
    # 标题
    title = Column(String(255))
    # 文本内容
    text = Column(Text)
    # 图片
    image = Column(String(2000))
    # 链接
    link = Column(String(2000))
    # 用户ID
    userid = Column(String(255))
    # 登记时间
    reg_time = Column(DateTime, index=True)
    # 消息方向：0-接收息，1-发送消息
    action = Column(Integer)
    # 附件json
    note = Column(JSON)

    @staticmethod
    @db_query
    def list_by_page(db: Session, page: Optional[int] = 1, count: Optional[int] = 30):
        result = db.query(Message).order_by(Message.reg_time.desc()).offset((page - 1) * count).limit(
            count).all()
        result.sort(key=lambda x: x.reg_time, reverse=False)
        return list(result)
