import time
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, JSON, Text, BigInteger, DateTime
from sqlalchemy.orm import Session

from app.db import db_query, db_update, db_id, Base


class Subscribe(Base):
    """
    订阅表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
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
    bangumiid = Column(Integer, index=True)
    mediaid = Column(String(255), index=True)
    # 季号
    season = Column(Integer)
    # 海报
    poster = Column(String(255))
    # 背景图
    backdrop = Column(String(255))
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
    # 最后更新时间
    last_update = Column(String(255))
    # 订阅站点
    sites = Column(JSON, default=list)
    # 是否使用 imdbid 搜索
    search_imdbid = Column(Integer, default=0)
    # 是否手动修改过总集数 0否 1是
    manual_total_episode = Column(Integer, default=0)
    # 自定义识别词
    custom_words = Column(String(255))
    # 自定义媒体类别
    media_category = Column(String(255))
    # 过滤规则组
    filter_groups = Column(JSON, default=list)
    # 选择的剧集组
    episode_group = Column(String(255))

    @staticmethod
    @db_query
    def exists(db: Session, tmdbid: Optional[int] = None, doubanid: Optional[str] = None, steamid: Optional[int] = None,
               javdbid: Optional[str] = None, bangumiid: Optional[int] = None, season: Optional[int] = None):
        if steamid:
            return db.query(Subscribe).filter(Subscribe.steamid == steamid).first()
        elif javdbid:
            # 区分大小写
            return db.query(Subscribe).filter(Subscribe.javdbid == javdbid).first()
        elif tmdbid:
            if season:
                return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid,
                                                  Subscribe.season == season).first()
            return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid).first()
        elif doubanid:
            return db.query(Subscribe).filter(Subscribe.doubanid == doubanid).first()
        elif bangumiid:
            return db.query(Subscribe).filter(Subscribe.bangumiid == bangumiid).first()
        return None

    @staticmethod
    @db_query
    def get_by_title(db: Session, title: str, season: Optional[int] = None):
        if season:
            return db.query(Subscribe).filter(Subscribe.name == title,
                                              Subscribe.season == season).first()
        return db.query(Subscribe).filter(Subscribe.name == title).first()

    @staticmethod
    @db_query
    def get_by_tmdbid(db: Session, tmdbid: int, season: Optional[int] = None):
        if season is not None:
            result = db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid,
                                                Subscribe.season == season).all()
        else:
            result = db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid).all()
        return list(result)

    @staticmethod
    @db_query
    def get_by_doubanid(db: Session, doubanid: str):
        return db.query(Subscribe).filter(Subscribe.doubanid == doubanid).first()

    @staticmethod
    @db_query
    def get_by_bangumiid(db: Session, bangumiid: int):
        return db.query(Subscribe).filter(Subscribe.bangumiid == bangumiid).first()

    @staticmethod
    @db_query
    def get_by_steamid(db: Session, steamid: str):
        return db.query(Subscribe).filter(Subscribe.steamid == steamid).first()

    @staticmethod
    @db_query
    def get_by_javdbid(db: Session, javdbid: str):
        # 区分大小写
        return db.query(Subscribe).filter(Subscribe.javdbid == javdbid).first()

    @staticmethod
    @db_query
    def get_by_mediaid(db: Session, mediaid: str):
        return db.query(Subscribe).filter(Subscribe.mediaid == mediaid).first()

    @staticmethod
    @db_query
    def list_by_type(db: Session, mtype: str, days: int):
        result = db.query(Subscribe) \
            .filter(Subscribe.type == mtype,
                    Subscribe.date >= time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.localtime(time.time() - 86400 * int(days)))
                    ).all()
        return list(result)

    @staticmethod
    @db_query
    def list_by_ids(db: Session, sids: list[int]):
        return db.query(Subscribe).filter(
            Subscribe.id.in_(sids)
        ).all()


class UserSubscribe(Base):
    """
    用户订阅表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 订阅ID
    subscribe_id = Column(BigInteger, index=True)
    # 订阅用户
    user_id = Column(BigInteger)
    # 创建时间
    date = Column(DateTime, default=datetime.now)
    # 缺失集数
    lack_episode = Column(Integer)
    # 状态：N-新建 R-订阅中 P-待定 S-暂停
    state = Column(String(255), nullable=False, index=True, default='N')
    # 下载器
    downloader = Column(String(255))
    # 是否洗版
    best_version = Column(Integer, default=0)
    # 当前优先级
    current_priority = Column(Integer)
    # 保存路径
    save_path = Column(String(2000))
    # 附加信息
    note = Column(JSON)

    @staticmethod
    @db_query
    def exists(db: Session, user_id: int, subscribe_id: int):
        return db.query(UserSubscribe).filter(
            UserSubscribe.subscribe_id == subscribe_id,
            UserSubscribe.user_id == user_id
        ).first()

    @staticmethod
    @db_query
    def get(db: Session, user_id: int, subscribe_id: int):
        return db.query(UserSubscribe).filter(
            UserSubscribe.subscribe_id == subscribe_id,
            UserSubscribe.user_id == user_id
        ).first()

    @staticmethod
    @db_query
    def list_by_userid(db: Session, user_id: int):
        return db.query(UserSubscribe).filter(
            UserSubscribe.user_id == user_id
        ).all()

    @staticmethod
    @db_query
    def list_by_state(db: Session, state: str, user_id: int):
        # 如果传入的状态不为空，拆分成多个状态
        if state:
            states = state.split(',')
            return db.query(UserSubscribe).filter(
                UserSubscribe.state.in_(states),
                UserSubscribe.user_id == user_id
            ).all()
        else:
            return db.query(UserSubscribe).filter(
                UserSubscribe.user_id == user_id
            ).all()

    @staticmethod
    @db_query
    def list_by_subscribeid(db: Session, subscribe_id: int):
        return db.query(UserSubscribe).filter(
            UserSubscribe.subscribe_id == subscribe_id
        ).all()

    @staticmethod
    @db_update
    def delete_by_subscribeid(db: Session, user_id: int, subscribe_id: int):
        return db.query(UserSubscribe).filter(
            UserSubscribe.user_id == user_id,
            UserSubscribe.subscribe_id == subscribe_id
        ).delete()
