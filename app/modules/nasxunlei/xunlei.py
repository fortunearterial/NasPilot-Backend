import js2py
import base64
import json
import requests

from types import SimpleNamespace
from app.utils.http import RequestUtils
from app.log import logger
from app.core.config import settings

class Xunlei:
    host = None
    common_header = {
        "Content-Type": "application/json; charset=UTF-8",
        "User-Agent": settings.USER_AGENT
    }
    __xunlei_get_token = None

    def check_server_now(self):
        resp = self._get(url="/webman/3rdparty/pan-xunlei-com/index.cgi/device/now", with_auth=False)
        return int(resp.get('now'))

    def info_watch(self):
        resp = self._post(
            url="/webman/3rdparty/pan-xunlei-com/index.cgi/device/info/watch",
            json_body={}
        )
        watch_info = SimpleNamespace()
        watch_info.target = resp.get("target")
        watch_info.client_version = resp.get("client_version")
        return watch_info

    def _get_torrents(self, filters):
        filters["type"] = {
            "in": "user#download-url,user#download"
        }
        resp = self._get(
            url="/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/tasks",
            params={
                "filters": json.dumps(filters),
                "space": self.info_watch().target,
            }
        )
        all_tasks = []
        if resp.get("tasks") is None:
            return all_tasks
        for task in resp.get("tasks"):
            task_param = task.get("params")

            task_info = SimpleNamespace()
            task_info.space = task.get("space")
            task_info.id = task.get("id")
            task_info.type = task.get("type")
            task_info.file_id = task.get("file_id")
            task_info.create_time = parser.parse(task.get("created_time")).timestamp()
            task_info.update_time = parser.parse(task.get("updated_time")).timestamp()
            task_info.name = task.get("name")
            task_info.file_size = int(task.get("file_size"))
            task_info.speed = int(task_param.get("speed"))
            task_info.percent_done = int(task.get("progress")) / 100
            match task.get("phase"):
                case "PHASE_TYPE_RUNNING":
                    task_info.status = NasXunlei_Status.PHASE_TYPE_RUNNING
                case "PHASE_TYPE_PAUSED":
                    task_info.status = NasXunlei_Status.PHASE_TYPE_PAUSED
                case "PHASE_TYPE_PENDING":
                    task_info.status = NasXunlei_Status.PHASE_TYPE_PENDING
                case "PHASE_TYPE_ERROR":
                    task_info.status = NasXunlei_Status.PHASE_TYPE_ERROR
                case "PHASE_TYPE_COMPLETE":
                    task_info.status = NasXunlei_Status.PHASE_TYPE_COMPLETE
            task_info.hashString = task_param.get("info_hash")
            task_info.download_dir = task_param.get("real_path")

            all_tasks.append(task_info)

        return all_tasks

    def get_torrents(self, ids=None, status=None):
        filter = {
            "type": {
                "in": "user#download-url,user#download"
            }
        }
        if ids is list:
            filter["id"] = {
                "in": ids.join(",")
            }
        elif ids is str:
            filter["id"] = {
                "in": ids
            }
        if status is not None and len(status) > 0:
            filter["phase"] = {
                "in": status.join(",")
            }
        return self._get_torrents(filters=filter)

    def get_complete_torrents(self, ids):
        filter = {}
        if ids is list:
            filter["id"] = {
                "in": ids.join(",")
            }
        elif ids is str:
            filter["id"] = {
                "in": ids
            }
        filter["phase"] = {
            "in": "PHASE_TYPE_COMPLETE"
        }
        return self._get_torrents(filters=filter)

    def get_downloading_torrents(self, ids):
        filter = {}
        if ids is list:
            filter["id"] = {
                "in": ids.join(",")
            }
        elif ids is str:
            filter["id"] = {
                "in": ids
            }
        filter["phase"] = {
            "in": "PHASE_TYPE_PENDING,PHASE_TYPE_RUNNING,PHASE_TYPE_PAUSED,PHASE_TYPE_ERROR"
        }
        return self._get_torrents(filters=filter)

    def add_torrent(self, content, download_dir):
        target = self.info_watch().target
        try:
            torrent_info = self._post(
                url="/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/resource/list",
                json_body={
                    "urls": content,
                }
            )
        except Exception as err:
            raise Exception("迅雷获取种子文件列表失败", err)
        path_id = self._get_path_id(target, download_dir)
        error = None
        for torrent_item in torrent_info.get("list").get("resources"):
            try:
                self._post(
                    url="/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/task",
                    json_body={
                        "type": "user#download-url",
                        "name": torrent_item.get("name"),
                        "file_name": torrent_item.get("file_name"),
                        "file_size": str(torrent_item.get("file_size") if torrent_item.get("file_size") is not None else 0),
                        "space": target,
                        "params": {
                            "target": target,
                            "url": torrent_item.get("meta").get("url"),
                            "total_file_count": str(torrent_item.get("file_count")),
                            "sub_file_index": self._get_file_index(torrent_item),
                            "file_id": "",
                            "parent_folder_id": path_id,
                        }
                    }
                )
            except Exception as err:
                error = Exception("迅雷提交任务失败", err)
        if error is not None:
            raise error

    def _get_path_id(self, space_id, path: str):
        try:
            parent_id = ""
            dir_list = path.split('/')
            while '' in dir_list:
                dir_list.remove('')
            cnt = 0
            while 1:
                if len(dir_list) == cnt:
                    return parent_id
                dirs = self._get(
                    url="/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/files",
                    params={
                        "filters": json.dumps({
                            "kind": {
                                "eq": "drive#folder"
                            }
                        }),
                        "space": space_id,
                        "parent_id": parent_id,
                        "limit": 200,
                    }
                )
                if parent_id == "":
                    parent_id = dirs['files'][0]['id']
                    continue

                exists = False
                if 'files' in dirs.keys():
                    for dir_now in dirs['files']:
                        if dir_now['name'] == dir_list[cnt]:
                            cnt += 1
                            exists = True
                            parent_id = dir_now['id']
                            break

                if exists:
                    continue

                parent_id = self._create_sub_path(space_id, dir_list[cnt], parent_id)
                if parent_id is None:
                    return None
                cnt += 1
        except Exception as err:
            raise Exception("获取目录 ID 失败", err)

    def _create_sub_path(self, space_id, dir_name: str, parent_id: str) -> TypeError:
        try:
            rep = self._post(
                url='/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/files',
                json_body={
                    "parent_id": parent_id,
                    "name": dir_name,
                    "space": space_id,
                    "kind": "drive#folder",
                }
            )
            return rep['file']['id']
        except Exception as err:
            raise Exception("创建目录失败", err)

    def _get_file_index(self, file_info) -> str:
        file_count = int(file_info['file_count'])
        if file_count == 1:
            return '--1,'
        return '0-' + str(file_count - 1)

    def get_files(self, tid):
        filters = None
        if tid is not None:
            filters = {
                "id": {
                    "in": tid
                }
            }
        task = self._get_torrents(filters=filters)
        if len(task) >= 1:
            task = task[0]
        else:
            raise Exception(f"No task id of {tid}")
        resp = self._get(
            url=f"{self.host}/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/files",
            params={
                "pan_auth": self._create_xunlei_token(),
                "parent_id": task.file_id
            }
        )
        files = resp.get("files")
        result = []
        for file in files:
            info = SimpleNamespace()
            info.id = file.get("id")
            info.name = file.get("name")
            info.size = int(file.get("size"))
            result.append(info)
        return result

    def get_download_dirs(self):
        resp = self._get(
            url="/webman/3rdparty/pan-xunlei-com/index.cgi/device/download_paths"
        )
        dirs = []
        for dir in resp:
            dirs.append(dir.get("RealPath"))
        return dirs

    def set_speed_limit(self, speed):
        self._post(
            url="/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/resource/list",
            json_body={
                "speed_limit": speed,
            }
        )

    def _set_task_status(self, ids, status):
        if ids is str:
            ids = [ids]
        torrents = self.get_torrents(ids=ids)
        has_failed_id = None
        for torrent in torrents:
            try:
                self._post(
                    url="/webman/3rdparty/pan-xunlei-com/index.cgi/method/patch/drive/v1/task",
                    json_body={
                        "id": torrent.id,
                        "space": torrent.space,
                        "type": torrent.type,
                        "set_params": {
                            "spec": json.dumps({
                                "phase": status
                            })
                        }
                    }
                )
            except Exception as err:
                has_failed_id = err
        if has_failed_id is not None:
            raise has_failed_id

    def start_torrents(self, ids):
        self._set_task_status(ids=ids, status="running")

    def stop_torrents(self, ids):
        self._set_task_status(ids=ids, status="pause")

    def delete_torrents(self, ids, delete_file):
        if delete_file:
            self._set_task_status(ids, "delete")
        else:
            target = self.info_watch().target
            url = f"/webman/3rdparty/pan-xunlei-com/index.cgi/method/delete/drive/v1/tasks?space={target}"
            if isinstance(ids, str):
                ids = [ids]
            for id in ids:
                url = f"{url}&task_ids={id}"
            self._post(url=url, json_body={})

    def _create_xunlei_token(self):
        token = self.__xunlei_get_token.GetXunLeiToken(self.check_server_now())
        return token

    def _post(self, url: str, json_body=None):
        xtoken = self._create_xunlei_token()
        headers = dict(**self.common_header)
        headers["pan-auth"] = xtoken
        url = f"{self.host}{url}{'?' if '?' not in url else '&'}pan_auth={xtoken}&device_space="
        url = url.replace("#", "%23")
        resp = RequestUtils(headers=headers).post(
            url=url,
            json=json_body,
        )
        return self._as_checked_json(resp)

    def _get(self, url, params=None, with_auth=True):
        if params is None:
            params = {}
        headers = dict(**self.common_header)
        if with_auth:
            xtoken = self._create_xunlei_token()
            params["pan_auth"] = xtoken
            headers["pan-auth"] = xtoken
        params["device_space"] = ""
        resp = RequestUtils(headers=headers).get(
            url=f"{self.host}{url}",
            params=params
        )
        return self._as_checked_json(resp)

    def _as_checked_json(self, result):
        if result is not None:
            try:
                if isinstance(result, requests.models.Response):
                    result = result.json()
                else:
                    result = json.loads(str(result))
            except Exception as err:
                if isinstance(result, requests.models.Response):
                    logger.debug(f"【NAS 迅雷】响应解析失败：{result.text}")
                else:
                    logger.debug(f"【NAS 迅雷】响应解析失败：{result}")
                raise Exception("响应 json 解析失败，请检查控制台输出日志。", err)
            if result.get("error_code") is not None and int(result.get("error_code")) != 0:
                if "permission_deny" in result.get('error'):
                    raise Exception("签名算法失效，请根据 README.md 中提示进行操作后再试。")
                else:
                    raise Exception(f"请求失败：{result.get('error')}")
        return result

    def __init__(self, host, port, username, password):
        self.host = host
        if self.host is not None and not str(self.host).startswith("http"):
            self.host = f"http://{self.host}"
        if str(port).isdigit():
            self.host = f"{self.host}:{port}"
        if username is not None and password is not None:
            self.common_header["Authorization"] = base64.b64encode(f"{username}:{password}".encode('utf-8'))
        # https://github.com/opennaslab/kubespider/blob/f55eab6a931d1851d5cbe2b6467d7dde96bffdef/.config/dependencies/xunlei_download_provider/get_token.js
        __xunlei_get_token_js_external = """
// 这部分代码不要动 -- start
iB = {
    exports: {}
},
lB = {
    exports: {}
};

var g$ = {
    utf8: {
        stringToBytes: function(e) {
            return g$.bin.stringToBytes(unescape(encodeURIComponent(e)))
        },
        bytesToString: function(e) {
            return decodeURIComponent(escape(g$.bin.bytesToString(e)))
        }
    },
    bin: {
        stringToBytes: function(e) {
            for (var t = [], n = 0; n < e.length; n++) t.push(e.charCodeAt(n) & 255);
            return t
        },
        bytesToString: function(e) {
            for (var t = [], n = 0; n < e.length; n++) t.push(String.fromCharCode(e[n]));
            return t.join("")
        }
    }
},
_N = g$;

var e = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
t = {
    rotl: function(n, r) {
        return n << r | n >>> 32 - r
    },
    rotr: function(n, r) {
        return n << 32 - r | n >>> r
    },
    endian: function(n) {
        if (n.constructor == Number) return t.rotl(n, 8) & 16711935 | t.rotl(n, 24) & 4278255360;
        for (var r = 0; r < n.length; r++) n[r] = t.endian(n[r]);
        return n
    },
    randomBytes: function(n) {
        for (var r = []; n > 0; n--) r.push(Math.floor(Math.random() * 256));
            return r
    },
    bytesToWords: function(n) {
        for (var r = [], o = 0, a = 0; o < n.length; o++, a += 8) r[a >>> 5] |= n[o] << 24 - a % 32;
            return r
    },
    wordsToBytes: function(n) {
        for (var r = [], o = 0; o < n.length * 32; o += 8) r.push(n[o >>> 5] >>> 24 - o % 32 & 255);
            return r
    },
    bytesToHex: function(n) {
        for (var r = [], o = 0; o < n.length; o++) r.push((n[o] >>> 4).toString(16)), r.push((n[o] & 15).toString(16));
            return r.join("")
    },
    hexToBytes: function(n) {
        for (var r = [], o = 0; o < n.length; o += 2) r.push(parseInt(n.substr(o, 2), 16));
            return r
    },
    bytesToBase64: function(n) {
        for (var r = [], o = 0; o < n.length; o += 3)
            for (var a = n[o] << 16 | n[o + 1] << 8 | n[o + 2], i = 0; i < 4; i++) o * 8 + i * 6 <= n.length * 8 ? r.push(e.charAt(a >>> 6 * (3 - i) & 63)) : r.push("=");
                return r.join("")
    },
    base64ToBytes: function(n) {
        n = n.replace(/[^A-Z0-9+\/]/ig, "");
        for (var r = [], o = 0, a = 0; o < n.length; a = ++o % 4) a != 0 && r.push((e.indexOf(n.charAt(o - 1)) & Math.pow(2, -2 * a + 8) - 1) << a * 2 | e.indexOf(n.charAt(o)) >>> 6 - a * 2);
            return r
    }
};
lB.exports = t

var L8e = function(e) {
    return e != null && (sB(e) || D8e(e) || !!e._isBuffer)
};

function sB(e) {
    return !!e.constructor && typeof e.constructor.isBuffer == "function" && e.constructor.isBuffer(e)
}

function D8e(e) {
    return typeof e.readFloatLE == "function" && typeof e.slice == "function" && sB(e.slice(0, 0))
}

function GetTokenInternal(a, i) {
    var e = lB.exports,
    t = _N.utf8,
    n = L8e,
    r = _N.bin,
    o = function(a, i) {
        a.constructor == String ? i && i.encoding === "binary" ? a = r.stringToBytes(a) : a = t.stringToBytes(a) : n(a) ? a = Array.prototype.slice.call(a, 0) : !Array.isArray(a) && a.constructor !== Uint8Array && (a = a.toString());
        for (var l = e.bytesToWords(a), u = a.length * 8, s = 1732584193, d = -271733879, f = -1732584194, h = 271733878, v = 0; v < l.length; v++) l[v] = (l[v] << 8 | l[v] >>> 24) & 16711935 | (l[v] << 24 | l[v] >>> 8) & 4278255360;
        l[u >>> 5] |= 128 << u % 32, l[(u + 64 >>> 9 << 4) + 14] = u;
        for (var g = o._ff, w = o._gg, y = o._hh, b = o._ii, v = 0; v < l.length; v += 16) {
            var $ = s,
                S = d,
                _ = f,
                k = h;
            s = g(s, d, f, h, l[v + 0], 7, -680876936), h = g(h, s, d, f, l[v + 1], 12, -389564586), f = g(f, h, s, d, l[v + 2], 17, 606105819), d = g(d, f, h, s, l[v + 3], 22, -1044525330), s = g(s, d, f, h, l[v + 4], 7, -176418897), h = g(h, s, d, f, l[v + 5], 12, 1200080426), f = g(f, h, s, d, l[v + 6], 17, -1473231341), d = g(d, f, h, s, l[v + 7], 22, -45705983), s = g(s, d, f, h, l[v + 8], 7, 1770035416), h = g(h, s, d, f, l[v + 9], 12, -1958414417), f = g(f, h, s, d, l[v + 10], 17, -42063), d = g(d, f, h, s, l[v + 11], 22, -1990404162), s = g(s, d, f, h, l[v + 12], 7, 1804603682), h = g(h, s, d, f, l[v + 13], 12, -40341101), f = g(f, h, s, d, l[v + 14], 17, -1502002290), d = g(d, f, h, s, l[v + 15], 22, 1236535329), s = w(s, d, f, h, l[v + 1], 5, -165796510), h = w(h, s, d, f, l[v + 6], 9, -1069501632), f = w(f, h, s, d, l[v + 11], 14, 643717713), d = w(d, f, h, s, l[v + 0], 20, -373897302), s = w(s, d, f, h, l[v + 5], 5, -701558691), h = w(h, s, d, f, l[v + 10], 9, 38016083), f = w(f, h, s, d, l[v + 15], 14, -660478335), d = w(d, f, h, s, l[v + 4], 20, -405537848), s = w(s, d, f, h, l[v + 9], 5, 568446438), h = w(h, s, d, f, l[v + 14], 9, -1019803690), f = w(f, h, s, d, l[v + 3], 14, -187363961), d = w(d, f, h, s, l[v + 8], 20, 1163531501), s = w(s, d, f, h, l[v + 13], 5, -1444681467), h = w(h, s, d, f, l[v + 2], 9, -51403784), f = w(f, h, s, d, l[v + 7], 14, 1735328473), d = w(d, f, h, s, l[v + 12], 20, -1926607734), s = y(s, d, f, h, l[v + 5], 4, -378558), h = y(h, s, d, f, l[v + 8], 11, -2022574463), f = y(f, h, s, d, l[v + 11], 16, 1839030562), d = y(d, f, h, s, l[v + 14], 23, -35309556), s = y(s, d, f, h, l[v + 1], 4, -1530992060), h = y(h, s, d, f, l[v + 4], 11, 1272893353), f = y(f, h, s, d, l[v + 7], 16, -155497632), d = y(d, f, h, s, l[v + 10], 23, -1094730640), s = y(s, d, f, h, l[v + 13], 4, 681279174), h = y(h, s, d, f, l[v + 0], 11, -358537222), f = y(f, h, s, d, l[v + 3], 16, -722521979), d = y(d, f, h, s, l[v + 6], 23, 76029189), s = y(s, d, f, h, l[v + 9], 4, -640364487), h = y(h, s, d, f, l[v + 12], 11, -421815835), f = y(f, h, s, d, l[v + 15], 16, 530742520), d = y(d, f, h, s, l[v + 2], 23, -995338651), s = b(s, d, f, h, l[v + 0], 6, -198630844), h = b(h, s, d, f, l[v + 7], 10, 1126891415), f = b(f, h, s, d, l[v + 14], 15, -1416354905), d = b(d, f, h, s, l[v + 5], 21, -57434055), s = b(s, d, f, h, l[v + 12], 6, 1700485571), h = b(h, s, d, f, l[v + 3], 10, -1894986606), f = b(f, h, s, d, l[v + 10], 15, -1051523), d = b(d, f, h, s, l[v + 1], 21, -2054922799), s = b(s, d, f, h, l[v + 8], 6, 1873313359), h = b(h, s, d, f, l[v + 15], 10, -30611744), f = b(f, h, s, d, l[v + 6], 15, -1560198380), d = b(d, f, h, s, l[v + 13], 21, 1309151649), s = b(s, d, f, h, l[v + 4], 6, -145523070), h = b(h, s, d, f, l[v + 11], 10, -1120210379), f = b(f, h, s, d, l[v + 2], 15, 718787259), d = b(d, f, h, s, l[v + 9], 21, -343485551), s = s + $ >>> 0, d = d + S >>> 0, f = f + _ >>> 0, h = h + k >>> 0
        }
        return e.endian([s, d, f, h])
    };
    o._ff = function(a, i, l, u, s, d, f) {
    var h = a + (i & l | ~i & u) + (s >>> 0) + f;
    return (h << d | h >>> 32 - d) + i
    }, o._gg = function(a, i, l, u, s, d, f) {
    var h = a + (i & u | l & ~u) + (s >>> 0) + f;
    return (h << d | h >>> 32 - d) + i
    }, o._hh = function(a, i, l, u, s, d, f) {
    var h = a + (i ^ l ^ u) + (s >>> 0) + f;
    return (h << d | h >>> 32 - d) + i
    }, o._ii = function(a, i, l, u, s, d, f) {
    var h = a + (l ^ (i | ~u)) + (s >>> 0) + f;
    return (h << d | h >>> 32 - d) + i
    }, o._blocksize = 16, o._digestsize = 16, iB.exports = function(a, i) {
    if (a == null) throw new Error("Illegal argument " + a);
    var l = e.wordsToBytes(o(a, i));
    return i && i.asBytes ? l : i && i.asString ? r.bytesToString(l) : e.bytesToHex(l)
    }

    return iB.exports(a, i)
}
// 这部分代码不要动 -- end

// 这部分代码根据手册修改 -- start
function GetXunLeiToken(e) {
    return cG(e)
}

var uKe = GetTokenInternal
// 这部分代码根据手册修改 -- end

// 这部分代码从迅雷网站js脚本中拷贝 -- start
function cKe() {
    return ""
}
function dKe() {
    return "nacaddofnljdnushaxonyumypznmulqnwtigzyrifhb"
}
function fKe() {
    return "nhhsihdomgbwscddvrytbqquoavtzdxokzrkfwkgmmgogxcaaqvjazuaiabkycizlzmelhnkhwrbhvxrwrcermnlfmyvtfdipjtkwbmjttfryjkfkelmdhkomppigbjahkwhsrfgrxocecgvmgtnfwptlbjchjxthkdhkxqvojdmvkktnawxzlkohuvitoxzjfixuesphcyicpayoisonahcjkvqmrptdgopfvnuyhunfleoywjpygjvzzmedalecqagnbnbqtamlsxodszfaeddyowuombmfauwfnkveufkzpvpkrlmzueaiesieaaojjhetnjkwvvzwupgmraoftqjusxihahdngnaephjiknvafsypegwhmbumxyssvhqkkooktzuvjlfonhovcgkcgakcwqiijtnqkdnvhkeqgysyaekihsqpkufhzygwnuihgpzgepkddfjwxevgvkuzqwpphpusbvnudumhcpfpeadrzsztddtgvcaqchkeunapzfrunnfuvcpnzjvyiyjy"
}
function pKe() {
    return "dcvlctigagoioixnlofenhxqmyuweghjfpcqzicxcyycejkmwajqciipvfeimzmsevpbuevedvcflbavizuhvghccvculroiubnjdvmqptupgglkrkngslehmnhgxtonelzuotjhomknzyjrpihytxxvfahekomraspqgtrxtattbrojbtnymqwpgswmkskyqstzkddcxxdfucudeonevbtwyohlfqrawnagqyhmgszjwkfioiqblgumgfsaloecebmzpvndkqsayfsnqsjpbcnpyymwscnpufphrdtgxfbaklluozfjkmnntqwmdlhinjzacydaszhuakmnffdabgpnbrqmwibwqdpavhutvosughwtspxhgfubledlasfforsjqshwzaoqftetwghuhnpvwuqtfnduzqcrntwpcinn"
}
function hKe() {
    return "rkstqjardbtwpjpprpqskvxcweajowugsycvxcnccpjqblkx"
}
function vKe() {
    return "dwesdgqjuvjchlwrgklykavgeiozqqagterhctphzruzgomyhcuajgwhwyjkzfofkswajxzienuokdspqwjhezulhumsywywvdrywopzimqzstfnrufuvkdmcrlujnxhsjiphsiftbeptpreulvekvhchspgjpkwafitimxwpicwrbghmcwtfphmjqhcbdaaprdigdhtqcrkiyrbufidtlxppuvqkwuqexsmuvkvmhjahbyvvczhcptpfslmwnujrylygwwbvlwxcdybvmflacejyjqguopgxsblqribrnxhzbjtphfsshrbpnysjuswiracsuxgczsgzckahevaoobujpbscjopxhwxmwxcjoyskpxmysdfyepsfcqoeklibnobnzbshpmvktnvmcwyzihbhyqcfxdjyzapjzcyxsqmlkhmhdzwsfnziuvvmfnbklkbcwpbkmqzbaxact"
}
function mKe() {
    return "winbdirfpkbyknjvbygilsojfiecisxaqctrcqayiuwkmqfszfqmqbzmgkecdzcvrzwfidgcykrswdoygwbuljuuykghtyihljmiilucbeigqsifrpfpjfxpwegdskucmpefwzvlptrbzfwdwqgwxvpsridysmzafyphubkxngicnqiprfqndgjrtociakkvnxhjgxiqrlsqypniuxvyqlobmafxetfzywovkjkjcga"
}
function gKe() {
    return "byuhqtnczevdqlfgjswvpxxlxajkngreqhhbkavsvgojvmarsuwqwrdtnkscdhoxgqixftqgifjyuurvcjqstlwupyzrygzneukifvpcdyyxpmgaalqiwbrhqj"
}
function yKe() {
    return "adhciysxxnslxewdmkdcify"
}
function bKe() {
    return "tluhetwqwop"
}
function _Ke() {
    return "atkra"
}
function wKe() {
    return "mjixakdsyjcjirwpcujtgokcfnexqdok"
}
function SKe() {
    return "wpeadnpxalghwehjvuxnzj"
}
function CKe() {
    return "mhgslzjciueibcxfjwpiw"
}
function EKe() {
    return "aoqfuq"
}
function kKe() {
    return "xla"
}
function $Ke() {
    return "aalwkrsplg"
}
function TKe() {
    return "blmbat"
}
function OKe() {
    return "okslxl"
}
function xKe() {
    return "pabe"
}
function cG(e) {
    return e + "." + uKe(e + cKe() + dKe() + fKe() + pKe() + hKe() + vKe() + mKe() + gKe() + yKe() + bKe() + _Ke() + wKe() + SKe() + CKe() + EKe() + kKe() + $Ke() + TKe() + OKe() + xKe())
}
// 这部分代码从迅雷网站js脚本中拷贝 -- end
"""
        context = js2py.EvalJs()
        context.execute(__xunlei_get_token_js_external)
        self.__xunlei_get_token = context


if __name__ == '__main__':
    xunlei = Xunlei('uat.synology.home.fortunearterial.top', 18443, '18627176816', 'ly2000281.')
    xunlei.check_server_now()