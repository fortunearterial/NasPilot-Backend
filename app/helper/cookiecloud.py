import json
from hashlib import md5
from typing import Any, Dict, Tuple, Optional

from app.core.config import settings
from app.utils.common import decrypt
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class CookieCloudHelper:
    _ignore_cookies: list = ["CookieAutoDeleteBrowsingDataCleanup", "CookieAutoDeleteCleaningDiscarded"]

    def __init__(self):
        self._sync_setting()
        self._req = RequestUtils(content_type="application/json")

    def _sync_setting(self):
        self._server = settings.COOKIECLOUD_HOST
        self._keys = settings.COOKIECLOUD_KEY
        self._passwords = settings.COOKIECLOUD_PASSWORD
        self._enable_local = settings.COOKIECLOUD_ENABLE_LOCAL
        self._local_path = settings.COOKIECLOUD_DATA_PATH

    def download(self) -> Tuple[Optional[dict], str]:
        """
        从CookieCloud下载数据
        :return: Cookie数据、错误信息
        """
        # 更新为最新设置
        self._sync_setting()

        if ((not self._server and not self._enable_local)
                or not self._keys
                or not self._passwords):
            return None, "CookieCloud参数不正确"

        if self._enable_local:
            # 开启本地服务时，从本地直接读取数据
            results = list(self._load_local_encrypt_data(self._keys))
            if not results:
                return {}, "未从本地CookieCloud服务加载到cookie数据，请检查服务器设置、用户KEY及加密密码是否正确"
        else:
            results = list(self._load_server_encrypt_data(self._keys))
            if not results:
                return {}, "CookieCloud请求失败，请检查服务器地址、用户KEY及加密密码是否正确"

        results = list(self._decrypted_data(results))
        if not results:
            return {}, "cookie解密为空"

        # 整理数据,使用domain域名的最后两级作为分组依据
        domain_groups = {}
        domain_updatetimes = {}
        for result in results:
            if result.get("cookie_data"):
                contents = result.get("cookie_data")
            else:
                contents = result

            for site, cookies in contents.items():
                for cookie in cookies:
                    domain_key = StringUtils.get_url_domain(cookie.get("domain"))
                    if not domain_updatetimes.get(domain_key):
                        domain_updatetimes[domain_key] = result.get("update_time")
                    else:
                        if result.get("update_time") > domain_updatetimes.get(domain_key):
                            domain_updatetimes[domain_key] = result.get("update_time")
                            domain_groups.pop(domain_key)

                    if not domain_groups.get(domain_key):
                        domain_groups[domain_key] = [cookie]
                    else:
                        domain_groups[domain_key].append(cookie)
        
        # 返回错误
        ret_cookies = {}
        # 索引器
        for domain, content_list in domain_groups.items():
            if not content_list:
                continue
            # 只有cf的cookie过滤掉
            cloudflare_cookie = True
            for content in content_list:
                if content["name"] != "cf_clearance":
                    cloudflare_cookie = False
                    break
            if cloudflare_cookie:
                continue
            # 站点Cookie
            cookie_str = ";".join(
                [f"{content.get('name')}={content.get('value')}"
                 for content in content_list
                 if content.get("name") and content.get("name") not in self._ignore_cookies]
            )
            ret_cookies[domain] = cookie_str
        return ret_cookies, ""

    def _get_crypt_key(self, key: str, password: str) -> bytes:
        """
        使用UUID和密码生成CookieCloud的加解密密钥
        """
        md5_generator = md5()
        md5_generator.update((key.strip() + '-' + password.strip()).encode('utf-8'))
        return (md5_generator.hexdigest()[:16]).encode('utf-8')

    def _load_local_encrypt_data(self, uuids: list) -> list[str]:
        for uuid in uuids:
            file_path = self._local_path / f"{uuid}.json"
            # 检查文件是否存在
            if file_path.exists():
                # 读取文件
                with open(file_path, encoding="utf-8", mode="r") as file:
                    read_content = file.read()
                data = json.loads(read_content.encode("utf-8"))
                yield data

    def _load_server_encrypt_data(self, uuids: list) -> list[str]:
        for uuid in uuids:
            req_url = "%s/get/%s" % (self._server, str(uuid).strip())
            ret = self._req.get_res(url=req_url)
            if ret and ret.status_code == 200:
                try:
                    result = ret.json()
                    result.update({
                        "key": uuid,
                        "password": self._passwords[self._keys.index(uuid)],
                    })
                    if not result:
                        print(f"未从{self._server}下载到用户KEY{uuid}cookie数据")
                    yield result
                except Exception as err:
                    print(f"从{self._server}下载用户KEY{uuid}cookie数据错误：{str(err)}")
            elif ret:
                print(f"远程同步CookieCloud用户KEY{uuid}失败，错误码：{ret.status_code}")
            else:
                print(f"CookieCloud请求用户KEY{uuid}失败，请检查服务器地址、用户KEY及加密密码是否正确")

    def _decrypted_data(self, results: list) -> list[str]:
        for result in results:
            encrypted = result.get("encrypted")
            if not encrypted:
                print("未获取到cookie密文")
            else:
                crypt_key = self._get_crypt_key(result.pop("key"), result.pop("password"))
                try:
                    decrypted_data = decrypt(encrypted, crypt_key).decode('utf-8')
                    yield json.loads(decrypted_data)
                except Exception as e:
                    print("cookie解密失败：" + str(e))