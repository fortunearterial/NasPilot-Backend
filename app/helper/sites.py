import copy
import datetime
import json
import traceback
import re

from typing import List
from urllib.parse import urlencode, quote, urlparse, parse_qs

from jinja2 import Template
from pyquery import PyQuery
from ruamel.yaml import CommentedMap

from app.db.models.site import Site
from app.log import logger
from app.core.config import settings
from app.db.site_oper import SiteOper
from app.helper.browser import PlaywrightHelper
from app.schemas import MediaType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils

# noinspection PyUnresolvedReferences
from app.resources.sites import SitesHelper as SitesHelperBase, SiteSpider as SiteSpiderBase

from utils.singleton import Singleton


class SitesHelper(SitesHelperBase):
    _auth_level: int = 9

    def __init__(self):
        super().__init__()
        self.siteoper = SiteOper()

    @property
    def auth_level(self):
        return self._auth_level

    def _to_indexer(self, site: Site):
        url = site.url
        if url and not url.endswith("/"):
            url = url + "/"
        rss_path = site.rss
        if rss_path and rss_path.startswith("/"):
            rss_path = rss_path[1:]
        browse_path = site.browse
        if browse_path and browse_path.startswith("/"):
            browse_path = browse_path[1:]
        search_path = site.search
        if search_path and search_path.startswith("/"):
            search_path = search_path[1:]
        return {
            "id": site.id,
            "name": site.name,
            "domain": site.domain,
            "encoding": "UTF-8",
            "public": True,
            "proxy": site.proxy,
            "search": {
                "paths": [{"path": search_path, "method": site.search_method, "start": 1}],
                "params": {
                    "search": site.search_config.get("body"),
                } if site.search_method.upper() == 'HTTP_POST' else {},
            } if site.search_method else {},
            "batch": {"delimiter": " ", "space_replace": "_"},
            "browse": {
                "path": browse_path,
                "method": site.browse_method,
                "start": site.browse_config.get("start"),
            } if site.browse_method == 'HTTP_GET' else None,
            "category": {

            },
            "torrents": self.__get_torrents(site.browse_config),
            "browser_torrents": self.__get_torrents(site.browse_config),
            "search_torrents": self.__get_torrents(site.search_config),
            "url": url,
            "types": site.types,
            "pri": site.pri,
            "rss": url + rss_path,
            "cookie": site.cookie,
            "ua": site.ua,
            "apikey": site.apikey,
            "token": site.token,
            "filter": site.filter,
            "render": site.render,
            "note": site.note,
            "limit_interval": site.limit_interval,
            "limit_count": site.limit_count,
            "limit_seconds": site.limit_seconds,
            "timeout": site.timeout,
            "is_active": site.is_active,
            "lst_mod_date": site.lst_mod_date,
            "downloader": site.downloader,
            "result_num": 1000
        }

    def __get_torrents(self, config: dict):
        list_fields: dict = config.get("list_fields")
        torrent_fields: dict = config.get("torrent_fields")
        return {
            "torrent_in_detail": config.get("torrent_in_detail"),
            "list": json.loads(config.get("list")) if config.get("list") else {},
            "list_fields": {
                "title": json.loads(list_fields.get("title")) if list_fields.get("title") else {},
                "details": json.loads(list_fields.get("details")) if list_fields.get("details") else {},
            },
            "torrent": json.loads(config.get("torrent")),
            "torrent_fields": {
                "id": json.loads(torrent_fields.get("id")) if torrent_fields.get("id") else {},
                "title": json.loads(torrent_fields.get("title")) if torrent_fields.get("title") else {},
                "description": json.loads(torrent_fields.get("description")) if torrent_fields.get(
                    "description") else {},
                "details": json.loads(torrent_fields.get("details")) if torrent_fields.get("details") else {},
                "download": json.loads(torrent_fields.get("download")) if torrent_fields.get("download") else {},
                "grabs": json.loads(torrent_fields.get("grabs")) if torrent_fields.get("grabs") else {},
                "leechers": json.loads(torrent_fields.get("leechers")) if torrent_fields.get("leechers") else {},
                "seeders": json.loads(torrent_fields.get("seeders")) if torrent_fields.get("seeders") else {},
                "size": json.loads(torrent_fields.get("size")) if torrent_fields.get("size") else {},
                "imdbid": json.loads(torrent_fields.get("imdbid")) if torrent_fields.get("imdbid") else {},
                "downloadvolumefactor": json.loads(torrent_fields.get("downloadvolumefactor")) if torrent_fields.get(
                    "downloadvolumefactor") else {},
                "uploadvolumefactor": json.loads(torrent_fields.get("uploadvolumefactor")) if torrent_fields.get(
                    "uploadvolumefactor") else {},
                "date_added": json.loads(torrent_fields.get("date_added")) if torrent_fields.get(
                    "date_added") else {},
                "date_elapsed": json.loads(torrent_fields.get("date_elapsed")) if torrent_fields.get(
                    "date_elapsed") else {},
                "free_date": json.loads(torrent_fields.get("free_date")) if torrent_fields.get("free_date") else {},
                "labels": json.loads(torrent_fields.get("labels")) if torrent_fields.get("labels") else {},
                "hit_and_run": json.loads(torrent_fields.get("hit_and_run")) if torrent_fields.get(
                    "hit_and_run") else {},
                "category": json.loads(torrent_fields.get("category")) if torrent_fields.get("category") else {},
                "tags": json.loads(torrent_fields.get("tags")) if torrent_fields.get("tags") else {},
                "subject": json.loads(torrent_fields.get("subject")) if torrent_fields.get("subject") else {},
                "description_free_forever": json.loads(
                    torrent_fields.get("description_free_forever")) if torrent_fields.get(
                    "description_free_forever") else {},
                "description_normal": json.loads(torrent_fields.get("description_normal")) if torrent_fields.get(
                    "description_normal") else {},
            }
        }

    def get_indexer(self, domain: str = None, site: Site = None):
        default_indexer = super().get_indexer(domain)
        logger.debug(f"{domain} default indexer : {default_indexer}")
        if default_indexer:
            return default_indexer
        if not site:
            if domain:
                site = self.siteoper.get_by_domain(domain)
        custom_indexer = self._to_indexer(site)
        logger.debug(f"{domain} custom indexer : {custom_indexer}")
        if default_indexer:
            # 合并
            custom_indexer.update(default_indexer)
        logger.debug(f"{domain} final  indexer : {custom_indexer}")
        return custom_indexer

    def get_indexers(self):
        sites = self.siteoper.list_active()
        return [self.get_indexer(domain=site.domain, site=site) for site in sites]


class SiteSpider(SiteSpiderBase):
    # # 是否出现错误
    # is_error: bool = False
    # # 索引器ID
    # indexerid: int = None
    # # 索引器名称
    # indexername: str = None
    # # 站点地址
    # url: str = None
    # # 站点Cookie
    # cookie: str = None
    # # 站点UA
    # ua: str = None
    # # Requests 代理
    # proxies: dict = None
    # # playwright 代理
    # proxy_server: dict = None
    # # 是否渲染
    # render: bool = False
    # # cat
    # cat: str = None
    # # 搜索关键字
    # keyword: str = None
    # # 媒体类型
    # mtype: MediaType = None
    # # 搜索路径、方式配置
    # search: dict = {}
    # # 批量搜索配置
    # batch: dict = {}
    # # 浏览配置
    # browse: dict = {}
    # # 站点分类配置
    # category: dict = {}
    # 种子列表是否在列表详情页
    torrent_in_detail: bool = False
    # 站点列表配置
    list: dict = {}
    # 站点列表字段配置
    list_fields: dict = {}
    # 站点种子列表配置
    torrent: dict = {}
    # 站点种子字段配置
    torrent_fields: dict = {}

    # # 页码
    # page: int = 0
    # # 搜索条数, 默认: 100条
    # result_num: int = 100
    # # 单个种子信息
    # torrents_info: dict = {}
    # # 种子列表
    # torrents_info_array: list = []
    # # 搜索超时, 默认: 15秒
    # _timeout = 15
    # # 支持的媒体类型
    # types: list = []

    def __init__(self,
                 indexer: CommentedMap,
                 keyword: [str, list] = None,
                 page: int = 0,
                 cat: str = None,
                 mtype: MediaType = None):
        """
        设置查询参数
        :param indexer: 索引器
        :param keyword: 搜索关键字，如果数组则为批量搜索
        :param page: 页码
        :param cat: 类别
        :param mtype: 媒体类型
        """
        super().__init__(indexer=indexer,
                         keyword=keyword,
                         mtype=mtype,
                         cat=cat,
                         page=page)

        if not indexer:
            return
        self.keyword = keyword
        self.mtype = mtype
        self.indexerid = indexer.get('id')
        self.indexername = indexer.get('name')
        self.search = indexer.get('search')
        self.batch = indexer.get('batch')
        self.browse = indexer.get('browse')
        self.category = indexer.get('category')
        self.torrent_in_detail = indexer.get('search_torrents').get('torrent_in_detail') if keyword else indexer.get(
            'browser_torrents').get('torrent_in_detail')
        self.list = indexer.get('search_torrents').get('list', {}) if keyword else indexer.get(
            'browser_torrents').get('list', {})
        self.list_fields = indexer.get('search_torrents').get('list_fields') if keyword else indexer.get(
            'browser_torrents').get('list_fields')
        self.torrent = indexer.get('search_torrents').get('torrent', {}) if keyword else indexer.get(
            'browser_torrents').get('torrent', {})
        self.torrent_fields = indexer.get('search_torrents').get('torrent_fields') if keyword else indexer.get(
            'browser_torrents').get('torrent_fields')
        self.render = indexer.get('render')
        self.url = indexer.get('url')
        self.result_num = int(indexer.get('result_num') or 100)
        self._timeout = int(indexer.get('timeout') or 15)
        self.types = indexer.get('types')
        self.page = page
        if self.url and not str(self.url).endswith("/"):
            self.url = self.url + "/"
        if indexer.get('ua'):
            self.ua = indexer.get('ua') or settings.USER_AGENT
        else:
            self.ua = settings.USER_AGENT
        if indexer.get('proxy'):
            self.proxies = settings.PROXY
            self.proxy_server = settings.PROXY_SERVER
        if indexer.get('cookie'):
            self.cookie = indexer.get('cookie')
        if cat:
            self.cat = cat
        self.torrents_info_array = []

    def get_torrents(self) -> List[dict]:
        """
        开始请求
        """
        torrents_info_array = super().get_torrents()
        logger.debug(f"default method returns {json.dumps(torrents_info_array)}")
        if torrents_info_array:
            return torrents_info_array

        if (not self.browse and not self.search) or not self.url:
            return []

        logger.debug(f"开始爬取 {self.url} 的种子信息")
        # 种子搜索相对路径
        paths = self.search.get('paths', [])
        torrentspath = ""
        if len(paths) == 1:
            torrentspath = paths[0].get('path', '')
        else:
            for path in paths:
                if not self.types and not self.mtype:
                    torrentspath = path.get('path')
                    break
                elif MediaType.MOVIE.value in self.types and self.mtype == MediaType.MOVIE:
                    torrentspath = path.get('path')
                    break
                elif MediaType.TV.value in self.types and self.mtype == MediaType.TV:
                    torrentspath = path.get('path')
                    break

        # 精确搜索
        if self.keyword:
            if isinstance(self.keyword, list):
                # 批量查询
                if self.batch:
                    delimiter = self.batch.get('delimiter') or ' '
                    space_replace = self.batch.get('space_replace') or ' '
                    search_word = delimiter.join([str(k).replace(' ',
                                                                 space_replace) for k in self.keyword])
                else:
                    search_word = " ".join(self.keyword)
                # 查询模式：或
                search_mode = "1"
            else:
                # 单个查询
                search_word = self.keyword
                # 查询模式与
                search_mode = "0"

            # 搜索URL
            indexer_params = self.search.get("params", {}).copy()
            if indexer_params:
                search_area = indexer_params.get('search_area')
                # search_area非0表示支持imdbid搜索
                if (search_area and
                        (not self.keyword or not self.keyword.startswith('tt'))):
                    # 支持imdbid搜索，但关键字不是imdbid时，不启用imdbid搜索
                    indexer_params.pop('search_area')
                # 变量字典
                inputs_dict = {
                    "keyword": search_word
                }
                # 查询参数，默认查询标题
                params = {
                    "search_mode": search_mode,
                    "search_area": 0,
                    "page": self.page or 0,
                    "notnewword": 1
                }
                # 额外参数
                for key, value in indexer_params.items():
                    params.update({
                        "%s" % key: str(value).format(**inputs_dict)
                    })
                # 分类条件
                if self.category:
                    if self.mtype == MediaType.TV:
                        cats = self.category.get("tv") or []
                    elif self.mtype == MediaType.MOVIE:
                        cats = self.category.get("movie") or []
                    else:
                        cats = (self.category.get("movie") or []) + (self.category.get("tv") or [])
                    for cat in cats:
                        if self.category.get("field"):
                            value = params.get(self.category.get("field"), "")
                            params.update({
                                "%s" % self.category.get("field"): value + self.category.get("delimiter",
                                                                                             ' ') + cat.get("id")
                            })
                        else:
                            params.update({
                                "cat%s" % cat.get("id"): 1
                            })
                searchurl = self.url + torrentspath + "?" + urlencode(params)
            else:
                # 变量字典
                inputs_dict = {
                    "keyword": quote(search_word),
                    "page": self.page or 0
                }
                # 无额外参数
                searchurl = self.url + str(torrentspath).format(**inputs_dict)

        # 列表浏览
        else:
            # 变量字典
            inputs_dict = {
                "page": self.page or 0,
                "keyword": ""
            }
            # 有单独浏览路径
            if self.browse:
                torrentspath = self.browse.get("path")
                if self.browse.get("start"):
                    start_page = int(self.browse.get("start")) + int(self.page or 0)
                    inputs_dict.update({
                        "page": start_page
                    })
            elif self.page:
                torrentspath = torrentspath + f"?page={self.page}"
            # 搜索Url
            searchurl = self.url + str(torrentspath).format(**inputs_dict)

        page_source = self.get_pagesource(searchurl)
        # 解析
        return self.parse(page_source)

    def get_pagesource(self, searchurl: str):
        if self.render:
            logger.info(f"开始仿真请求：{searchurl}")
            # 浏览器仿真
            page_source = PlaywrightHelper().get_page_source(
                url=searchurl,
                cookies=self.cookie,
                ua=self.ua,
                proxies=self.proxy_server,
                timeout=self._timeout
            )
        else:
            logger.info(f"开始程序请求：{searchurl}")
            # requests请求
            ret = RequestUtils(
                ua=self.ua,
                cookies=self.cookie,
                timeout=self._timeout,
                referer=self.referer,
                proxies=self.proxies
            ).get_res(searchurl, allow_redirects=True)
            page_source = RequestUtils.get_decoded_html_content(ret,
                                                                settings.ENCODING_DETECTION_PERFORMANCE_MODE,
                                                                settings.ENCODING_DETECTION_MIN_CONFIDENCE)
        logger.debug(f"完成    请求：{searchurl}，结果{page_source}")
        return page_source

    def __get_title(self, torrent):
        logger.debug(f"开始解析种子的标题")
        # title default text
        if 'title' not in self.fields:
            logger.debug(f"完成解析种子的标题，跳过")
            return
        selector = self.fields.get('title', {})
        if 'selector' in selector:
            title = torrent(selector.get('selector', '')).clone()
            self.__remove(title, selector)
            items = self.__attribute_or_text(title, selector)
            self.torrents_info['title'] = self.__index(items, selector)
        elif 'text' in selector:
            render_dict = {}
            if "title_default" in self.fields:
                title_default_selector = self.fields.get('title_default', {})
                title_default_item = torrent(title_default_selector.get('selector', '')).clone()
                self.__remove(title_default_item, title_default_selector)
                items = self.__attribute_or_text(title_default_item, selector)
                title_default = self.__index(items, title_default_selector)
                render_dict.update({'title_default': title_default})
            if "title_optional" in self.fields:
                title_optional_selector = self.fields.get('title_optional', {})
                title_optional_item = torrent(title_optional_selector.get('selector', '')).clone()
                self.__remove(title_optional_item, title_optional_selector)
                items = self.__attribute_or_text(title_optional_item, title_optional_selector)
                title_optional = self.__index(items, title_optional_selector)
                render_dict.update({'title_optional': title_optional})
            self.torrents_info['title'] = Template(selector.get('text')).render(fields=render_dict)
        self.torrents_info['title'] = self.__filter_text(self.torrents_info.get('title'),
                                                         selector.get('filters'))
        logger.debug(f"完成解析种子的标题，结果：{self.torrents_info['title']}")

    def __get_description(self, torrent):
        logger.debug(f"开始解析种子的描述")
        # title optional text
        if 'description' not in self.fields:
            logger.debug(f"完成解析种子的描述，跳过")
            return
        selector = self.fields.get('description', {})
        if "selector" in selector \
                or "selectors" in selector:
            description = torrent(selector.get('selector', selector.get('selectors', ''))).clone()
            if description:
                self.__remove(description, selector)
                items = self.__attribute_or_text(description, selector)
                self.torrents_info['description'] = self.__index(items, selector)
        elif "text" in selector:
            render_dict = {}
            if "tags" in self.fields:
                tags_selector = self.fields.get('tags', {})
                tags_item = torrent(tags_selector.get('selector', '')).clone()
                self.__remove(tags_item, tags_selector)
                items = self.__attribute_or_text(tags_item, tags_selector)
                tag = self.__index(items, tags_selector)
                render_dict.update({'tags': tag})
            if "subject" in self.fields:
                subject_selector = self.fields.get('subject', {})
                subject_item = torrent(subject_selector.get('selector', '')).clone()
                self.__remove(subject_item, subject_selector)
                items = self.__attribute_or_text(subject_item, subject_selector)
                subject = self.__index(items, subject_selector)
                render_dict.update({'subject': subject})
            if "description_free_forever" in self.fields:
                description_free_forever_selector = self.fields.get("description_free_forever", {})
                description_free_forever_item = torrent(description_free_forever_selector.get("selector", '')).clone()
                self.__remove(description_free_forever_item, description_free_forever_selector)
                items = self.__attribute_or_text(description_free_forever_item, description_free_forever_selector)
                description_free_forever = self.__index(items, description_free_forever_selector)
                render_dict.update({"description_free_forever": description_free_forever})
            if "description_normal" in self.fields:
                description_normal_selector = self.fields.get("description_normal", {})
                description_normal_item = torrent(description_normal_selector.get("selector", '')).clone()
                self.__remove(description_normal_item, description_normal_selector)
                items = self.__attribute_or_text(description_normal_item, description_normal_selector)
                description_normal = self.__index(items, description_normal_selector)
                render_dict.update({"description_normal": description_normal})
            self.torrents_info['description'] = Template(selector.get('text')).render(fields=render_dict)
        self.torrents_info['description'] = self.__filter_text(self.torrents_info.get('description'),
                                                               selector.get('filters'))
        logger.debug(f"完成解析种子的描述，结果：{self.torrents_info['description']}")

    def __get_detail(self, torrent):
        logger.debug(f"开始解析种子的详情页地址")
        # details page text
        if 'details' not in self.fields:
            logger.debug(f"结束解析种子的详情页地址，跳过")
            return
        selector = self.fields.get('details', {})
        details = torrent(selector.get('selector', '')).clone()
        self.__remove(details, selector)
        items = self.__attribute_or_text(details, selector)
        item = self.__index(items, selector)
        detail_link = self.__filter_text(item, selector.get('filters'))
        if detail_link:
            if not detail_link.startswith("http"):
                if detail_link.startswith("//"):
                    self.torrents_info['page_url'] = self.url.split(":")[0] + ":" + detail_link
                elif detail_link.startswith("/"):
                    self.torrents_info['page_url'] = self.url + detail_link[1:]
                else:
                    self.torrents_info['page_url'] = self.url + detail_link
            else:
                self.torrents_info['page_url'] = detail_link
        logger.debug(f"结束解析种子的详情页地址，结果：{self.torrents_info['page_url']}")

    def __get_download(self, torrent):
        # download link text
        logger.debug(f"开始解析种子的下载地址")
        if 'download' not in self.fields:
            logger.debug(f"完成解析种子的下载地址，跳过")
            return
        selector = self.fields.get('download', {})
        download = torrent(selector.get('selector', '')).clone()
        self.__remove(download, selector)
        items = self.__attribute_or_text(download, selector)
        item = self.__index(items, selector)
        download_link = self.__filter_text(item, selector.get('filters'))
        if download_link:
            if not download_link.startswith("http") \
                    and not download_link.startswith("magnet"):
                _scheme, _domain = StringUtils.get_url_netloc(self.domain)
                if _domain in download_link:
                    if download_link.startswith("/"):
                        self.torrents_info['enclosure'] = f"{_scheme}:{download_link}"
                    else:
                        self.torrents_info['enclosure'] = f"{_scheme}://{download_link}"
                else:
                    if download_link.startswith("/"):
                        self.torrents_info['enclosure'] = f"{self.url}{download_link[1:]}"
                    else:
                        self.torrents_info['enclosure'] = f"{self.url}{download_link}"
            else:
                self.torrents_info['enclosure'] = download_link
        self.torrents_info['enclosure'] = self.__filter_text(self.torrents_info['enclosure'],
                                                             selector.get('sp_filters'))
        logger.debug(f"完成解析种子的下载地址，结果：{self.torrents_info['enclosure']}")

    def __get_imdbid(self, torrent):
        logger.debug(f"开始解析种子的imdbid")
        # imdbid
        if "imdbid" not in self.fields:
            logger.debug(f"完成解析种子的imdbid，跳过")
            return
        selector = self.fields.get('imdbid', {})
        imdbid = torrent(selector.get('selector', '')).clone()
        self.__remove(imdbid, selector)
        items = self.__attribute_or_text(imdbid, selector)
        item = self.__index(items, selector)
        self.torrents_info['imdbid'] = item
        self.torrents_info['imdbid'] = self.__filter_text(self.torrents_info.get('imdbid'),
                                                          selector.get('filters'))
        logger.debug(f"完成解析种子的imdbid，结果：{self.torrents_info['imdbid']}")

    def __get_size(self, torrent):
        logger.debug(f"开始解析种子的大小")
        # torrent size int
        if 'size' not in self.fields:
            logger.debug(f"完成解析种子的大小，跳过")
            return
        selector = self.fields.get('size', {})
        size = torrent(selector.get('selector', selector.get("selectors", ''))).clone()
        self.__remove(size, selector)
        items = self.__attribute_or_text(size, selector)
        item = self.__index(items, selector)
        if item:
            size_val = item.replace("\n", "").strip()
            size_val = self.__filter_text(size_val,
                                          selector.get('filters'))
            self.torrents_info['size'] = StringUtils.num_filesize(size_val)
        else:
            self.torrents_info['size'] = 0
        logger.debug(f"完成解析种子的大小，结果{self.torrents_info['size']}")

    def __get_leechers(self, torrent):
        logger.debug(f"开始解析种子的下载中数量")
        # torrent leechers int
        if 'leechers' not in self.fields:
            logger.debug(f"完成解析种子的下载中数量，跳过")
            return
        selector = self.fields.get('leechers', {})
        leechers = torrent(selector.get('selector', '')).clone()
        self.__remove(leechers, selector)
        items = self.__attribute_or_text(leechers, selector)
        item = self.__index(items, selector)
        if item:
            peers_val = item.split("/")[0]
            peers_val = peers_val.replace(",", "")
            peers_val = self.__filter_text(peers_val,
                                           selector.get('filters'))
            self.torrents_info['peers'] = int(peers_val) if peers_val and peers_val.isdigit() else 0
        else:
            self.torrents_info['peers'] = 0
        logger.debug(f"完成解析种子的下载中数量，结果：{self.torrents_info['peers']}")

    def __get_seeders(self, torrent):
        logger.debug(f"开始解析种子的做种数量")
        # torrent leechers int
        if 'seeders' not in self.fields:
            logger.debug(f"完成解析种子的做种数量，跳过")
            return
        selector = self.fields.get('seeders', {})
        seeders = torrent(selector.get('selector', '')).clone()
        self.__remove(seeders, selector)
        items = self.__attribute_or_text(seeders, selector)
        item = self.__index(items, selector)
        if item:
            seeders_val = item.split("/")[0]
            seeders_val = seeders_val.replace(",", "")
            seeders_val = self.__filter_text(seeders_val,
                                             selector.get('filters'))
            self.torrents_info['seeders'] = int(seeders_val) if seeders_val and seeders_val.isdigit() else 0
        else:
            self.torrents_info['seeders'] = 0
        logger.debug(f"完成解析种子的做种数量，结果：{self.torrents_info['seeders']}")

    def __get_grabs(self, torrent):
        logger.debug(f"开始解析种子的grabs")
        # torrent grabs int
        if 'grabs' not in self.fields:
            logger.debug(f"完成解析种子的grabs，跳过")
            return
        selector = self.fields.get('grabs', {})
        grabs = torrent(selector.get('selector', '')).clone()
        self.__remove(grabs, selector)
        items = self.__attribute_or_text(grabs, selector)
        item = self.__index(items, selector)
        if item:
            grabs_val = item.split("/")[0]
            grabs_val = grabs_val.replace(",", "")
            grabs_val = self.__filter_text(grabs_val,
                                           selector.get('filters'))
            self.torrents_info['grabs'] = int(grabs_val) if grabs_val and grabs_val.isdigit() else 0
        else:
            self.torrents_info['grabs'] = 0
        logger.debug(f"完成解析种子的grabs，结果：{self.torrents_info['grabs']}")

    def __get_pubdate(self, torrent):
        logger.debug(f"开始解析种子的发布日期")
        # torrent pubdate yyyy-mm-dd hh:mm:ss
        if 'date_added' not in self.fields:
            logger.debug(f"完成解析种子的发布日期，跳过")
            return
        selector = self.fields.get('date_added', {})
        pubdate = torrent(selector.get('selector', '')).clone()
        self.__remove(pubdate, selector)
        items = self.__attribute_or_text(pubdate, selector)
        pubdate_str = self.__index(items, selector)
        if pubdate_str:
            pubdate_str = pubdate_str.replace('\n', ' ').strip()
        self.torrents_info['pubdate'] = self.__filter_text(pubdate_str,
                                                           selector.get('filters'))
        logger.debug(f"完成解析种子的发布日期，结果：{self.torrents_info['pubdate']}")

    def __get_date_elapsed(self, torrent):
        logger.debug(f"开始解析种子的发布日期（times ago）")
        # torrent data elaspsed text
        if 'date_elapsed' not in self.fields:
            logger.debug(f"完成解析种子的发布日期（times ago），跳过")
            return
        selector = self.fields.get('date_elapsed', {})
        date_elapsed = torrent(selector.get('selector', '')).clone()
        self.__remove(date_elapsed, selector)
        items = self.__attribute_or_text(date_elapsed, selector)
        self.torrents_info['date_elapsed'] = self.__index(items, selector)
        self.torrents_info['date_elapsed'] = self.__filter_text(self.torrents_info.get('date_elapsed'),
                                                                selector.get('filters'))
        logger.debug(f"完成解析种子的发布日期（times ago），结果：{self.torrents_info['date_elapsed']}")

    def __get_downloadvolumefactor(self, torrent):
        # downloadvolumefactor int
        selector = self.fields.get('downloadvolumefactor', {})
        if not selector:
            return
        self.torrents_info['downloadvolumefactor'] = 1
        if 'case' in selector:
            for downloadvolumefactorselector in list(selector.get('case', {}).keys()):
                downloadvolumefactor = torrent(downloadvolumefactorselector)
                if len(downloadvolumefactor) > 0:
                    self.torrents_info['downloadvolumefactor'] = selector.get('case', {}).get(
                        downloadvolumefactorselector)
                    break
        elif "selector" in selector:
            downloadvolume = torrent(selector.get('selector', '')).clone()
            self.__remove(downloadvolume, selector)
            items = self.__attribute_or_text(downloadvolume, selector)
            item = self.__index(items, selector)
            if item:
                downloadvolumefactor = re.search(r'(\d+\.?\d*)', item)
                if downloadvolumefactor:
                    self.torrents_info['downloadvolumefactor'] = int(downloadvolumefactor.group(1))

    def __get_uploadvolumefactor(self, torrent):
        # uploadvolumefactor int
        selector = self.fields.get('uploadvolumefactor', {})
        if not selector:
            return
        self.torrents_info['uploadvolumefactor'] = 1
        if 'case' in selector:
            for uploadvolumefactorselector in list(selector.get('case', {}).keys()):
                uploadvolumefactor = torrent(uploadvolumefactorselector)
                if len(uploadvolumefactor) > 0:
                    self.torrents_info['uploadvolumefactor'] = selector.get('case', {}).get(
                        uploadvolumefactorselector)
                    break
        elif "selector" in selector:
            uploadvolume = torrent(selector.get('selector', '')).clone()
            self.__remove(uploadvolume, selector)
            items = self.__attribute_or_text(uploadvolume, selector)
            item = self.__index(items, selector)
            if item:
                uploadvolumefactor = re.search(r'(\d+\.?\d*)', item)
                if uploadvolumefactor:
                    self.torrents_info['uploadvolumefactor'] = int(uploadvolumefactor.group(1))

    def __get_labels(self, torrent):
        logger.debug(f"开始解析种子的标签")
        # labels ['label1', 'label2']
        if 'labels' not in self.fields:
            logger.debug(f"完成解析种子的标签，跳过")
            return
        selector = self.fields.get('labels', {})
        labels = torrent(selector.get("selector", "")).clone()
        self.__remove(labels, selector)
        items = self.__attribute_or_text(labels, selector)
        if items:
            self.torrents_info['labels'] = [item for item in items if item]
        else:
            self.torrents_info['labels'] = []
        logger.debug(f"完成解析种子的标签，结果：{self.torrents_info['labels']}")

    def __get_free_date(self, torrent):
        logger.debug(f"开始解析种子的免费截止时间")
        # free date yyyy-mm-dd hh:mm:ss
        if 'freedate' not in self.fields:
            logger.debug(f"完成解析种子的免费截止时间，跳过")
            return
        selector = self.fields.get('freedate', {})
        freedate = torrent(selector.get('selector', '')).clone()
        self.__remove(freedate, selector)
        items = self.__attribute_or_text(freedate, selector)
        self.torrents_info['freedate'] = self.__index(items, selector)
        self.torrents_info['freedate'] = self.__filter_text(self.torrents_info.get('freedate'),
                                                            selector.get('filters'))
        logger.debug(f"完成解析种子的免费截止时间，结果：{self.torrents_info['freedate']}")

    def __get_hit_and_run(self, torrent):
        # hitandrun True/False
        if 'hr' not in self.fields:
            return
        selector = self.fields.get('hr', {})
        hit_and_run = torrent(selector.get('selector', ''))
        if hit_and_run:
            self.torrents_info['hit_and_run'] = True
        else:
            self.torrents_info['hit_and_run'] = False

    def __get_category(self, torrent):
        logger.debug(f"开始解析种子的分类")
        # category 电影/电视剧
        if 'category' not in self.fields:
            logger.debug(f"完成解析种子的分类，跳过")
            return
        selector = self.fields.get('category', {})
        category = torrent(selector.get('selector', '')).clone()
        self.__remove(category, selector)
        items = self.__attribute_or_text(category, selector)
        category_value = self.__index(items, selector)
        category_value = self.__filter_text(category_value,
                                            selector.get('filters'))
        if category_value and self.category:
            tv_cats = [str(cat.get("id")) for cat in self.category.get("tv") or []]
            movie_cats = [str(cat.get("id")) for cat in self.category.get("movie") or []]
            if category_value in tv_cats \
                    and category_value not in movie_cats:
                self.torrents_info['category'] = MediaType.TV.value
            elif category_value in movie_cats:
                self.torrents_info['category'] = MediaType.MOVIE.value
            else:
                self.torrents_info['category'] = MediaType.UNKNOWN.value
        else:
            self.torrents_info['category'] = MediaType.UNKNOWN.value
        logger.debug(f"完成解析种子的分类，结果：{self.torrents_info['category']}")

    def __get_id(self, torrent):
        logger.debug(f"开始解析种子的ID")
        # id
        if 'id' not in self.fields:
            logger.debug(f"完成解析种子的ID，跳过")
            return
        selector = self.fields.get('id', {})
        id = torrent(selector.get('selector', '')).clone()
        self.__remove(id, selector)
        items = self.__attribute_or_text(id, selector)
        self.torrents_info['id'] = self.__index(items, selector)
        self.torrents_info['id'] = self.__filter_text(self.torrents_info.get('id'),
                                                      selector.get('filters'))
        logger.debug(f"完成解析种子的ID，结果：{self.torrents_info['id']}")

    def get_info(self, torrent) -> dict:
        """
        解析单条种子数据
        """
        logger.debug(f"开始解析种子")
        self.torrents_info = {}
        try:
            # ID
            self.__get_id(torrent)
            # 标题
            self.__get_title(torrent)
            # 描述
            self.__get_description(torrent)
            # 详情页面
            self.__get_detail(torrent)
            # 下载链接
            self.__get_download(torrent)
            # 完成数
            self.__get_grabs(torrent)
            # 下载数
            self.__get_leechers(torrent)
            # 做种数
            self.__get_seeders(torrent)
            # 大小
            self.__get_size(torrent)
            # IMDBID
            self.__get_imdbid(torrent)
            # 下载系数
            self.__get_downloadvolumefactor(torrent)
            # 上传系数
            self.__get_uploadvolumefactor(torrent)
            # 发布时间
            self.__get_pubdate(torrent)
            # 已发布时间
            self.__get_date_elapsed(torrent)
            # 免费载止时间
            self.__get_free_date(torrent)
            # 标签
            self.__get_labels(torrent)
            # HR
            self.__get_hit_and_run(torrent)
            # 分类
            self.__get_category(torrent)

        except Exception as err:
            logger.error("%s 搜索出现错误：%s" % (self.indexername, str(err)))
        logger.debug(f"完成解析种子，结果：{self.torrents_info}")
        return self.torrents_info

    @staticmethod
    def __filter_text(text: str, filters: list):
        """
        对文件进行处理
        """
        if not text or not filters or not isinstance(filters, list):
            return text
        if not isinstance(text, str):
            text = str(text)
        for filter_item in filters:
            if not text:
                break
            method_name = filter_item.get("name")
            try:
                args = filter_item.get("args")
                if method_name == "re_search" and isinstance(args, list):
                    rematch = re.search(r"%s" % args[0], text)
                    if rematch:
                        text = rematch.group(args[-1])
                elif method_name == "split" and isinstance(args, list):
                    text = text.split(r"%s" % args[0])[args[-1]]
                elif method_name == "replace" and isinstance(args, list):
                    text = text.replace(r"%s" % args[0], r"%s" % args[-1])
                elif method_name == "dateparse" and isinstance(args, str):
                    text = text.replace("\n", " ").strip()
                    text = datetime.datetime.strptime(text, r"%s" % args)
                elif method_name == "strip":
                    text = text.strip(r"%s" % args)
                elif method_name == "appendleft":
                    text = f"{args}{text}"
                elif method_name == "querystring":
                    parsed_url = urlparse(str(text))
                    query_params = parse_qs(parsed_url.query)
                    param_value = query_params.get(args)
                    text = param_value[0] if param_value else ''
                elif method_name == "detailparse":
                    text = f"@:【{json.dumps(args)}】【{text}】"
            except Exception as err:
                logger.debug(f'过滤器 {method_name} 处理失败：{str(err)} - {traceback.format_exc()}')
        return text.strip()

    @staticmethod
    def __remove(item, selector):
        """
        移除元素
        """
        if selector and "remove" in selector:
            removelist = selector.get('remove', '').split(', ')
            for v in removelist:
                item.remove(v)

    @staticmethod
    def __attribute_or_text(item, selector: dict):
        if not selector:
            return item
        if not item:
            return []
        if 'attribute' in selector:
            items = [i.attr(selector.get('attribute')) for i in item.items() if i]
        else:
            items = [i.text() for i in item.items() if i]
        return items

    @staticmethod
    def __index(items: list, selector: dict):
        if not items:
            return None
        if selector:
            if "contents" in selector \
                    and len(items) > int(selector.get("contents")):
                items = items[0].split("\n")[selector.get("contents")]
            elif "index" in selector \
                    and len(items) > int(selector.get("index")):
                items = items[int(selector.get("index"))]
        if isinstance(items, list):
            items = items[0]
        return items

    def parse(self, html_text: str) -> List[dict]:
        """
        解析列表页面
        """
        if not html_text:
            self.is_error = True
            return []
        # 清空旧结果
        self.torrents_info_array = []

        try:
            if self.torrent_in_detail:
                # 解析站点文本对象
                html_doc = PyQuery(html_text)
                # 种子筛选器
                lists_selector = self.list.get('selector', '')
                # 遍历列表html列表
                for torn in html_doc(lists_selector):
                    self.fields = self.list_fields
                    detail_info = self.get_info(PyQuery(torn))
                    if detail_info.get('title') in self.keyword:
                        detail_html_text = self.get_pagesource(detail_info.get('page_url'))
                        self._parse(detail_html_text)
                        if len(self.torrents_info_array) >= int(self.result_num):
                            break
            else:
                self._parse(html_text)
            return self.torrents_info_array
        except Exception as err:
            self.is_error = True
            logger.warn(f"错误：{self.indexername} {str(err)}")

    def _parse(self, html_text: str) -> List[dict]:
        """
        解析种子列表页面
        """
        if not html_text:
            return []
        self.fields = self.torrent_fields
        # 解析站点文本对象
        html_doc = PyQuery(html_text)
        # 种子筛选器
        torrents_selector = self.torrent.get('selector', '')
        # 遍历种子html列表
        for torn in html_doc(torrents_selector):
            if len(self.torrents_info_array) >= int(self.result_num):
                break
            self.torrents_info_array.append(copy.deepcopy(self.get_info(PyQuery(torn))))


class PageSpider(metaclass=Singleton):
    # 站点地址
    url: str = None
    # 站点Cookie
    cookie: str = None
    # 站点UA
    ua: str = None
    # Requests 代理
    proxies: dict = None
    # playwright 代理
    proxy_server: dict = None
    # 是否渲染
    render: bool = False
    # 搜索超时, 默认: 15秒
    _timeout: int = 15
    # Requests Referer头
    referer: str = None

    def __init__(self, **kwargs):
        properties = self.__get_properties()
        for key, value in kwargs.items():
            if key in properties:
                continue
            setattr(self, key, value)

    def parse(self, selector: dict) -> str:
        html_text = self.__get_sourcecode()
        try:
            # 解析站点文本对象
            html_doc = PyQuery(html_text)
            result = html_doc(selector.get('selector', '')).clone()
            items = self.__attribute_or_text(result, selector)
            item = self.__index(items, selector)
            return item
        except Exception as err:
            logger.warn(f"错误：{self.url} {str(err)}")

    def __get_properties(self):
        """
        获取属性列表
        """
        property_names = []
        for member_name in dir(self.__class__):
            member = getattr(self.__class__, member_name)
            if isinstance(member, property):
                property_names.append(member_name)
        return property_names

    def __get_sourcecode(self):
        if self.render:
            logger.info(f"开始仿真请求：{self.url}")
            # 浏览器仿真
            page_source = PlaywrightHelper().get_page_source(
                url=self.url,
                cookies=self.cookie,
                ua=self.ua,
                proxies=self.proxy_server,
                timeout=self._timeout
            )
        else:
            logger.info(f"开始程序请求：{self.url}")
            # requests请求
            ret = RequestUtils(
                ua=self.ua,
                cookies=self.cookie,
                timeout=self._timeout,
                referer=self.referer,
                proxies=self.proxies
            ).get_res(self.url, allow_redirects=True)
            page_source = RequestUtils.get_decoded_html_content(ret,
                                                                settings.ENCODING_DETECTION_PERFORMANCE_MODE,
                                                                settings.ENCODING_DETECTION_MIN_CONFIDENCE)
        logger.debug(f"完成    请求：{self.url}，结果{page_source}")
        return page_source

    @staticmethod
    def __remove(item, selector):
        """
        移除元素
        """
        if selector and "remove" in selector:
            removelist = selector.get('remove', '').split(', ')
            for v in removelist:
                item.remove(v)

    @staticmethod
    def __attribute_or_text(item, selector):
        if not selector:
            return item
        if not item:
            return []
        if 'attribute' in selector:
            items = [i.attr(selector.get('attribute')) for i in item.items() if i]
        else:
            items = [i.text() for i in item.items() if i]
        return items

    @staticmethod
    def __index(items, selector):
        if not items:
            return None
        if selector:
            if "contents" in selector \
                    and len(items) > int(selector.get("contents")):
                items = items[0].split("\n")[selector.get("contents")]
            elif "index" in selector \
                    and len(items) > int(selector.get("index")):
                items = items[int(selector.get("index"))]
        if isinstance(items, list):
            items = items[0]
        return items
