import time
from typing import Tuple, List, Optional

from app import schemas
from app.core.context import MediaInfo
from app.db import DbOper
from app.db.models.subscribe import Subscribe, UserSubscribe
from app.db.models.subscribehistory import SubscribeHistory
from app.db.models.user import User


class SubscribeOper(DbOper):
    """
    订阅管理
    """

    def add(self, mediainfo: MediaInfo, user_id: int, **kwargs) -> Tuple[int, str]:
        """
        新增订阅
        """
        subscribe = Subscribe.exists(self._db,
                                     tmdbid=mediainfo.tmdb_id,
                                     doubanid=mediainfo.douban_id,
                                     steamid=mediainfo.steam_id,
                                     javdbid=mediainfo.javdb_id,
                                     bangumiid=mediainfo.bangumi_id,
                                     season=kwargs.get('season'))
        kwargs.update({
            "name": mediainfo.title,
            "year": mediainfo.year,
            "type": mediainfo.type.value,
            "tmdbid": mediainfo.tmdb_id,
            "imdbid": mediainfo.imdb_id,
            "tvdbid": mediainfo.tvdb_id,
            "doubanid": mediainfo.douban_id,
            "bangumiid": mediainfo.bangumi_id,
            "steamid": mediainfo.steam_id,
            "javdbid": mediainfo.javdb_id,
            "episode_group": mediainfo.episode_group,
            "poster": mediainfo.get_poster_image(),
            "backdrop": mediainfo.get_backdrop_image(),
            "vote": mediainfo.vote_average,
            "description": mediainfo.overview,
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        })
        if not subscribe:
            subscribe = Subscribe.from_dict(**kwargs)
            subscribe.create(self._db)
            # 查询订阅
            subscribe = Subscribe.exists(self._db,
                                         tmdbid=mediainfo.tmdb_id,
                                         doubanid=mediainfo.douban_id,
                                         steamid=mediainfo.steam_id,
                                         javdbid=mediainfo.javdb_id,
                                         bangumiid=mediainfo.bangumi_id,
                                         season=kwargs.get('season'))
            self._add_user_subscribe(subscribe.id, user_id, **kwargs)
            return subscribe.id, "新增订阅成功"
        else:
            self._add_user_subscribe(subscribe.id, user_id, **kwargs)
            return subscribe.id, "订阅已存在"

    def _add_user_subscribe(self, subscribe_id: int, user_id: int, **kwargs):
        """
        新增用户订阅
        """
        user_subscribe = UserSubscribe.exists(self._db,
                                              user_id=user_id,
                                              subscribe_id=subscribe_id)
        if not user_subscribe:
            user_subscribe = UserSubscribe.from_dict(user_id=user_id,
                                           subscribe_id=subscribe_id,
                                           **kwargs)
            user_subscribe.create(self._db)
            user_subscribe = UserSubscribe.exists(self._db,
                                                  user_id=user_id,
                                                  subscribe_id=subscribe_id)
            return user_subscribe.id, "新增用户订阅成功"
        else:
            return user_subscribe.id, "用户订阅已存在"

    def exists(self, user_id: int, tmdbid: Optional[int] = None, doubanid: Optional[str] = None,
               steamid: Optional[str] = None,
               javdbid: Optional[str] = None, season: Optional[int] = None) -> bool:
        """
        判断是否存在
        """
        if tmdbid:
            if season is not None:
                return True if Subscribe.exists(self._db, tmdbid=tmdbid, season=season) else False
            else:
                return True if Subscribe.exists(self._db, tmdbid=tmdbid) else False
        elif doubanid:
            return True if Subscribe.exists(self._db, doubanid=doubanid) else False
        elif steamid:
            return True if Subscribe.exists(self._db, steamid=steamid) else False
        elif javdbid:
            return True if Subscribe.exists(self._db, javdbid=javdbid) else False
        return False

    def _merge_all(self, subscribes: List[Subscribe], usersubscribes: List[UserSubscribe]) -> List[schemas.Subscribe]:
        """
        合并结果
        """
        results = list()
        for s in subscribes:
            for us in usersubscribes:
                if s.id == us.subscribe_id:
                    rd = s.to_dict()
                    usd = us.to_dict()
                    usd.pop('subscribe_id')
                    usd.pop('id')
                    rd.update(usd)
                    results.append(rd)
                    break
        return results

    def _merge_single(self, subscribe: Subscribe, usersubscribe: UserSubscribe) -> schemas.Subscribe:
        """
        合并结果
        """
        result = dict()
        if subscribe.id == usersubscribe.subscribe_id:
            rd = subscribe.to_dict()
            usd = usersubscribe.to_dict()
            usd.pop('subscribe_id')
            usd.pop('id')
            rd.update(usd)
            result = rd
        return result

    def get(self, sid: int) -> schemas.Subscribe:
        """
        获取订阅
        """
        return Subscribe.get(self._db, rid=sid)

    def get_subscribe(self, sid: int, user_id: int) -> schemas.Subscribe:
        """
        获取订阅
        """
        return self._merge_single(Subscribe.get(self._db, rid=sid),
                                  UserSubscribe.get(self._db, user_id=user_id, subscribe_id=sid))

    def list(self, user_id: int, state: Optional[str] = None) -> List[schemas.Subscribe]:
        """
        获取订阅列表
        """
        if state:
            usersubscribes = UserSubscribe.list_by_state(self._db, state, user_id)
        else:
            usersubscribes = UserSubscribe.list_by_userid(self._db, user_id)

        subscribe_ids = [us.subscribe_id for us in usersubscribes]
        subscribes = Subscribe.list_by_ids(self._db, subscribe_ids)
        return self._merge_all(subscribes, usersubscribes)

    def list_all(self,) -> List[Subscribe]:
        """
        获取订阅列表
        """
        return Subscribe.list(self._db)

    def list_by_userid(self, user_id: int) -> List[schemas.Subscribe]:
        """
        获取订阅列表
        """
        usersubscribes = UserSubscribe.list_by_userid(self._db, user_id)

        subscribe_ids = [us.subscribe_id for us in usersubscribes]
        subscribes = Subscribe.list_by_ids(self._db, subscribe_ids)
        return self._merge_all(subscribes, usersubscribes)

    def delete(self, sid: int):
        """
        删除订阅
        """
        Subscribe.delete(self._db, rid=sid)

    def update(self, sid: int, payload: dict) -> Subscribe:
        """
        更新订阅
        """
        subscribe = self.get(sid)
        if subscribe:
            subscribe.update(self._db, payload)
        return subscribe

    def list_by_tmdbid(self, tmdbid: int, season: Optional[int] = None) -> List[Subscribe]:
        """
        获取指定tmdb_id的订阅
        """
        return Subscribe.get_by_tmdbid(self._db, tmdbid=tmdbid, season=season)

    def list_by_username(self, username: str, state: Optional[str] = None, mtype: Optional[str] = None) -> List[
        Subscribe]:
        """
        获取指定用户的订阅
        """
        return Subscribe.list_by_username(self._db, username=username, state=state, mtype=mtype)

    def list_by_type(self, mtype: str, current_user: User, days: Optional[int] = 7) -> Subscribe:
        """
        获取指定类型的订阅
        """
        return Subscribe.list_by_type(self._db, mtype=mtype, days=days)

    def add_history(self, **kwargs):
        """
        新增订阅
        """
        # 去除kwargs中 SubscribeHistory 没有的字段
        kwargs = {k: v for k, v in kwargs.items() if hasattr(SubscribeHistory, k)}
        # 更新完成订阅时间
        kwargs.update({"date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())})
        # 去掉主键
        if "id" in kwargs:
            kwargs.pop("id")
        subscribe = SubscribeHistory(**kwargs)
        subscribe.create(self._db)

    def exist_history(self, tmdbid: Optional[int] = None, doubanid: Optional[str] = None, season: Optional[int] = None):
        """
        判断是否存在订阅历史
        """
        if tmdbid:
            if season:
                return True if SubscribeHistory.exists(self._db, tmdbid=tmdbid, season=season) else False
            else:
                return True if SubscribeHistory.exists(self._db, tmdbid=tmdbid) else False
        elif doubanid:
            return True if SubscribeHistory.exists(self._db, doubanid=doubanid) else False
        return False

    def is_best_version(self, sid: int):
        """
        判断是否为最佳版本
        """
        usersubscribes = UserSubscribe.list_by_subscribeid(self._db, subscribe_id=sid)
        if usersubscribes:
            for us in usersubscribes:
                if us.best_version == 1:
                    return True
        return False

    def get_current_priority(self, sid: int):
        """
        获取当前优先级
        """
        current_priority = 100
        usersubscribes = UserSubscribe.list_by_subscribeid(self._db, subscribe_id=sid)
        if usersubscribes:
            for us in usersubscribes:
                current_priority = min(current_priority, us.current_priority or 0)
        return current_priority


class UserSubscribeOper(DbOper):
    """
    用户订阅管理
    """

    def list_by_subscribeid(self, subscribe_id: int) -> List[UserSubscribe]:
        """
        获取指定用户的订阅
        """
        return UserSubscribe.list_by_subscribeid(self._db, subscribe_id=subscribe_id)
