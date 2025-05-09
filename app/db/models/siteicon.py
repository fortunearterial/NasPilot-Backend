from sqlalchemy import Column, String, BigInteger
from sqlalchemy.orm import Session

from app.db import db_query, db_id, Base


class SiteIcon(Base):
    """
    站点图标表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 站点名称
    name = Column(String(255), nullable=False)
    # 域名Key
    domain = Column(String(255), index=True)
    # 图标地址
    url = Column(String(255), nullable=False)
    # 图标Base64
    base64 = Column(String(255))

    @staticmethod
    @db_query
    def get_by_domain(db: Session, domain: str):
        return db.query(SiteIcon).filter(SiteIcon.domain == domain).first()
