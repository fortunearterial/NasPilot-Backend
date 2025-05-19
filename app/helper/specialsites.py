import time
from datetime import datetime
from urllib import parse
from uuid import UUID

import oss2
import playwright.sync_api

from oss2.credentials import StaticCredentialsProvider

from app.utils.singleton import Singleton
from app.utils.string import StringUtils
from app.helper.sites import PageSpider


class SpecialSitesHelper(metaclass=Singleton):
    ACCESS_KEY_ID = "LTAI5t8v2Nqh7LhF1a4XM7oQ"
    ACCESS_KEY_SECRET = "qGRvy7tqcESCgYODUzsoHVMyFJqOe7"

    def btbtl_handler(self, url: str):
        auth = oss2.ProviderAuthV4(StaticCredentialsProvider(
            access_key_id=SpecialSitesHelper.ACCESS_KEY_ID,
            access_key_secret=SpecialSitesHelper.ACCESS_KEY_SECRET,
        ))
        bucket = oss2.Bucket(auth, "https://oss-cn-shanghai.aliyuncs.com", "naspliot-pub", region="cn-shanghai")  # noqa

        uri = parse.urlparse(url)
        object_id = f"btbtl.com{uri.path.replace('.html', '.torrent')}"
        if not bucket.object_exists(object_id):
            _spider = PageSpider(url=url)
            file_bytes = _spider.action(callback=self._btbtl_handler_callback)
            # 上传到OSS并返回地址
            result = bucket.put_object(object_id, file_bytes)
            if result.status != 200:
                raise Exception("上传到OSS失败")
        # 返回结果
        return f"https://naspliot-pub.oss-cn-shanghai.aliyuncs.com/{object_id}"

    def _btbtl_handler_callback(self, page: playwright.sync_api.Page):
        # 等待新页面打开事件
        with page.expect_popup() as download_page_info:
            # 点击内容为“下载种子文件”的 a 标签
            page.click("a:has-text('下载种子文件')", timeout=120000)
        # 获取新打开的页面对象
        download_page = download_page_info.value
        download_page.wait_for_load_state("networkidle")
        time.sleep(5)
        with download_page.expect_download() as download_info:
            download_page.click("a:has-text('点击下载')", timeout=3000)
        download_file = download_info.value.path()
        file_bytes = download_file.read_bytes()
        download_file.unlink(missing_ok=True)
        return file_bytes
