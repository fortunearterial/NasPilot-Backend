from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, JSON, Sequence, String, and_, BigInteger

from app.db import db_query, db_update, db_id, Base


class Workflow(Base):
    """
    工作流表
    """
    # ID
    id = Column(BigInteger, primary_key=True, index=True, default=db_id)
    # 名称
    name = Column(String(255), index=True, nullable=False)
    # 描述
    description = Column(String(255))
    # 定时器
    timer = Column(String(255))
    # 状态：W-等待 R-运行中 P-暂停 S-成功 F-失败
    state = Column(String(255), nullable=False, index=True, default='W')
    # 已执行动作（,分隔）
    current_action = Column(String(255))
    # 任务执行结果
    result = Column(String(255))
    # 已执行次数
    run_count = Column(Integer, default=0)
    # 任务列表
    actions = Column(JSON, default=list)
    # 任务流
    flows = Column(JSON, default=list)
    # 执行上下文
    context = Column(JSON, default=dict)
    # 创建时间
    add_time = Column(String(255), default=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    # 最后执行时间
    last_time = Column(String(255))

    @staticmethod
    @db_query
    def get_enabled_workflows(db):
        return db.query(Workflow).filter(Workflow.state != 'P').all()

    @staticmethod
    @db_query
    def get_by_name(db, name: str):
        return db.query(Workflow).filter(Workflow.name == name).first()

    @staticmethod
    @db_update
    def update_state(db, wid: int, state: str):
        db.query(Workflow).filter(Workflow.id == wid).update({"state": state})
        return True

    @staticmethod
    @db_update
    def start(db, wid: int):
        db.query(Workflow).filter(Workflow.id == wid).update({
            "state": 'R'
        })
        return True

    @staticmethod
    @db_update
    def fail(db, wid: int, result: str):
        db.query(Workflow).filter(and_(Workflow.id == wid, Workflow.state != "P")).update({
            "state": 'F',
            "result": result,
            "last_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return True

    @staticmethod
    @db_update
    def success(db, wid: int, result: Optional[str] = None):
        db.query(Workflow).filter(and_(Workflow.id == wid, Workflow.state != "P")).update({
            "state": 'S',
            "result": result,
            "run_count": Workflow.run_count + 1,
            "last_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return True

    @staticmethod
    @db_update
    def reset(db, wid: int, reset_count: Optional[bool] = False):
        db.query(Workflow).filter(Workflow.id == wid).update({
            "state": 'W',
            "result": None,
            "current_action": None,
            "run_count": 0 if reset_count else Workflow.run_count,
        })
        return True

    @staticmethod
    @db_update
    def update_current_action(db, wid: int, action_id: str, context: dict):
        db.query(Workflow).filter(Workflow.id == wid).update({
            "current_action": Workflow.current_action + f",{action_id}" if Workflow.current_action else action_id,
            "context": context
        })
        return True
