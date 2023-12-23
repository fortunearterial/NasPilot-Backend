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
            cookies="list_mode=h; theme=auto; over18=1; _ym_uid=1702991513933832321; _ym_d=1702991513; locale=zh; _ym_isad=2; cf_clearance=jAPJ4YVONhXpDy8kBGWzmgFuDF8UJsXKu7o16PwhSSc-1703333277-0-2-25e5af4b.8dc226a.72e4f0ab-0.2.1703333277; _jdb_session=Zgwa%2BwPrhseWOrlggyh%2F0IW8raFY%2BGhrHwzLoj5UDVBg9H6Skzg0zHMAUj7P1et65KTKeg2nMeqfLTGq9GB77dvyEh%2BiUxGzdtlYVlhiFvTIFacqCV%2BonlveAYdlnGZP2bnynMYoivC03vF2GAn9hjMWUs87G6u49fa%2FhZnVU7rsVqKaRmHg%2FESPKSJD%2BYDyGdRX92rJf%2FT1qMergwkEOtNkpYYSUFeM%2BzBdAv%2BRdlbdcJSQbjv%2Fdp8WPURz%2BV7Xox1zyJEWcHYhtDNxBn3fei8fH5qjy764u6iMMI4vMY7JdNjUQ54cD2c3ss7FHyDIrEGEOYEaz2ifgZ%2BEY%2BXcC9hDxqn%2BAsf2wI%2BTcfnoizAXEgWsKRXgX9nALQnQDywclpu%2BcgSIObrVAFWB8%2FL%2BmhuB8fLNdiJ0ktG5HTfLwGKr5HfCW1lNGqlsQE16vQYaQVRMpkufihc8VpVa0Kae6dqw5fpj82ba8LoVg21y%2B2RABg%3D%3D--kjAX%2BBxOgxBRJIbY--HNc4TIZBuxbrVeQExlF2Kw%3D%3D",
            session=self._session,
            proxies=settings.PROXY
        ).get_res(url=req_url, params=params)
        if resp and resp.status_code == 400 and "rate_limit" in resp.text:
            return None
        return resp.text if resp else None

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
        if html is not None:
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
