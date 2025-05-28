from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class TorrentFileParams(BaseModel):
    """迅雷文件参数"""
    download_size: Optional[str] = None
    progress: Optional[str] = None
    speed: Optional[str] = None
    subfile_id: Optional[str] = None


class TorrentFile(BaseModel):
    """迅雷种子文件信息"""
    # 文件类型
    kind: Optional[str] = None
    # 文件ID
    id: Optional[str] = None
    # 父目录ID
    parent_id: Optional[str] = None
    # 文件名
    name: Optional[str] = None
    # 用户ID
    user_id: Optional[str] = None
    # 文件大小
    size: Optional[str] = None
    # 版本
    revision: Optional[str] = None
    # 文件扩展名
    file_extension: Optional[str] = None
    # MIME类型
    mime_type: Optional[str] = None
    # 是否标星
    starred: Optional[bool] = False
    # 网页内容链接
    web_content_link: Optional[str] = None
    # 创建时间
    created_time: Optional[str] = None
    # 修改时间
    modified_time: Optional[str] = None
    # 图标链接
    icon_link: Optional[str] = None
    # 缩略图链接
    thumbnail_link: Optional[str] = None
    # MD5校验和
    md5_checksum: Optional[str] = None
    # 哈希值
    hash: Optional[str] = None
    # 链接
    links: Optional[Dict[str, Any]] = Field(default_factory=dict)
    # 阶段
    phase: Optional[str] = None
    # 审核
    audit: Optional[Any] = None
    # 媒体信息
    medias: Optional[List[Any]] = Field(default_factory=list)
    # 是否已删除
    trashed: Optional[bool] = False
    # 删除时间
    delete_time: Optional[str] = None
    # 原始URL
    original_url: Optional[str] = None
    # 参数
    params: Optional[TorrentFileParams] = None
    # 原始文件索引
    original_file_index: Optional[int] = 0
    # 空间
    space: Optional[str] = None
    # 应用
    apps: Optional[List[Any]] = Field(default_factory=list)
    # 是否可写
    writable: Optional[bool] = False
    # 文件夹类型
    folder_type: Optional[str] = None
    # 集合
    collection: Optional[Any] = None
    # 排序名称
    sort_name: Optional[str] = None
    # 用户修改时间
    user_modified_time: Optional[str] = None
    # 拼写名称
    spell_name: Optional[List[str]] = Field(default_factory=list)
    # 文件类别
    file_category: Optional[str] = None
    # 标签
    tags: Optional[List[str]] = Field(default_factory=list)
    # 引用事件
    reference_events: Optional[List[Any]] = Field(default_factory=list)