from typing import Optional, List

from pydantic import BaseModel

class Feed(BaseModel):
    method: str
    path: str

    class Config:
        orm_mode = False

class Search(BaseModel):
    method: str
    path: str
    body: Optional[str]

    class Config:
        orm_mode = False

class Site(BaseModel):
    # ID
    id: Optional[int]
    # 站点名称
    name: Optional[str]
    # 站点主域名Key
    domain: Optional[str]
    # 站点地址
    url: Optional[str]
    # 站点优先级
    pri: Optional[int] = 0
    # 适用类型
    types: Optional[List[str]] = None
    # FEED地址
    feed: Optional[Feed] = None
    # SEARCH地址
    search: Optional[Search] = None
    # XPATH
    xpath: Optional[str] = None
    # Cookie
    cookie: Optional[str] = None
    # User-Agent
    ua: Optional[str] = None
    # 是否使用代理
    proxy: Optional[int] = 0
    # 过滤规则
    filter: Optional[str] = None
    # 是否演染
    render: Optional[int] = 0
    # 是否公开站点
    public: Optional[int] = 0
    # 备注
    note: Optional[str] = None
    # 流控单位周期
    limit_interval: Optional[int] = None
    # 流控次数
    limit_count: Optional[int] = None
    # 流控间隔
    limit_seconds: Optional[int] = None
    # 是否启用
    is_active: Optional[bool] = True

    class Config:
        orm_mode = True
