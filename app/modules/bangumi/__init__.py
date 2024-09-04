from typing import List, Optional, Tuple, Union
from functools import lru_cache

import re

from app import schemas
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.bangumi.bangumi import BangumiApi
from app.utils.http import RequestUtils


class BangumiModule(_ModuleBase):
    bangumiapi: BangumiApi = None

    def init_module(self) -> None:
        self.bangumiapi = BangumiApi()

    def stop(self):
        pass

    def test(self) -> Tuple[bool, str]:
        """
        测试模块连接性
        """
        ret = RequestUtils().get_res("https://api.bgm.tv/")
        if ret and ret.status_code == 200:
            return True, ""
        elif ret:
            return False, f"无法连接Bangumi，错误码：{ret.status_code}"
        return False, "Bangumi网络连接失败"

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    @staticmethod
    def get_name() -> str:
        return "Bangumi"

    def recognize_media(self, meta: MetaBase = None,
                        mtype: MediaType = None,
                        bangumiid: int = None,
                        only_ova_episodes: bool = False,
                        **kwargs) -> Optional[MediaInfo]:
        """
        识别媒体信息
        :param bangumiid: 识别的Bangumi ID
        :return: 识别的媒体信息，包括剧集信息
        """
        if settings.RECOGNIZE_SOURCE and not "bangumi" in settings.RECOGNIZE_SOURCE:
            return None
        if not bangumiid:
            return None

        # 直接查询详情
        info = self.bangumi_info(bangumiid=bangumiid, only_ova_episodes=only_ova_episodes)
        if info:
            # 赋值TMDB信息并返回
            mediainfo = MediaInfo(bangumi_info=info)
            logger.info(f"{bangumiid} Bangumi识别结果：{mediainfo.type.value} "
                        f"{mediainfo.title_year}")
            return mediainfo
        else:
            logger.info(f"{bangumiid} 未匹配到Bangumi媒体信息")

        return None

    def recognize_media_id(self, media_info: MediaInfo = None,
                        **kwargs) -> None:
        """
        识别媒体信息
        :param bangumiid: 识别的Bangumi ID
        :return: 识别的媒体信息，包括剧集信息
        """
        if settings.RECOGNIZE_SOURCE and not "bangumi" in settings.RECOGNIZE_SOURCE:
            return
        if not media_info:
            return
        if media_info.bangumi_id:
            return

        infos = self.search_medias(MetaInfo(title=media_info.original_title, mtype=media_info.type.value))
        for info in infos:
            if info.original_title == media_info.original_title \
                or info.title == media_info.title:
                media_info.bangumi_id = info.bangumi_id
                break

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        搜索媒体信息
        :param meta:  识别的元数据
        :reutrn: 媒体信息
        """
        if settings.SEARCH_SOURCE and "bangumi" not in settings.SEARCH_SOURCE:
            return None
        if not meta.name:
            return []
        infos = self.bangumiapi.search(meta.name)
        if infos:
            return [MediaInfo(bangumi_info=info) for info in infos
                    if meta.name.lower() in str(info.get("name")).lower()
                    or meta.name.lower() in str(info.get("name_cn")).lower()]
        return []

    @lru_cache(maxsize=128)
    def bangumi_info(self, bangumiid: int, only_ova_episodes: bool = False) -> Optional[dict]:
        """
        获取Bangumi信息
        :param bangumiid: BangumiID
        :return: Bangumi信息
        """
        if not bangumiid:
            return None
        logger.info(f"开始获取Bangumi信息：{bangumiid} ...")
        #FIX: 补充季信息
        subjects = self.bangumiapi.subjects(bangumiid)
        # 如果有上一季
        prev_season_details = list(filter(lambda s: s.get('relation') == '前传', subjects))
        if prev_season_details:
            # 返回第一季的信息
            return self.bangumi_info(prev_season_details[0].get('id'))

        seasons = {}
        season_eps = {}
        self._fill_season(seasons, season_eps, 1, bangumiid,only_ova_episodes)

        detail = self.bangumiapi.detail(bangumiid)
        # 季0
        if '0' in season_eps:
            season_eps['0'] = list(sorted([dict(t) for t in set([tuple(d.items()) for d in season_eps.get('0')])], key=lambda t: t.get('airdate')))
            seasons[0] = {
                "date": season_eps['0'][0].get('airdate'),
                "total_episodes": len(season_eps['0']),
                "name": "特别篇",
                "season_number": 0
            }
        detail['seasons'] = list([seasons.get(s) for s in sorted(seasons.keys())])
        detail['_season_eps'] = season_eps
        return detail

    def _fill_season(self, seasons: list, season_eps: dict, season_number: int, bangumiid: int, only_ova_episodes: bool = False):
        # 获取正确的季数
        detail = self.bangumiapi.detail(bangumiid)
        _season_numbers = re.findall("第([0-9]+)期", detail.get("name"))
        if _season_numbers:
            season_number = int(_season_numbers[0])
        if not season_number in seasons:
            seasons[season_number] = dict(detail)
            seasons[season_number].update({"season_number": season_number})
        # 填充正篇
        if not only_ova_episodes:
            eps = self.bangumiapi.episodes(bangumiid, 0)
            if eps.get('data'):
                if not str(season_number) in season_eps:
                    season_eps[str(season_number)] = []
                season_eps[str(season_number)].extend(eps.get('data'))
        # 填充OVA
        sps = self.bangumiapi.episodes(bangumiid, 1)
        if sps.get('data'):
            if not '0' in season_eps:
                season_eps['0'] = []
            season_eps['0'].extend(sps.get('data'))
            if only_ova_episodes:
                if not str(season_number) in season_eps:
                    season_eps[str(season_number)] = []
                season_eps[str(season_number)].extend(sps.get('data'))

        subjects = self.bangumiapi.subjects(bangumiid)
         # 如果有番外篇
        ova_season_details = list(filter(lambda s: (s.get('relation') == '番外篇' or s.get('relation') == '衍生') and not s.get("name_cn").startswith("剧场版"), subjects))
        if ova_season_details:
            if not '0' in season_eps:
                season_eps['0'] = []
            for ova_season_detail in ova_season_details:
                eps = self.bangumiapi.episodes(ova_season_detail.get('id'), 0)
                if len(eps.get('data')) < 10: #TODO: 怎么区分是小剧场还是番外
                    season_eps['0'].extend(eps.get('data'))
        # 如果有下一季
        next_season_details = list(filter(lambda s: s.get('relation') == '续集', subjects))
        if next_season_details:
            self._fill_season(seasons, season_eps, season_number + 1, next_season_details[0].get('id'), only_ova_episodes)

    def bangumi_calendar(self) -> Optional[List[MediaInfo]]:
        """
        获取Bangumi每日放送
        """
        infos = self.bangumiapi.calendar()
        if infos:
            return [MediaInfo(bangumi_info=info) for info in infos]
        return []

    def bangumi_credits(self, bangumiid: int) -> List[schemas.MediaPerson]:
        """
        根据TMDBID查询电影演职员表
        :param bangumiid:  BangumiID
        """
        persons = self.bangumiapi.credits(bangumiid)
        if persons:
            return [schemas.MediaPerson(source='bangumi', **person) for person in persons]
        return []

    def bangumi_recommend(self, bangumiid: int) -> List[MediaInfo]:
        """
        根据BangumiID查询推荐电影
        :param bangumiid:  BangumiID
        """
        subjects = self.bangumiapi.subjects(bangumiid)
        if subjects:
            return [MediaInfo(bangumi_info=subject) for subject in subjects]
        return []

    def bangumi_person_detail(self, person_id: int) -> Optional[schemas.MediaPerson]:
        """
        获取人物详细信息
        :param person_id:  豆瓣人物ID
        """
        personinfo = self.bangumiapi.person_detail(person_id)
        if personinfo:
            return schemas.MediaPerson(source='bangumi', **{
                "id": personinfo.get("id"),
                "name": personinfo.get("name"),
                "images": personinfo.get("images"),
                "biography": personinfo.get("summary"),
                "birthday": personinfo.get("birth_day"),
                "gender": personinfo.get("gender")
            })
        return None

    def bangumi_person_credits(self, person_id: int) -> List[MediaInfo]:
        """
        根据TMDBID查询人物参演作品
        :param person_id:  人物ID
        """
        credits_info = self.bangumiapi.person_credits(person_id=person_id)
        if credits_info:
            return [MediaInfo(bangumi_info=credit) for credit in credits_info]
        return []

    def bangumi_episodes(self, bangumiid: int, season: int) -> List[schemas.BangumiEpisode]:
        """
        根据Bangumi查询某季的所有信信息
        :param bangumiid:  bangumiid
        :param season:  季
        """
        eps = self.bangumi_info(bangumiid=bangumiid).get("_season_eps").get(str(season))
        if eps:
            return [{
                "air_date": ep.get("airdate"),
                "episode_number": ep.get("ep"),
                "name": ep.get("name_cn") or ep.get("name"),
                "overview": ep.get("desc"),
                "runtime": ep.get("duration"),
                "season_number": season,
                "still_path": None,
                "vote_average": None,
                "crew": None,
                "guest_stars": None
            } for ep in eps]
        return []
