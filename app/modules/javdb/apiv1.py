# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
from datetime import datetime
from functools import lru_cache
from random import choice
from urllib import parse
from lxml import etree

import requests

from app.core.config import settings
from app.utils.string import StringUtils
from app.utils.http import RequestUtils
from app.utils.singleton import Singleton
from app.modules.javdb.html_cache import HtmlCache


class JavDBApi(metaclass=Singleton):
    cache: HtmlCache = None

    _urls = {
        # 搜索类
        # /search?q=search_word&f=all
        # 聚合搜索
        "search": "/search?f=all",

        # Jav info
        "jav_detail": "/v/%s/corrections/new",
        # AV info
        "av_detail": "/%s"
    }

    _base_url = "https://javdb.com"
    _session = None

    def __init__(self):
        self._session = requests.Session()
        self.cache = HtmlCache()

    @lru_cache(maxsize=settings.CACHE_CONF.get('javdb'))
    def __invoke(self, url: str, **kwargs) -> dict:
        """
        GET请求
        """
        req_url = self._base_url + url

        params = {}
        if kwargs:
            params.update(kwargs)

        ts = params.pop(
            '_ts',
            datetime.strftime(datetime.now(), '%Y%m%d')
        )
        params.update({
            '_ts': ts
        })
        resp = RequestUtils(
            ua=settings.USER_AGENT,
            cookies="list_mode=h; theme=auto; over18=1; _ym_uid=1702991513933832321; _ym_d=1702991513; locale=zh; _rucaptcha_session_id=556f4fb93ef6bf28395bea9047a0a2ed; _ym_isad=2; cf_clearance=wt.rbDMfSR_U9FS5l1dZ206yoJvshbRhqBLobCGacEA-1703079310-0-1-25e5af4b.c512240d.72e4f0ab-0.2.1703079310; _jdb_session=SZ%2B0%2B%2F%2BOWeVHlB%2FUbd829rNj9WyohW%2FCK%2Bp6TFkpjnq0kctM5kFKL%2FKFP49CKmsZauTSWFkzytXhSM16N%2FHVZvua06xnUEnTzmW7VvO7I3daOm9xaolm0ReFEIdHkBx1Pd9oQgQVWChqQLoYeKlpMm%2BzFcHrxqSGLpA2QcsVdUHgY%2BCMI6d6T4kHE0nRpsulYQh17RObk9AlZsMyauYUZafkWpPZ1rjQ6RW%2BU8dQgs%2Fo2JdYaNeytUwg%2BHJsMhKtnROiNhCkADS5JxRlNpP3nVuoc%2FcvJXY02QXcdLp%2BVDrgE%2FV5XB11KrqjgPsps%2BOKC5ToXOoSx9kHMjeBjMvIFj6ScKPHShibP8lfPZVIVC3ob8EfrqkeJA1JDGFo%2BdOsYc7Iyd9pkqRyylWTz6y80DhNTm2tdNhn1cBk4iu0mhumZ4F19Cl%2FUFY%2Bdxkxvz47Cot7ffps6L0qhomJgvKz5Q4Aeq%2BIZ8VMztFarz7yzFHTIg%3D%3D--3pKo3yi61TsUMy82--ujy7RriGh2M7eZcKArRb7Q%3D%3D",
            session=self._session,
            proxies=settings.PROXY
        ).get_res(url=req_url, params=params)
        if resp and resp.status_code == 400 and "rate_limit" in resp.text:
            return resp.json()
        return resp.text if resp else {}

    def search(self, keyword: str, start: int = 0, count: int = 20,
               ts=datetime.strftime(datetime.now(), '%Y%m%d')) -> dict:
        """
        关键字搜索
        """
        search_results: List = []
        api_result = self.__invoke(self._urls["search"], q=keyword)

        html = etree.HTML(api_result)
        if html:
            videos = html.xpath("//div[contains(@class, 'movie-list')]/div[@class='item']/a")
            for video in videos:
                javdbid = video.xpath("./@href")[0][3:]
                name = video.xpath("./@title")[0].strip()
                javid = video.xpath("./div[@class='video-title']/strong/text()")[0].strip()
                pub_data = video.xpath("./div[@class='meta']/text()")[0].strip()
                header_image = video.xpath("./div[contains(@class, 'cover')]/img/@src")[0]
                tags = video.xpath("./div[contains(@class, 'tags')]/span/text()")
                search_results.append({
                    "javdbid": javdbid,
                    "name": f"{javid} {name}", 
                    "original_title": javid,
                    "header_image": header_image,
                    "status": any("磁鏈" in tag for tag in tags),
                    "release_date": pub_data
                })
        return search_results

    def jav_detail(self, subject_id: str):
        """
        Jav详情
        """
        url = self._urls["jav_detail"] % (subject_id)
        api_result = self.cache.get(url)
        if not api_result:
            api_result = self.__invoke(url)
            self.cache.update(url, api_result)
        html = etree.HTML(api_result)
        if html:
            title = html.xpath("//h2[contains(@class, 'title')]/strong/a/text()")[0].strip()
            header_image = html.xpath("//img[@class='video-cover']/@src")[0]

            form = html.xpath(f"//form[@action='/v/{subject_id}/corrections']")[0]
            javid = form.xpath(".//input[@id='movie_correction_number']/@value")[0].strip()
            release_date = form.xpath(".//input[@id='movie_correction_release_date']/@value")[0].strip()
            duration = form.xpath(".//input[@id='movie_correction_duration']/@value")[0].strip()

            director = form.xpath(".//select[@id='movie_correction_director_id']")[0]
            director_ids = director.xpath("./option/@value")
            director_names = director.xpath("./option/text()")
            directors = [{"id": director_ids[i], "name": director_names[i], "job": "导演"}for i in range(len(director_ids))]

            maker = form.xpath(".//select[@id='movie_correction_maker_id']")[0]
            maker_ids = maker.xpath("./option/@value")
            maker_names = maker.xpath("./option/text()")
            makers = [{"id": maker_ids[i], "name": maker_names[i]}for i in range(len(maker_ids))]

            publisher = form.xpath(".//select[@id='movie_correction_publisher_id']")[0]
            publisher_ids = publisher.xpath("./option/@value")
            publisher_names = publisher.xpath("./option/text()")
            publishers = [{"id": publisher_ids[i], "name": publisher_names[i]}for i in range(len(publisher_ids))]

            serie = form.xpath(".//select[@id='movie_correction_series_id']")[0]
            serie_ids = serie.xpath("./option/@value")
            serie_names = serie.xpath("./option/text()")
            series = [{"id": serie_ids[i], "name": serie_names[i]}for i in range(len(serie_ids))]

            tags = form.xpath(".//select[@id='movie_correction_tag_ids']/option/text()")

            actor = form.xpath(".//select[@id='movie_correction_actor_ids']")[0]
            actor_ids = actor.xpath("./option/@value")
            actor_names = actor.xpath("./option/text()")
            actors = [{"id": actor_ids[i], "name": actor_names[i][:-1], "gender": 1 if actor_names[i][-1:] == "♀" else 2}for i in range(len(actor_ids))]
            
            return {
                "javdbid": subject_id,
                "name": title, 
                "original_title": javid,
                "header_image": header_image,
                # "status": any("磁鏈" in tag for tag in tags),
                "release_date": release_date,
                "duration": duration,
                "directors": directors,
                "makers": makers,
                "publishers": publishers,
                "series": series,
                "tags": tags,
                "actors": actors
            }

    def clear_cache(self):
        """
        清空LRU缓存
        """
        self.__invoke.cache_clear()

    def __del__(self):
        if self._session:
            self._session.close()
