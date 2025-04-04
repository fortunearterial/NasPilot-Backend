import copy
import datetime
import re
import traceback
from typing import List
from urllib.parse import quote, urlencode, urlparse, parse_qs

import chardet
from jinja2 import Template
from pyquery import PyQuery
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.helper.browser import PlaywrightHelper
from app.log import logger
from app.schemas.types import MediaType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils

import time
import random
import base64
import json
from app.helper.sitecategory import SiteCategoryHelper
from app.modules.indexer.spider import TorrentSpider


class DetailTorrentSpider(TorrentSpider):
    # 编码
    encoding: str = None
    # 链接字段配置
    feed_links: dict = {} # feed页面进行下钻获取
    search_links: dict = {} # search页面进行下钻获取
    list_links: dict = {} # list页面进行下钻获取
    # 单个链接信息
    link_path: str = None

    def __init__(self,
                 indexer: CommentedMap,
                 keyword: [str, list] = None,
                 page: int = 0,
                 referer: str = None,
                 mtype: MediaType = None):
        """
        设置查询参数
        :param indexer: 索引器
        :param keyword: 搜索关键字，如果数组则为批量搜索
        :param page: 页码
        :param referer: Referer
        :param mtype: 媒体类型
        """
        if not indexer:
            return
        super().__init__(indexer, keyword, page, referer, mtype)
        self.batch = self.search.get('batch')
        self.feed_links = indexer.get('torrents').get('feed_links')
        self.search_links = indexer.get('torrents').get('search_links')
        self.list_links = indexer.get('torrents').get('list_links')
        self.encoding = indexer.get('encoding')

    def _get_html(self, searchurl, method = 'get', params = None) -> str:
        logger.info(f"开始请求：{searchurl}")

        if self.render:
            # 浏览器仿真
            if method == 'get':
                page_source = PlaywrightHelper().get_page_source(
                    url=searchurl,
                    cookies=self.cookie,
                    ua=self.ua,
                    proxies=self.proxy_server
                )
            else:
                # TODO: post request
                page_source = PlaywrightHelper().get_page_source(
                    url=searchurl,
                    params=params,
                    cookies=self.cookie,
                    ua=self.ua,
                    proxies=self.proxy_server
                )
        else:
            # requests请求
            if method == 'get':
                ret = RequestUtils(
                    ua=self.ua,
                    cookies=self.cookie,
                    timeout=30,
                    referer=self.referer,
                    proxies=self.proxies
                ).get_res(searchurl, allow_redirects=True)
            else:
                ret = RequestUtils(
                    ua=self.ua,
                    cookies=self.cookie,
                    timeout=30,
                    referer=self.referer,
                    proxies=self.proxies
                ).post_res(searchurl, params=params, allow_redirects=True)
            if ret is not None:
                # 使用chardet检测字符编码
                raw_data = ret.content
                if raw_data:
                    # fix: 用指定的编码进行解码
                    if self.encoding:
                        page_source = raw_data.decode(self.encoding)
                    else:
                        try:
                            result = chardet.detect(raw_data)
                            encoding = result['encoding']
                            # 解码为字符串
                            page_source = raw_data.decode(encoding)
                        except Exception as e:
                            logger.debug(f"chardet解码失败：{str(e)}")
                            # 探测utf-8解码
                            if re.search(r"charset=\"?utf-8\"?", ret.text, re.IGNORECASE):
                                ret.encoding = "utf-8"
                            else:
                                ret.encoding = ret.apparent_encoding
                        page_source = ret.text
                else:
                    page_source = ret.text
            else:
                page_source = ""

        return page_source

    def get_torrents(self) -> List[dict]:
        """
        开始请求
        """
        if not self.search or not self.domain:
            return []

        # 种子搜索相对路径
        paths = self.search.get('paths', [])
        torrentspath = ""
        torrentsmethod = ""
        if len(paths) == 1:
            torrentspath = paths[0].get('path', '')
            torrentsmethod = paths[0].get('method', '')
        else:
            for path in paths:
                if path.get("type") == "all" and not self.mtype:
                    torrentspath = path.get('path')
                    torrentsmethod = path.get('method')
                    break
                elif path.get("type") == "movie" and self.mtype == MediaType.MOVIE:
                    torrentspath = path.get('path')
                    torrentsmethod = path.get('method')
                    break
                elif path.get("type") == "tv" and self.mtype == MediaType.TV:
                    torrentspath = path.get('path')
                    torrentsmethod = path.get('method')
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
            indexer_params = self.search.get("params") or {}
            params = indexer_params.get('search')
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
                params = params.format(**inputs_dict)
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
                searchurl = self.domain + str(torrentspath).format(**inputs_dict)
            else:
                # 变量字典
                inputs_dict = {
                    "keyword": quote(search_word),
                    "page": self.page or 0
                }
                # 无额外参数
                searchurl = self.domain + str(torrentspath).format(**inputs_dict)

            # 获取页面源代码
            page_source = self._get_html(searchurl, method = torrentsmethod, params = params)

            # 解析
            return self.parselinks(page_source, self.search_links)
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
            searchurl = self.domain + str(torrentspath).format(**inputs_dict)

            # 获取页面源代码
            page_source = self._get_html(searchurl)

            # 解析
            return self.parselinks(page_source, self.feed_links)
        

    def _get_links(self, torrent, sel):
        # links
        selector = {}
        selector.update(sel)
        selector["selector"] = "a"
        selector["attribute"] = "href"
        link = torrent(selector.get('selector', '')).clone()
        self._remove(link, selector)
        items = self._attribute_or_text(link, selector)
        item = self._index(items, selector)
        detail_link = self._filter_text(item, selector.get('filters'))
        if detail_link:
            if not detail_link.startswith("http"):
                if detail_link.startswith("//"):
                    detail_link = self.domain.split(":")[0] + ":" + detail_link
                elif detail_link.startswith("/"):
                    detail_link = self.domain + detail_link[1:]
                else:
                    detail_link = self.domain + detail_link

            self.link_path = detail_link
            page_source = self._get_html(detail_link)

            self.parse(page_source)

    def _get_detail(self, torrent):
        # details page text
        if 'details' not in self.fields:
            self.torrents_info['page_url'] = self.link_path
            return
        super()._get_detail(torrent)

    # def _get_download(self, torrent):
    #     # download link
    #     if 'download' not in self.fields:
    #         return
    #     selector = self.fields.get('download', {})
    #     download = torrent(selector.get('selector', '')).clone()
    #     self._remove(download, selector)
    #     items = self._attribute_or_text(download, selector)
    #     item = self._index(items, selector)
    #     download_link = self._filter_text(item, selector.get('filters'))
    #     if download_link:
    #         if not download_link.startswith("http") and not download_link.startswith("magnet") and not download_link.startswith("["):
    #             self.torrents_info['enclosure'] = self.domain + download_link[1:] if download_link.startswith("/") else self.domain + download_link
    #         else:
    #             self.torrents_info['enclosure'] = download_link

    def get_links(self, torrent, selector: dict) -> dict:
        """
        解析单条种子数据
        """
        self.link_path = None
        try:
            self._get_links(torrent, selector)
        except Exception as err:
            logger.error("%s 搜索出现错误：%s" % (self.indexername, str(err)))

        time.sleep(random.randint(1, 10))

    def parselinks(self, html_text: str, links: dict) -> List[dict]:
        """
        解析整个页面，进行下钻
        """
        if not html_text:
            self.is_error = True
            return []
        # 清空旧结果
        self.torrents_info_array = []
        try:
            # 解析站点文本对象
            html_doc = PyQuery(html_text)
            # 种子筛选器
            torrents_selector = links.get('selector', '')
            # 遍历种子html列表
            for torn in html_doc(torrents_selector):
                self.get_links(PyQuery(torn), links)
            return self.torrents_info_array
        except Exception as err:
            self.is_error = True
            logger.warn(f"错误：{self.indexername} {str(err)}")

    def parse(self, html_text: str) -> List[dict]:
        """
        解析整个页面，进行列表获取
        """
        if not html_text:
            self.is_error = True
            return []
        try:
            # 种子筛选器-列表型
            if self.lists:
                # 解析站点文本对象
                html_doc = PyQuery(html_text)
                torrents_selector = self.lists.get('selector', '')
                # 遍历种子html列表
                for torn in html_doc(torrents_selector):
                    self.torrents_info_array.append(copy.deepcopy(self.get_info(PyQuery(torn))))
                    if len(self.torrents_info_array) >= int(self.result_num):
                        break
                return self.torrents_info_array
            # 种子筛选器-列表下钻型
            if self.list_links:
                return self.parselinks(html_text, self.list_links)
            
        except Exception as err:
            self.is_error = True
            logger.warn(f"错误：{self.indexername} {str(err)}")

    @staticmethod
    def _filter_text(text: str, filters: list):
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
                    text = text.strip()
                elif method_name == "appendleft":
                    text = f"{args}{text}"
                elif method_name == "querystring":
                    parsed_url = urlparse(text)
                    query_params = parse_qs(parsed_url.query)
                    param_value = query_params.get(args)
                    text = param_value[0] if param_value else ''
                elif method_name == "crawl_page":
                    params = base64.b64encode(
                        json.dumps({
                            "method": "get",
                            "params": f"url={text}&query={json.dumps(args)}"
                        }).encode('utf-8')).decode('utf-8')
                    text = f"[{params}]{settings.APP_DOMAIN}/crawl/page"
            except Exception as err:
                logger.debug(f'过滤器 {method_name} 处理失败：{str(err)} - {traceback.format_exc()}')
        return text.strip()