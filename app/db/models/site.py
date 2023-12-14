from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, String, Sequence, JSON
from sqlalchemy.orm import Session

from app.db import db_query, db_update, Base


class Site(Base):
    """
    站点表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
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
    # FEED地址
    feed = Column(JSON)
    # SEARCH地址
    search = Column(JSON)
    # XPATH
    xpath = Column(String(2000))
    # Cookie
    cookie = Column(String(255))
    # User-Agent
    ua = Column(String(255))
    # 是否使用代理 0-否，1-是
    proxy = Column(Integer)
    # 过滤规则
    filter = Column(String(255))
    # 是否渲染
    render = Column(Integer)
    # 是否公开站点
    public = Column(Integer)
    # 附加信息
    note = Column(String(255))
    # 流控单位周期
    limit_interval = Column(Integer, default=0)
    # 流控次数
    limit_count = Column(Integer, default=0)
    # 流控间隔
    limit_seconds = Column(Integer, default=0)
    # 是否启用
    is_active = Column(Boolean(), default=True)
    # 创建时间
    lst_mod_date = Column(String(255), default=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @staticmethod
    @db_query
    def get_by_domain(db: Session, domain: str):
        return db.query(Site).filter(Site.domain == domain).first()

    @staticmethod
    @db_query
    def get_by_url(db: Session, url: str):
        return db.query(Site).filter(Site.url == url).first()

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
    @db_update
    def reset(db: Session):
        db.query(Site).delete()
