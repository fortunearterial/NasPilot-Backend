from sqlalchemy import Column, Integer, String, Sequence, Float, Text, Date
from sqlalchemy.orm import Session

from app.db import db_query, Base


class SubscribeHistory(Base):
    """
    订阅历史表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    # 标题
    name = Column(String(255), nullable=False, index=True)
    # 年份
    year = Column(String(4))
    # 类型
    type = Column(String(255))
    # 搜索关键字
    keyword = Column(String(255))
    tmdbid = Column(Integer, index=True)
    imdbid = Column(String(255))
    tvdbid = Column(Integer)
    doubanid = Column(String(255), index=True)
    bangumiid = Column(Integer, index=True)
    steamid = Column(Integer, index=True)
    javdbid = Column(Integer, index=True)
    # 季号
    season = Column(Integer)
    # 海报
    poster = Column(String(2000))
    # 背景图
    backdrop = Column(String(2000))
    # 评分，float
    vote = Column(Float)
    # 简介
    description = Column(Text)
    # 过滤规则
    filter = Column(String(255))
    # 包含
    include = Column(String(255))
    # 排除
    exclude = Column(String(255))
    # 质量
    quality = Column(String(255))
    # 分辨率
    resolution = Column(String(255))
    # 特效
    effect = Column(String(255))
    # 总集数
    total_episode = Column(Integer)
    # 开始集数
    start_episode = Column(Integer)
    # 订阅完成时间
    date = Column(Date)
    # 订阅用户
    username = Column(String(255))
    # 订阅站点
    sites = Column(String(255))
    # 是否洗版
    best_version = Column(Integer, default=0)
    # 保存路径
    save_path = Column(String(255))
    # 是否使用 imdbid 搜索
    search_imdbid = Column(Integer, default=0)

    @staticmethod
    @db_query
    def list_by_type(db: Session, mtype: str, page: int = 1, count: int = 30):
        result = db.query(SubscribeHistory).filter(
            SubscribeHistory.type == mtype
        ).order_by(
                SubscribeHistory.date.desc()
        ).offset((page - 1) * count).limit(count).all()
        return list(result)
