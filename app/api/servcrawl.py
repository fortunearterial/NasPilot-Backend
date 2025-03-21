from typing import Any, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json
from pyquery import PyQuery

from app.utils.http import RequestUtils
from app.helper.sites import SitesHelper, SiteSpider
from app.utils.string import StringUtils
from app.core.config import settings
from log import logger

crawl_router = APIRouter(tags=['servcrawl'])


@crawl_router.get("/page", summary="页面爬虫", response_class=PlainTextResponse)
def crawl_page(url: str, query: str) -> Any:
    """
    页面爬虫
    """
    selector = json.loads(query)
    domain = StringUtils.get_url_domain(url)
    indexer = SitesHelper().get_indexer(domain=domain)

    _spider = SiteSpider(indexer=indexer)
    html_text = _spider.get_pagesource(url)
    try:
        # 解析站点文本对象
        html_doc = PyQuery(html_text)
        result = html_doc(selector.get('selector', '')).clone()
        items = __attribute_or_text(result, selector)
        item = __index(items, selector)
        return item
    except Exception as err:
        logger.warn(f"错误：{url} {str(err)}")


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