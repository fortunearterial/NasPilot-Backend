from sqlalchemy import Column, String, JSON, BigInteger
from sqlalchemy.orm import Session

from app.db import db_query, db_update, db_id, Base


class PluginData(Base):
    """
    插件数据表
    """
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    plugin_id = Column(String(255), nullable=False, index=True)
    key = Column(String(255), index=True, nullable=False)
    value = Column(JSON)

    @staticmethod
    @db_query
    def get_plugin_data(db: Session, plugin_id: str):
        result = db.query(PluginData).filter(PluginData.plugin_id == plugin_id).all()
        return list(result)

    @staticmethod
    @db_query
    def get_plugin_data_by_key(db: Session, plugin_id: str, key: str):
        return db.query(PluginData).filter(PluginData.plugin_id == plugin_id, PluginData.key == key).first()

    @staticmethod
    @db_update
    def del_plugin_data_by_key(db: Session, plugin_id: str, key: str):
        db.query(PluginData).filter(PluginData.plugin_id == plugin_id, PluginData.key == key).delete()

    @staticmethod
    @db_update
    def del_plugin_data(db: Session, plugin_id: str):
        db.query(PluginData).filter(PluginData.plugin_id == plugin_id).delete()

    @staticmethod
    @db_query
    def get_plugin_data_by_plugin_id(db: Session, plugin_id: str):
        result = db.query(PluginData).filter(PluginData.plugin_id == plugin_id).all()
        return list(result)
