# import json
# from .limiter import LimiterHelper
#
# from app.db.site_oper import SiteOper
# from app.db.models.site import Site
# from app.utils.singleton import Singleton
# from app.utils.string import StringUtils
#
# class SitesHelper(metaclass=Singleton):
#     _auth_level: int = 9
#     _auth_version: str = '1.0.3'
#     _indexer_version: str = '1.0.5'
#     _limiters = {}
#
#     def __init__(self):
#         super().__init__()
#         self.siteoper = SiteOper()
#
#     @property
#     def auth_level(self):
#         return self._auth_level
#
#     @property
#     def auth_version(self):
#         return self._auth_version
#
#     @property
#     def indexer_version(self):
#         return self._indexer_version
#
#     def _to_indexer(self, site: Site):
#         url = site.url
#         if url and not url.endswith("/"):
#             url = url + "/"
#         feed_path = site.feed.get("path")
#         if feed_path and feed_path.startswith("/"):
#             feed_path = feed_path[1:]
#         search_path = site.search.get("path")
#         if search_path and search_path.startswith("/"):
#             search_path = search_path[1:]
#         torrents = json.loads(site.xpath)
#         return {
#             "id": site.id,
#             "name": site.name,
#             "domain": site.url,
#             "encoding": "UTF-8",
#             "render": site.render,
#             "public": True,
#             "proxy": site.proxy,
#             "cookie": site.cookie,
#             "parser": "dSpider" if torrents.get("feed_links") else "",
#             "_support_types": site.types,
#             "_downloader": site.downloader,
#             "rss": url + feed_path if site.feed.get("method") == 'RSS' else None,
#             "search": {
#                 "paths": [{ "path": search_path, "method": site.search.get("method").lower() }],
#                 "params": {
#                     "search": site.search.get("body"),
#                 } if site.search.get("method").upper() == 'HTTP POST' else {},
#                 "batch": { "delimiter": " ", "space_replace": "_" }
#             } if search_path else None,
#             "browse": { "path": feed_path, "start": 1 } if site.feed.get("method") == 'GET' else None,
#             "ua": site.ua,
#             "torrents": torrents
#         }
#
#     def get_indexer(self, site: Site = None, domain: str = None):
#         if domain:
#             site = self.siteoper.get_by_domain(domain)
#         if not site:
#             return None
#         return self._to_indexer(site)
#
#     def get_indexers(self):
#         sites = self.siteoper.list_active()
#         return [self._to_indexer(site) for site in sites]
#
#     def check(self, url):
#         domain = StringUtils.get_url_domain(url)
#         if not self._limiters.get(domain):
#             site = self.siteoper.get_by_domain(domain)
#             if site.limit_count == 0:
#                 return False, ''
#             self._limiters[domain] = LimiterHelper(calls=site.limit_count, period=site.limit_interval, raise_on_limit=False)
#         return not self._limiters[domain].submit(), '超过限制'