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


class SteamApi(metaclass=Singleton):
    _urls = {
        # 搜索类
        # /search/results/?query&term=search_word&start: int=0&count: int=50&force_infinite=1&ndl=1&infinite=1
        # 聚合搜索
        "search": "/search/results/?query&l=schinese&force_infinite=1&ndl=1&infinite=1",
        "steamid": "/app/%s",

        # game info
        "game_detail": "/appdetails"
    }

    _api_key = "8D94856F0FFFF54024B33B66F0C7143F"
    _base_url = "https://store.steampowered.com"
    _api_url = "https://store.steampowered.com/api"
    _session = None

    def __init__(self):
        self._session = requests.Session()

    @lru_cache(maxsize=settings.CACHE_CONF.get('steam'))
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
            session=self._session,
            proxies=settings.PROXY
        ).get_res(url=req_url, params=params)
        if resp and resp.status_code == 400 and "rate_limit" in resp.text:
            return resp.json()
        return resp.json() if resp else {}

    @lru_cache(maxsize=settings.CACHE_CONF.get('steam'))
    def __get(self, url: str, **kwargs) -> dict:
        """
        GET请求
        """
        req_url = self._api_url + url

        params = {}
        if kwargs:
            params.update(kwargs)

        ts = params.pop(
            '_ts',
            datetime.strftime(datetime.now(), '%Y%m%d')
        )
        params.update({
            'key': self._api_key,
            '_ts': ts
        })
        resp = RequestUtils(
            session=self._session,
            proxies=settings.PROXY
        ).get_res(url=req_url, params=params)
        if resp and resp.status_code == 400 and "rate_limit" in resp.text:
            return resp.json()
        return resp.json() if resp else {}

    @lru_cache(maxsize=settings.CACHE_CONF.get('steam'))
    def __post(self, url: str, **kwargs) -> dict:
        """
        POST请求
        esponse = requests.post(
            url="https://store.steampowered.com/api/appdetails/?appids=1551360&l=english&key=",
        )
        """
        req_url = self._api_url + url
        params = {'apikey': self._api_key}
        if kwargs:
            params.update(kwargs)
        if '_ts' in params:
            params.pop('_ts')
        resp = RequestUtils(
            session=self._session,
            proxies=settings.PROXY
        ).post_res(url=req_url, data=params)
        if resp and resp.status_code == 400 and "rate_limit" in resp.text:
            return resp.json()
        return resp.json() if resp else {}

    def search(self, keyword: str, start: int = 0, count: int = 20,
               ts=datetime.strftime(datetime.now(), '%Y%m%d')) -> dict:
        """
        关键字搜索
        """
        search_results: List = []
        api_result = self.__invoke(self._urls["search"], term=keyword,
                             start=start, count=count, _ts=ts)

        html = etree.HTML(api_result.get("results_html"))
        if html:
            lists = html.xpath("//a[starts-with(@href, \"https://store.steampowered.com/app/\")]")
            for l in lists:
                href = l.xpath("./@href")[0]
                relative_href = href[len("https://store.steampowered.com/app/"):]
                steam_appid = relative_href[:relative_href.find("/")]
                header_image = l.xpath(".//img/@src")[0]
                name = l.xpath(".//span[@class=\"title\"]/text()")[0].strip()
                pub_data = l.xpath(".//div[contains(@class, \"search_released\")]/text()")[0].strip()
                search_results.append({
                    "steam_appid": steam_appid,
                    "name": name, 
                    "header_image": header_image,
                    "release_date": {
                        "date": pub_data
                    }
                })
        return search_results

    def game_detail(self, subject_id: str, lang: str = "schinese"):
        """
        游戏详情
        """
        return self.__get(self._urls["game_detail"], appids=subject_id, l=lang)

    def clear_cache(self):
        """
        清空LRU缓存
        """
        self.__invoke.cache_clear()

    def __del__(self):
        if self._session:
            self._session.close()
