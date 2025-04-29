from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, String, Sequence, JSON, Text, DateTime, BigInteger
from sqlalchemy.orm import Session

from app.db import db_query, db_update, db_id, Base


class Site(Base):
    """
    站点表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 站点名
    name = Column(String(255), nullable=False)
    # 域名Key
    domain = Column(String(255), index=True)
    # 站点地址
    url = Column(String(255), nullable=False)
    # 适用类型
    types = Column(JSON)
    # 站点优先级
    pri = Column(Integer, default=1)
    # RSS地址
    rss = Column(String(255))
    # RSS转标准值映射
    rss_mapping = Column(JSON)
    # BROWSE地址
    browse = Column(String(255))
    # BROWSE请求方式
    browse_method = Column(String(20))
    # BROWSE获取种子列表配置
    browse_config = Column(JSON)
    # SEARCH地址
    search = Column(String(255))
    # SEARCH请求方式
    search_method = Column(String(20))
    # SEARCH获取种子列表配置
    search_config = Column(JSON)
    # Cookie
    cookie = Column(Text)
    # User-Agent
    ua = Column(String(255))
    # ApiKey
    apikey = Column(String(255))
    # Token
    token = Column(String(255))
    # 是否使用代理 0-否，1-是
    proxy = Column(Integer)
    # 过滤规则
    filter = Column(String(255))
    # 是否渲染
    render = Column(Integer)
    # 是否公开站点
    public = Column(Integer)
    # 附加信息
    note = Column(JSON)
    # 流控单位周期
    limit_interval = Column(Integer, default=0)
    # 流控次数
    limit_count = Column(Integer, default=0)
    # 流控间隔
    limit_seconds = Column(Integer, default=0)
    # 超时时间
    timeout = Column(Integer, default=15)
    # 是否启用
    is_active = Column(Boolean, default=True)
    # 创建时间
    lst_mod_date = Column(DateTime, default=datetime.now)
    # 下载器
    downloader = Column(String(20))

    @staticmethod
    @db_query
    def get_by_domain(db: Session, domain: str):
        return db.query(Site).filter(Site.domain == domain).first()

    @staticmethod
    @db_query
    def get_actives(db: Session):
        result = db.query(Site).filter(Site.is_active == 1).all()
        return list(result)

    @staticmethod
    @db_query
    def list_order_by_pri(db: Session):
        result = db.query(Site).order_by(Site.pri).all()
        return list(result)

    @staticmethod
    @db_query
    def get_domains_by_ids(db: Session, ids: list):
        result = db.query(Site.domain).filter(Site.id.in_(ids)).all()
        return [r[0] for r in result]

    @staticmethod
    @db_update
    def reset(db: Session):
        db.query(Site).delete()
