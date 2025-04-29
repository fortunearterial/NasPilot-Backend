import asyncio
import copy
import gc
import inspect
import json
import pickle
import sys
import traceback
from abc import ABCMeta
from pathlib import Path
from typing import Optional, Any, Tuple, List, Set, Union, Dict, get_origin, get_args, Type

from qbittorrentapi import TorrentFilesList
from transmission_rpc import File

from app.core.config import settings
from app.core.context import Context, MediaInfo, TorrentInfo
from app.core.event import EventManager
from app.core.meta import MetaBase
from app.core.module import ModuleManager
from app.db.message_oper import MessageOper
from app.db.user_oper import UserOper
from app.helper.message import MessageHelper, MessageQueueManager
from app.helper.service import ServiceConfigHelper
from app.log import logger
from app.schemas import TransferInfo, TransferTorrent, ExistMediaInfo, DownloadingTorrent, CommingMessage, Notification, \
    WebhookEventInfo, TmdbEpisode, MediaPerson, FileItem, TransferDirectoryConf
from app.schemas.types import TorrentStatus, MediaType, MediaImageType, EventType
from app.utils.object import ObjectUtils
from app.db.userjob_oper import UserJobOper


class ChainBase(metaclass=ABCMeta):
    """
    处理链基类
    """

    def __init__(self):
        """
        公共初始化
        """
        self.modulemanager = ModuleManager()
        self.eventmanager = EventManager()
        self.messageoper = MessageOper()
        self.messagehelper = MessageHelper()
        self.messagequeue = MessageQueueManager(
            send_callback=self.run_module
        )
        self.useroper = UserOper()
        self.userjoboper = UserJobOper()

    @staticmethod
    def load_cache(filename: str) -> Any:
        """
        从本地加载缓存
        """
        cache_path = settings.TEMP_PATH / filename
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as err:
                logger.error(f"加载缓存 {filename} 出错：{str(err)}")
        return None

    @staticmethod
    def save_cache(cache: Any, filename: str) -> None:
        """
        保存缓存到本地
        """
        try:
            with open(settings.TEMP_PATH / filename, 'wb') as f:
                pickle.dump(cache, f)  # noqa
        except Exception as err:
            logger.error(f"保存缓存 {filename} 出错：{str(err)}")
        finally:
            # 主动资源回收
            del cache
            gc.collect()

    @staticmethod
    def remove_cache(filename: str) -> None:
        """
        删除本地缓存
        """
        cache_path = settings.TEMP_PATH / filename
        if cache_path.exists():
            cache_path.unlink()

    def run_module(self, method: str, user_id: int = None, *args, **kwargs) -> Any:
        """
        运行包含该方法的所有模块，然后返回结果
        当kwargs包含命名参数raise_exception时，如模块方法抛出异常且raise_exception为True，则同步抛出异常
        """

        def is_result_empty(ret):
            """
            判断结果是否为空
            """
            if isinstance(ret, tuple):
                return all(value is None for value in ret)
            else:
                return ret is None

        def extract_inner_type(annotation):
            origin = get_origin(annotation)
            args = get_args(annotation)

            # 递归解析嵌套类型
            if origin is Union:  # Optional 实际是 Union[T, None]
                inner_type = next((arg for arg in args if arg is not type(None)), None)
                return extract_inner_type(inner_type)
            elif origin is list or origin is List:  # List[T]
                return extract_inner_type(args[0])
            else:
                return annotation

        def get_method_return_annotation():
            """
            获取方法的参数名和默认值
            """
            # 获取当前堆栈帧的上一级帧（即调用者）
            for i in range(1, 50):
                if sys._getframe(i).f_code.co_name == "run_module":
                    caller_frame = sys._getframe(i + 1)
                    break
            # 获取调用者的函数对象
            caller_func_name = caller_frame.f_code.co_name
            # 尝试从实例中获取方法（若调用者是类方法）
            instance = caller_frame.f_locals.get('self', None)
            if instance:
                caller_func_obj = getattr(instance.__class__, caller_func_name, None)
            else:
                caller_func_obj = caller_frame.f_globals.get(caller_func_name, None)
            return_annotation = caller_func_obj.__annotations__.get('return', None)
            return extract_inner_type(return_annotation)

        def broadcast_to_clients(method: str, timeout: int = 5, *args, **kwargs):
            """
            广播消息给所有客户端
            """
            logger.debug(f"请求[广播]模块执行：{method}(args={args}, kwargs={kwargs}) ...")

            # 模式，交由websocket广播处理
            from app.api.websockets import ConnectionManager
            # 获取调用者的返回类型注解
            return_annotation = get_method_return_annotation()

            try:
                results = asyncio.run(ConnectionManager().broadcast(
                    request_data={"method": method, "args": args, "kwargs": kwargs},
                    timeout=timeout
                ))
                if not results:
                    return None
                return [return_annotation(**result) for result in results]
            except BaseException as ex:
                logger.error(f"执行[广播]模块 {method} 出错，转由服务端执行：{str(ex)}")
                return run_on_server(method=method, *args, **kwargs)

        def send_to_client(user_id: int, method: str, timeout: int = 5, *args, **kwargs):
            """
            发送消息给指定客户端
            """
            logger.debug(f"请求[单机]模块执行：{method}(args={args}, kwargs={kwargs}) ...")
            if not user_id:
                raise Exception("user_id is required")

            # 实时模式，交由websocket单点处理
            from app.api.websockets import ConnectionManager
            # 获取调用者的返回类型注解
            return_annotation = get_method_return_annotation()

            try:
                results = asyncio.run(
                    ConnectionManager().send(user_id=user_id,
                                             request_data={"method": method, "args": args, "kwargs": kwargs},
                                             timeout=timeout)
                )
                if not results:
                    return None
                return [return_annotation(**result) for result in results]
            except BaseException as ex:
                logger.error(f"执行[单机]模块 {method} 出错：{str(ex)}")
                return None

        def run_on_server(method: str, *args, **kwargs):
            logger.debug(f"请求[服务端]模块执行：{method} ...")

            result = None
            modules = self.modulemanager.get_running_modules(method)
            # 按优先级排序
            modules = sorted(modules, key=lambda x: x.get_priority())
            for module in modules:
                module_id = module.__class__.__name__
                try:
                    module_name = module.get_name()
                except Exception as err:
                    logger.debug(f"获取[服务端]模块名称出错：{str(err)}")
                    module_name = module_id
                try:
                    func = getattr(module, method)
                    if is_result_empty(result):
                        # 返回None，第一次执行或者需继续执行下一模块
                        result = func(*args, **kwargs)
                    elif ObjectUtils.check_signature(func, result):
                        # 返回结果与方法签名一致，将结果传入（不能多个模块同时运行的需要通过开关控制）
                        result = func(result)
                    elif isinstance(result, list):
                        # 返回为列表，有多个模块运行结果时进行合并（不能多个模块同时运行的需要通过开关控制）
                        temp = func(*args, **kwargs)
                        if isinstance(temp, list):
                            result.extend(temp)
                    else:
                        # 中止继续执行
                        break
                except Exception as err:
                    if kwargs.get("raise_exception"):
                        raise
                    logger.error(
                        f"运行[服务端]模块 {module_id}.{method} 出错：{str(err)}\n{traceback.format_exc()}")
                    self.messagehelper.put(title=f"{module_name}发生了错误",
                                           message=str(err),
                                           role="system")
                    self.eventmanager.send_event(
                        EventType.SystemError,
                        {
                            "type": "module",
                            "module_id": module_id,
                            "module_name": module_name,
                            "module_method": method,
                            "error": str(err),
                            "traceback": traceback.format_exc()
                        }
                    )
            return result

        if method in [
            "tmdb_discover", "tmdb_trending",
            "bangumi_calendar",
            "douban_discover",
            "movie_showing", "movie_top250", "tv_weekly_chinese", "tv_weekly_global", "tv_animation",
            "movie_hot", "tv_hot",
            "recognize_media", "refresh_torrents"
        ]:
            return broadcast_to_clients(method=method, timeout=60, *args, **kwargs)
        elif method in ["downloader_info", "list_files", "download"]:
            return send_to_client(user_id=user_id, method=method, *args, **kwargs)
        if method in ["mediaserver_librarys"]:
            # 延迟模式，由用户消费
            self.userjoboper.publish(user_id=user_id, method=method, *args, **kwargs)
            return None
        else:
            return run_on_server(method=method, *args, **kwargs)

    def recognize_media(self, meta: MetaBase = None,
                        mtype: Optional[MediaType] = None,
                        tmdbid: Optional[int] = None,
                        doubanid: Optional[str] = None,
                        steamid: Optional[int] = None,
                        javdbid: Optional[str] = None,
                        bangumiid: Optional[int] = None,
                        episode_group: Optional[str] = None,
                        cache: bool = True) -> Optional[MediaInfo]:
        """
        识别媒体信息，不含Fanart图片
        :param meta:     识别的元数据
        :param mtype:    识别的媒体类型，与tmdbid配套
        :param tmdbid:   tmdbid
        :param doubanid: 豆瓣ID
        :param steamid: STEAM ID
        :param javdbid: JAVDB ID
        :param bangumiid: BangumiID
        :param episode_group: 剧集组
        :param cache:    是否使用缓存
        :return: 识别的媒体信息，包括剧集信息
        """
        # 识别用名中含指定信息情形
        if not mtype and meta and meta.type in [MediaType.TV, MediaType.MOVIE, MediaType.GAME, MediaType.JAV]:
            mtype = meta.type
        if not tmdbid and hasattr(meta, "tmdbid"):
            tmdbid = meta.tmdbid
        if not doubanid and hasattr(meta, "doubanid"):
            doubanid = meta.doubanid
        if not bangumiid and hasattr(meta, "bangumiid"):
            bangumiid = meta.bangumiid
        if not steamid and hasattr(meta, "steamid"):
            steamid = meta.steamid
        if not javdbid and hasattr(meta, "javdbid"):
            javdbid = meta.javdbid
        # 有tmdbid时不使用其它ID
        if tmdbid:
            doubanid = None
            bangumiid = None
        # TODO: self.run_module("recognize_media_id", media_info=media_info, cache=cache)
        return self.run_module("recognize_media", meta=meta, mtype=mtype,
                               tmdbid=tmdbid, doubanid=doubanid, steamid=steamid, javdbid=javdbid, bangumiid=bangumiid,
                               episode_group=episode_group, cache=cache)

    def match_doubaninfo(self, name: str, imdbid: Optional[str] = None,
                         mtype: Optional[MediaType] = None, year: Optional[str] = None, season: Optional[int] = None,
                         raise_exception: bool = False) -> Optional[dict]:
        """
        搜索和匹配豆瓣信息
        :param name: 标题
        :param imdbid: imdbid
        :param mtype: 类型
        :param year: 年份
        :param season: 季
        :param raise_exception: 触发速率限制时是否抛出异常
        """
        return self.run_module("match_doubaninfo", name=name, imdbid=imdbid,
                               mtype=mtype, year=year, season=season, raise_exception=raise_exception)

    def match_tmdbinfo(self, name: str, mtype: Optional[MediaType] = None,
                       year: Optional[str] = None, season: Optional[int] = None) -> Optional[dict]:
        """
        搜索和匹配TMDB信息
        :param name: 标题
        :param mtype: 类型
        :param year: 年份
        :param season: 季
        """
        return self.run_module("match_tmdbinfo", name=name,
                               mtype=mtype, year=year, season=season)

    def obtain_images(self, mediainfo: MediaInfo) -> Optional[MediaInfo]:
        """
        补充抓取媒体信息图片
        :param mediainfo:  识别的媒体信息
        :return: 更新后的媒体信息
        """
        return self.run_module("obtain_images", mediainfo=mediainfo)

    def obtain_specific_image(self, mediaid: Union[str, int], mtype: MediaType,
                              image_type: MediaImageType, image_prefix: Optional[str] = None,
                              season: Optional[int] = None, episode: Optional[int] = None) -> Optional[str]:
        """
        获取指定媒体信息图片，返回图片地址
        :param mediaid:     媒体ID
        :param mtype:       媒体类型
        :param image_type:  图片类型
        :param image_prefix: 图片前缀
        :param season:      季
        :param episode:     集
        """
        return self.run_module("obtain_specific_image", mediaid=mediaid, mtype=mtype,
                               image_prefix=image_prefix, image_type=image_type,
                               season=season, episode=episode)

    def douban_info(self, doubanid: str, mtype: Optional[MediaType] = None,
                    raise_exception: bool = False) -> Optional[dict]:
        """
        获取豆瓣信息
        :param doubanid: 豆瓣ID
        :param mtype: 媒体类型
        :return: 豆瓣信息
        :param raise_exception: 触发速率限制时是否抛出异常
        """
        return self.run_module("douban_info", doubanid=doubanid, mtype=mtype, raise_exception=raise_exception)

    def tvdb_info(self, tvdbid: int) -> Optional[dict]:
        """
        获取TVDB信息
        :param tvdbid: int
        :return: TVDB信息
        """
        return self.run_module("tvdb_info", tvdbid=tvdbid)

    def tmdb_info(self, tmdbid: int, mtype: MediaType, season: Optional[int] = None) -> Optional[dict]:
        """
        获取TMDB信息
        :param tmdbid: int
        :param mtype:  媒体类型
        :param season: 季
        :return: TVDB信息
        """
        return self.run_module("tmdb_info", tmdbid=tmdbid, mtype=mtype, season=season)

    def bangumi_info(self, bangumiid: int) -> Optional[dict]:
        """
        获取Bangumi信息
        :param bangumiid: int
        :return: Bangumi信息
        """
        return self.run_module("bangumi_info", bangumiid=bangumiid)

    def message_parser(self, source: str, body: Any, form: Any,
                       args: Any) -> Optional[CommingMessage]:
        """
        解析消息内容，返回字典，注意以下约定值：
        userid: 用户ID
        username: 用户名
        text: 内容
        :param source: 消息来源（渠道配置名称）
        :param body: 请求体
        :param form: 表单
        :param args: 参数
        :return: 消息渠道、消息内容
        """
        return self.run_module("message_parser", source=source, body=body, form=form, args=args)

    def webhook_parser(self, body: Any, form: Any, args: Any) -> Optional[WebhookEventInfo]:
        """
        解析Webhook报文体
        :param body:  请求体
        :param form:  请求表单
        :param args:  请求参数
        :return: 字典，解析为消息时需要包含：title、text、image
        """
        return self.run_module("webhook_parser", body=body, form=form, args=args)

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        搜索媒体信息
        :param meta:  识别的元数据
        :reutrn: 媒体信息列表
        """
        return self.run_module("search_medias", meta=meta)

    def search_persons(self, name: str) -> Optional[List[MediaPerson]]:
        """
        搜索人物信息
        :param name:  人物名称
        """
        return self.run_module("search_persons", name=name)

    def search_collections(self, name: str) -> Optional[List[MediaInfo]]:
        """
        搜索集合信息
        :param name:  集合名称
        """
        return self.run_module("search_collections", name=name)

    def search_torrents(self, site: dict,
                        keywords: List[str],
                        mtype: Optional[MediaType] = None,
                        page: Optional[int] = 0) -> List[TorrentInfo]:
        """
        搜索一个站点的种子资源
        :param site:  站点
        :param keywords:  搜索关键词列表
        :param mtype:  媒体类型
        :param page:  页码
        :reutrn: 资源列表
        """
        return self.run_module("search_torrents", site=site, keywords=keywords,
                               mtype=mtype, page=page)

    def refresh_torrents(self, site: dict, keyword: Optional[str] = None,
                         cat: Optional[str] = None, page: Optional[int] = 0) -> List[TorrentInfo]:
        """
        获取站点最新一页的种子，多个站点需要多线程处理
        :param site:  站点
        :param keyword:  标题
        :param cat:  分类
        :param page:  页码
        :reutrn: 种子资源列表
        """
        return self.run_module("refresh_torrents", site=site, keyword=keyword, cat=cat, page=page)

    def filter_torrents(self, rule_groups: List[str],
                        torrent_list: List[TorrentInfo],
                        mediainfo: MediaInfo = None) -> List[TorrentInfo]:
        """
        过滤种子资源
        :param rule_groups:  过滤规则组名称列表
        :param torrent_list:  资源列表
        :param mediainfo:  识别的媒体信息
        :return: 过滤后的资源列表，添加资源优先级
        """
        return self.run_module("filter_torrents", rule_groups=rule_groups,
                               torrent_list=torrent_list, mediainfo=mediainfo)

    def download(self, content: Union[Path, str], download_dir: Path, cookie: str,
                 episodes: Set[int] = None, category: Optional[str] = None, label: Optional[str] = None,
                 downloader: Optional[str] = None
                 ) -> Optional[Tuple[Optional[str], Optional[str], Optional[str], str]]:
        """
        根据种子文件，选择并添加下载任务
        :param content:  种子文件地址或者磁力链接
        :param download_dir:  下载目录
        :param cookie:  cookie
        :param episodes:  需要下载的集数
        :param category:  种子分类
        :param label:  标签
        :param downloader:  下载器
        :return: 下载器名称、种子Hash、种子文件布局、错误原因
        """
        return self.run_module("download", content=content, download_dir=download_dir,
                               cookie=cookie, episodes=episodes, category=category, label=label,
                               downloader=downloader)

    def download_added(self, context: Context, download_dir: Path, torrent_path: Path = None) -> None:
        """
        添加下载任务成功后，从站点下载字幕，保存到下载目录
        :param context:  上下文，包括识别信息、媒体信息、种子信息
        :param download_dir:  下载目录
        :param torrent_path:  种子文件地址
        :return: None，该方法可被多个模块同时处理
        """
        return self.run_module("download_added", context=context, torrent_path=torrent_path,
                               download_dir=download_dir)

    def list_torrents(self, status: TorrentStatus = None,
                      hashs: Union[list, str] = None,
                      downloader: Optional[str] = None
                      ) -> Optional[List[Union[TransferTorrent, DownloadingTorrent]]]:
        """
        获取下载器种子列表
        :param status:  种子状态
        :param hashs:  种子Hash
        :param downloader:  下载器
        :return: 下载器中符合状态的种子列表
        """
        return self.run_module("list_torrents", status=status, hashs=hashs, downloader=downloader)

    def transfer(self, fileitem: FileItem, meta: MetaBase, mediainfo: MediaInfo,
                 target_directory: TransferDirectoryConf = None,
                 target_storage: Optional[str] = None, target_path: Path = None,
                 transfer_type: Optional[str] = None, scrape: bool = None,
                 library_type_folder: bool = None, library_category_folder: bool = None,
                 episodes_info: List[TmdbEpisode] = None) -> Optional[TransferInfo]:
        """
        文件转移
        :param fileitem:  文件信息
        :param meta: 预识别的元数据
        :param mediainfo:  识别的媒体信息
        :param target_directory:  目标目录配置
        :param target_storage:  目标存储
        :param target_path:  目标路径
        :param transfer_type:  转移模式
        :param scrape: 是否刮削元数据
        :param library_type_folder: 是否按类型创建目录
        :param library_category_folder: 是否按类别创建目录
        :param episodes_info: 当前季的全部集信息
        :return: {path, target_path, message}
        """
        return self.run_module("transfer",
                               fileitem=fileitem, meta=meta, mediainfo=mediainfo,
                               target_directory=target_directory,
                               target_path=target_path, target_storage=target_storage,
                               transfer_type=transfer_type, scrape=scrape,
                               library_type_folder=library_type_folder,
                               library_category_folder=library_category_folder,
                               episodes_info=episodes_info)

    def transfer_completed(self, hashs: str, downloader: Optional[str] = None) -> None:
        """
        下载器转移完成后的处理
        :param hashs:  种子Hash
        :param downloader:  下载器
        """
        return self.run_module("transfer_completed", hashs=hashs, downloader=downloader)

    def remove_torrents(self, hashs: Union[str, list], delete_file: bool = True,
                        downloader: Optional[str] = None) -> bool:
        """
        删除下载器种子
        :param hashs:  种子Hash
        :param delete_file: 是否删除文件
        :param downloader:  下载器
        :return: bool
        """
        return self.run_module("remove_torrents", hashs=hashs, delete_file=delete_file, downloader=downloader)

    def start_torrents(self, hashs: Union[list, str], downloader: Optional[str] = None) -> bool:
        """
        开始下载
        :param hashs:  种子Hash
        :param downloader:  下载器
        :return: bool
        """
        return self.run_module("start_torrents", hashs=hashs, downloader=downloader)

    def stop_torrents(self, hashs: Union[list, str], downloader: Optional[str] = None) -> bool:
        """
        停止下载
        :param hashs:  种子Hash
        :param downloader:  下载器
        :return: bool
        """
        return self.run_module("stop_torrents", hashs=hashs, downloader=downloader)

    def torrent_files(self, tid: str,
                      downloader: Optional[str] = None) -> Optional[Union[TorrentFilesList, List[File]]]:
        """
        获取种子文件
        :param tid:  种子Hash
        :param downloader:  下载器
        :return: 种子文件
        """
        return self.run_module("torrent_files", tid=tid, downloader=downloader)

    def media_exists(self, mediainfo: MediaInfo, itemid: Optional[str] = None,
                     server: Optional[str] = None) -> Optional[ExistMediaInfo]:
        """
        判断媒体文件是否存在
        :param mediainfo:  识别的媒体信息
        :param itemid:  媒体服务器ItemID
        :param server:  媒体服务器
        :return: 如不存在返回None，存在时返回信息，包括每季已存在所有集{type: movie/tv, seasons: {season: [episodes]}}
        """
        return self.run_module("media_exists", mediainfo=mediainfo, itemid=itemid, server=server)

    def media_files(self, mediainfo: MediaInfo) -> Optional[List[FileItem]]:
        """
        获取媒体文件清单
        :param mediainfo:  识别的媒体信息
        :return: 媒体文件列表
        """
        return self.run_module("media_files", mediainfo=mediainfo)

    def post_message(self, message: Notification) -> None:
        """
        发送消息
        :param message:  消息体
        :return: 成功或失败
        """
        # 保存原消息
        self.messagehelper.put(message, role="user", title=message.title)
        self.messageoper.add(**message.dict())
        # 发送消息按设置隔离
        if not message.userid and message.mtype:
            # 消息隔离设置
            notify_action = ServiceConfigHelper.get_notification_switch(message.mtype)
            if notify_action:
                # 'admin' 'user,admin' 'user' 'all'
                actions = notify_action.split(",")
                # 是否已发送管理员标志
                admin_sended = False
                send_orignal = False
                for action in actions:
                    send_message = copy.deepcopy(message)
                    if action == "admin" and not admin_sended:
                        # 仅发送管理员
                        logger.info(f"{send_message.mtype} 的消息已设置发送给管理员")
                        # 读取管理员消息IDS
                        send_message.targets = self.useroper.get_settings(settings.SUPERUSER)
                        admin_sended = True
                    elif action == "user" and send_message.username:
                        # 发送对应用户
                        logger.info(f"{send_message.mtype} 的消息已设置发送给用户 {send_message.username}")
                        # 读取用户消息IDS
                        send_message.targets = self.useroper.get_settings(send_message.username)
                        if send_message.targets is None:
                            # 没有找到用户
                            if not admin_sended:
                                # 回滚发送管理员
                                logger.info(f"用户 {send_message.username} 不存在，消息将发送给管理员")
                                # 读取管理员消息IDS
                                send_message.targets = self.useroper.get_settings(settings.SUPERUSER)
                                admin_sended = True
                            else:
                                # 管理员发过了，此消息不发了
                                logger.info(f"用户 {send_message.username} 不存在，消息无法发送到对应用户")
                                continue
                        elif send_message.username == settings.SUPERUSER:
                            # 管理员同名已发送
                            admin_sended = True
                    else:
                        # 按原消息发送全体
                        if not admin_sended:
                            send_orignal = True
                        break
                    # 按设定发送
                    self.eventmanager.send_event(etype=EventType.NoticeMessage,
                                                 data={**send_message.dict(), "type": send_message.mtype})
                    self.messagequeue.send_message("post_message", message=send_message)
                if not send_orignal:
                    return
        # 发送消息事件
        self.eventmanager.send_event(etype=EventType.NoticeMessage, data={**message.dict(), "type": message.mtype})
        # 按原消息发送
        self.messagequeue.send_message("post_message", message=message)

    def post_medias_message(self, message: Notification, medias: List[MediaInfo]) -> None:
        """
        发送媒体信息选择列表
        :param message:  消息体
        :param medias:  媒体列表
        :return: 成功或失败
        """
        note_list = [media.to_dict() for media in medias]
        self.messagehelper.put(message, role="user", note=note_list, title=message.title)
        self.messageoper.add(**message.dict(), note=note_list)
        return self.messagequeue.send_message("post_medias_message", message=message, medias=medias)

    def post_torrents_message(self, message: Notification, torrents: List[Context]) -> None:
        """
        发送种子信息选择列表
        :param message:  消息体
        :param torrents:  种子列表
        :return: 成功或失败
        """
        note_list = [torrent.torrent_info.to_dict() for torrent in torrents]
        self.messagehelper.put(message, role="user", note=note_list, title=message.title)
        self.messageoper.add(**message.dict(), note=note_list)
        return self.messagequeue.send_message("post_torrents_message", message=message, torrents=torrents)

    def metadata_img(self, mediainfo: MediaInfo,
                     season: Optional[int] = None, episode: Optional[int] = None) -> Optional[dict]:
        """
        获取图片名称和url
        :param mediainfo: 媒体信息
        :param season: 季号
        :param episode: 集号
        """
        return self.run_module("metadata_img", mediainfo=mediainfo, season=season, episode=episode)

    def media_category(self) -> Optional[Dict[str, list]]:
        """
        获取媒体分类
        :return: 获取二级分类配置字典项，需包括电影、电视剧
        """
        return self.run_module("media_category")

    def register_commands(self, commands: Dict[str, dict]) -> None:
        """
        注册菜单命令
        """
        self.run_module("register_commands", commands=commands)

    def scheduler_job(self) -> None:
        """
        定时任务，每10分钟调用一次，模块实现该接口以实现定时服务
        """
        self.run_module("scheduler_job")

    def clear_cache(self) -> None:
        """
        清理缓存，模块实现该接口响应清理缓存事件
        """
        self.run_module("clear_cache")
