from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db import db_query, db_update, Base


class PluginData(Base):
    """
    插件数据表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    plugin_id = Column(String(255), nullable=False, index=True)
    key = Column(String(255), index=True, nullable=False)
    value = Column(String(255))

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
    @db_query
    def get_plugin_data_by_plugin_id(db: Session, plugin_id: str):
        result = db.query(PluginData).filter(PluginData.plugin_id == plugin_id).all()
        return list(result)
