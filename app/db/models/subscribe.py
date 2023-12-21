from sqlalchemy import Column, Integer, String, Sequence, Text
from sqlalchemy.orm import Session

from app.db import db_query, db_update, Base


class Subscribe(Base):
    """
    订阅表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    # 标题
    name = Column(String(255), nullable=False, index=True)
    # 年份
    year = Column(String(255))
    # 类型
    type = Column(String(255))
    # 搜索关键字
    keyword = Column(String(255))
    tmdbid = Column(Integer, index=True)
    imdbid = Column(String(255))
    tvdbid = Column(Integer)
    doubanid = Column(String(255), index=True)
    steamid = Column(Integer, index=True)
    javdbid = Column(String(10), index=True)
    # 季号
    season = Column(Integer)
    # 海报
    poster = Column(String(255))
    # 背景图
    backdrop = Column(String(255))
    # 评分
    vote = Column(Integer)
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
    # 缺失集数
    lack_episode = Column(Integer)
    # 附加信息
    note = Column(String(255))
    # 状态：N-新建， R-订阅中
    state = Column(String(255), nullable=False, index=True, default='N')
    # 最后更新时间
    last_update = Column(String(255))
    # 创建时间
    date = Column(String(255))
    # 订阅用户
    username = Column(String(255))
    # 订阅站点
    sites = Column(String(255))
    # 是否洗版
    best_version = Column(Integer, default=0)
    # 当前优先级
    current_priority = Column(Integer)
    # 保存路径
    save_path = Column(String(4096))

    @staticmethod
    @db_query
    def exists(db: Session, tmdbid: int = None, doubanid: str = None, steamid: int = None, javdbid: str = None, season: int = None):
        if steamid:
            return db.query(Subscribe).filter(Subscribe.steamid == steamid).first()
        elif javdbid:
            return db.query(Subscribe).filter(Subscribe.javdbid == javdbid).first()
        elif tmdbid:
            if season:
                return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid,
                                                  Subscribe.season == season).first()
            return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid).first()
        elif doubanid:
            return db.query(Subscribe).filter(Subscribe.doubanid == doubanid).first()
        return None

    @staticmethod
    @db_query
    def get_by_state(db: Session, state: str):
        result = db.query(Subscribe).filter(Subscribe.state == state).all()
        return list(result)

    @staticmethod
    @db_query
    def get_by_tmdbid(db: Session, tmdbid: int, season: int = None):
        if season:
            result = db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid,
                                                Subscribe.season == season).all()
        else:
            result = db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid).all()
        return list(result)

    @staticmethod
    @db_query
    def get_by_title(db: Session, title: str, season: int = None):
        if season:
            return db.query(Subscribe).filter(Subscribe.name == title,
                                              Subscribe.season == season).first()
        return db.query(Subscribe).filter(Subscribe.name == title).first()

    @staticmethod
    @db_query
    def get_by_doubanid(db: Session, doubanid: str):
        return db.query(Subscribe).filter(Subscribe.doubanid == doubanid).first()

    @staticmethod
    @db_query
    def get_by_steamid(db: Session, steamid: str):
        return db.query(Subscribe).filter(Subscribe.steamid == steamid).first()

    @staticmethod
    @db_query
    def get_by_javdbid(db: Session, javdbid: str):
        return db.query(Subscribe).filter(Subscribe.javdbid == javdbid).first()

    @db_update
    def delete_by_tmdbid(self, db: Session, tmdbid: int, season: int):
        subscrbies = self.get_by_tmdbid(db, tmdbid, season)
        for subscrbie in subscrbies:
            subscrbie.delete(db, subscrbie.id)
        return True

    @db_update
    def delete_by_doubanid(self, db: Session, doubanid: str):
        subscribe = self.get_by_doubanid(db, doubanid)
        if subscribe:
            subscribe.delete(db, subscribe.id)
        return True

    @db_update
    def delete_by_steamid(self, db: Session, steamid: str):
        subscribe = self.get_by_steamid(db, steamid)
        if subscribe:
            subscribe.delete(db, subscribe.id)
        return True

    @db_update
    def delete_by_javdbid(self, db: Session, javdbid: str):
        subscribe = self.get_by_javdbid(db, javdbid)
        if subscribe:
            subscribe.delete(db, subscribe.id)
        return True
