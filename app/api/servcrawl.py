from typing import Any, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json
from pyquery import PyQuery

from app import schemas
from app.chain.media import MediaChain
from app.chain.subscribe import SubscribeChain
from app.core.metainfo import MetaInfo
from app.core.security import verify_apikey
from app.db import get_db
from app.db.models.subscribe import Subscribe
from app.schemas import RadarrMovie, SonarrSeries
from app.schemas.types import MediaType
from app.utils.http import RequestUtils
from app.helper.sites import SitesHelper
from app.utils.string import StringUtils
from app.core.config import settings

crawl_router = APIRouter(tags=['servcrawl'])


@crawl_router.get("/page", summary="页面爬虫", response_class=PlainTextResponse)
def crawl_page(url: str, query: str) -> Any:
    """
    页面爬虫
    """
    selector = json.loads(query)
    domain = StringUtils.get_url_domain(url)
    indexer = SitesHelper().get_indexer(domain=domain)

    indexerid = indexer.get('id')
    indexername = indexer.get('name')
    browse = indexer.get('browse')
    category = indexer.get('category')
    render = indexer.get('render')
    domain = indexer.get('domain')
    encoding = indexer.get('encoding')

    ua = indexer.get('ua') or settings.USER_AGENT
    if indexer.get('proxy'):
        proxies = settings.PROXY
        proxy_server = settings.PROXY_SERVER
    else:
        proxies = None
    cookie = indexer.get('cookie')

    ret = RequestUtils(
                    ua=ua,
                    cookies=cookie,
                    timeout=30,
                    proxies=proxies
                ).get_res(url, allow_redirects=True)
    if ret is not None:
        # 使用chardet检测字符编码
        raw_data = ret.content
        if raw_data:
            # fix: 用指定的编码进行解码
            if encoding:
                page_source = raw_data.decode(encoding)
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

    if page_source:
        html_doc = PyQuery(page_source)
        el = html_doc(selector.get('selector', ''))
        items = __attribute_or_text(el, selector)
        item = __index(items, selector)
        return item
    
    return ""


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