import re
from pathlib import Path
from typing import List, Optional, Tuple, Union

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.steam.apiv1 import SteamApi
from app.modules.steam.steam_cache import SteamCache
from app.modules.steam.scraper import SteamScraper
from app.schemas.types import MediaType
from app.utils.common import retry
from app.utils.system import SystemUtils


class SteamModule(_ModuleBase):
    steamapi: SteamApi = None
    scraper: SteamScraper = None
    cache: SteamCache = None

    def init_module(self) -> None:
        self.steamapi = SteamApi()
        self.scraper = SteamScraper()
        self.cache = SteamCache()

    @staticmethod
    def get_name() -> str:
        return "Steam"

    def stop(self):
        self.cache.save()

    def test(self) -> Tuple[bool, str]:
        """
        测试模块连接性
        """
        return True, ""

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    def recognize_media(self, meta: MetaBase = None,
                        mtype: MediaType = None,
                        steamid: int = None,
                        **kwargs) -> Optional[MediaInfo]:
        """
        识别媒体信息
        :param meta:     识别的元数据
        :param mtype:    识别的媒体类型，与steamid配套
        :param steamid: STEAM ID
        :return: 识别的媒体信息，包括剧集信息
        """
        if settings.RECOGNIZE_SOURCE and not "steam" in settings.RECOGNIZE_SOURCE:
            return None

        if not meta:
            cache_info = {}
        else:
            if mtype:
                meta.type = mtype
            cache_info = self.cache.get(meta)
        if not cache_info:
            # 缓存没有或者强制不使用缓存
            if steamid:
                # 直接查询详情
                info = self.steam_info(steamid=steamid, mtype=mtype or meta.type)
            elif meta:
                logger.info(f"正在识别 {meta.name} ...")
                # 匹配STEAM信息
                match_info = self.match(name=meta.name,
                                                   mtype=mtype or meta.type,
                                                   year=meta.year)
                if match_info:
                    # 匹配到STEAM信息
                    info = self.steam_info(
                        steamid=match_info.get("steam_appid"),
                        mtype=mtype or meta.type
                    )
                else:
                    logger.info(f"{meta.name if meta else steamid} 未匹配到STEAM媒体信息")
                    return None
            else:
                logger.error("识别媒体信息时未提供元数据或STEAM ID")
                return None
            # 保存到缓存
            if meta:
                self.cache.update(meta, info)
        else:
            # 使用缓存信息
            if cache_info.get("title"):
                logger.info(f"{meta.name} 使用STEAM识别缓存：{cache_info.get('title')}")
                info = self.steam_info(mtype=cache_info.get("type"),
                                        steamid=cache_info.get("id"))
            else:
                logger.info(f"{meta.name} 使用STEAM识别缓存：无法识别")
                info = None

        if info:
            # 赋值STEAM信息并返回
            mediainfo = MediaInfo(steam_info=info)
            if meta:
                logger.info(f"{meta.name} STEAM识别结果：{mediainfo.type.value} "
                            f"{mediainfo.title_year} "
                            f"{mediainfo.steam_id}")
            else:
                logger.info(f"{steamid} STEAM识别结果：{mediainfo.type.value} "
                            f"{mediainfo.title_year}")
            return mediainfo
        else:
            logger.info(f"{meta.name if meta else steamid} 未匹配到STEAM媒体信息")

        return None

    def steam_info(self, steamid: int, mtype: MediaType = None) -> Optional[dict]:
        """
        获取STEAM信息
        :param steamid: STEAM ID
        :param mtype:    媒体类型
        :return: STEAM信息
        """
        """
        {
            "type": "game",
            "name": "小骨：英雄杀手(Skul: The Hero Slayer)",
            "steam_appid": 1147560,
            "required_age": 0,
            "is_free": false,
            "controller_support": "full",
            "dlc": [
                1525720,
                2512790
            ],
            "detailed_description": "<a href=\"https://steamcommunity.com/linkfilter/?u=https%3A%2F%2Fdiscord.gg%2FNYnkFDE\" target=\"_blank\" rel=\" noopener\"  ><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Discord_skul.png?t=1700130360\" /></a><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/DemonCastle_Destroyed_W620.gif?t=1700130360\" /><h2 class=\"bb_tag\">背景</h2>与之前一样，人类再次袭击魔王城，但这次与之前不同， 冒险者们决定与帝国军和《卡利恩的勇者》联手发动全面进攻 。希望一劳永逸的彻底摧毁魔王城， 而他们成功的以压倒性的数量将魔王城毁于一旦。<br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Combat.gif?t=1700130360\" /><h2 class=\"bb_tag\">横版动作游戏</h2>Skul：The Hero Slayer是平台动作游戏，具备每次游戏时都会变化的地图和多样的奖励系统、以及一旦失败便会重新开始等Rogue-lite的经典特点 。<br><br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/SwapSkull_W620.gif?t=1700130360\" /><h2 class=\"bb_tag\">万千头骨，万千可操控角色</h2>Skul是一个特殊的小骷髅，除了他独特的战斗技能外，他也可以通过戴上其他头骨来获得崭新的能力。每次最多可以装备两个头骨，每一个头骨都有自己独特的攻击范围，速度与力量！<br>选择属于你自己的风格的组合，在火热的战斗中击败敌人吧！<br><br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Adventurers.gif?t=1700130360\" /><h2 class=\"bb_tag\">冒险家</h2>在冒险途中的小骨与一伙冒险家对上了眼神！那些贪婪的家伙把狩猎魔族当作了娱乐赛事…并想通过狩猎你而一战成名！<br>但是“小骨虽小，力能击石！”谁是猎手谁是猎物可不一定呢…<br><br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Boss.gif?t=1700130360\" /><h2 class=\"bb_tag\">被黑暗魔石所侵蚀的Boss们</h2>每个章节的最后一关，小骨会与因黑魔石的严重侵蚀而变得强大到不可理喻的最大敌人正面交锋！黑魔石是从生命自身的憎恨和痛苦中提取的邪恶石头，它能污染并控制一切触碰到它的生灵，也因此几乎无人能够熟练的掌控黑魔石。<br><br><br><strong>BUG反馈及玩法交流</strong><br>玩家QQ群：420112400<br>B站：<a href=\"https://steamcommunity.com/linkfilter/?u=https%3A%2F%2Fspace.bilibili.com%2F487760001\" target=\"_blank\" rel=\" noopener\"  >https://space.bilibili.com/487760001</a>",
            "about_the_game": "<a href=\"https://steamcommunity.com/linkfilter/?u=https%3A%2F%2Fdiscord.gg%2FNYnkFDE\" target=\"_blank\" rel=\" noopener\"  ><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Discord_skul.png?t=1700130360\" /></a><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/DemonCastle_Destroyed_W620.gif?t=1700130360\" /><h2 class=\"bb_tag\">背景</h2>与之前一样，人类再次袭击魔王城，但这次与之前不同， 冒险者们决定与帝国军和《卡利恩的勇者》联手发动全面进攻 。希望一劳永逸的彻底摧毁魔王城， 而他们成功的以压倒性的数量将魔王城毁于一旦。<br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Combat.gif?t=1700130360\" /><h2 class=\"bb_tag\">横版动作游戏</h2>Skul：The Hero Slayer是平台动作游戏，具备每次游戏时都会变化的地图和多样的奖励系统、以及一旦失败便会重新开始等Rogue-lite的经典特点 。<br><br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/SwapSkull_W620.gif?t=1700130360\" /><h2 class=\"bb_tag\">万千头骨，万千可操控角色</h2>Skul是一个特殊的小骷髅，除了他独特的战斗技能外，他也可以通过戴上其他头骨来获得崭新的能力。每次最多可以装备两个头骨，每一个头骨都有自己独特的攻击范围，速度与力量！<br>选择属于你自己的风格的组合，在火热的战斗中击败敌人吧！<br><br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Adventurers.gif?t=1700130360\" /><h2 class=\"bb_tag\">冒险家</h2>在冒险途中的小骨与一伙冒险家对上了眼神！那些贪婪的家伙把狩猎魔族当作了娱乐赛事…并想通过狩猎你而一战成名！<br>但是“小骨虽小，力能击石！”谁是猎手谁是猎物可不一定呢…<br><br><br><br><img src=\"https://cdn.akamai.steamstatic.com/steam/apps/1147560/extras/Boss.gif?t=1700130360\" /><h2 class=\"bb_tag\">被黑暗魔石所侵蚀的Boss们</h2>每个章节的最后一关，小骨会与因黑魔石的严重侵蚀而变得强大到不可理喻的最大敌人正面交锋！黑魔石是从生命自身的憎恨和痛苦中提取的邪恶石头，它能污染并控制一切触碰到它的生灵，也因此几乎无人能够熟练的掌控黑魔石。<br><br><br><strong>BUG反馈及玩法交流</strong><br>玩家QQ群：420112400<br>B站：<a href=\"https://steamcommunity.com/linkfilter/?u=https%3A%2F%2Fspace.bilibili.com%2F487760001\" target=\"_blank\" rel=\" noopener\"  >https://space.bilibili.com/487760001</a>",
            "short_description": "Skul：The Hero Slayer是2D Rogue Lite动作平台游戏。负责魔王城平安的小骷髅“Skul”，为了拯救被人类捉住的魔王，一个人独自对抗帝国军队开始冒险。",
            "supported_languages": "英语, 日语, 韩语, 简体中文, 德语, 法语, 西班牙语 - 西班牙, 俄语, 繁体中文, 葡萄牙语 - 巴西, 波兰语",
            "reviews": "“一款美丽而高品质的像素风格游戏。”<br><a href=\"https://www.pcgamer.com/five-new-steam-games-you-probably-missed-february-24-2020/\" target=\"_blank\" rel=\"\"  >PC Gamer</a><br><br>“使人造成一种紧张气氛的游戏操作。”<br><a href=\"https://steamcommunity.com/linkfilter/?u=https%3A%2F%2Findiegamesplus.com%2F2020%2F02%2Fskul-the-hero-slayer-is-a-roguelike-of-many-hats-or-skulls\" target=\"_blank\" rel=\" noopener\"  >Indie Games Plus</a><br><br>“多种角色和特征包括在内的游戏。”<br><a href=\"https://steamcommunity.com/linkfilter/?u=https%3A%2F%2Fpixeljudge.com%2Fpreviews%2Fskul-the-hero-slayer%2F\" target=\"_blank\" rel=\" noopener\"  >Pixel Judge</a><br>",
            "header_image": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/header_alt_assets_3_schinese.jpg?t=1700130360",
            "capsule_image": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/capsule_231x87_alt_assets_3_schinese.jpg?t=1700130360",
            "capsule_imagev5": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/capsule_184x69_alt_assets_3_schinese.jpg?t=1700130360",
            "website": "https://playneowiz.com/skul",
            "pc_requirements": {
                "minimum": "<strong>最低配置:</strong><br><ul class=\"bb_ul\"><li><strong>操作系统 *:</strong> Windows 7+<br></li><li><strong>处理器:</strong> Dual core from Intel or AMD at 2.8 GHz<br></li><li><strong>内存:</strong> 4 GB RAM<br></li><li><strong>显卡:</strong> Nvidia 450 GTS / Radeon HD 5750 or better<br></li><li><strong>DirectX 版本:</strong> 11<br></li><li><strong>存储空间:</strong> 需要 1 GB 可用空间<br></li><li><strong>附注事项:</strong> DirectX 9.1+ or OpenGL 3.2+</li></ul>",
                "recommended": "<strong>推荐配置:</strong><br><ul class=\"bb_ul\"><li><strong>操作系统 *:</strong> Windows 7+<br></li><li><strong>处理器:</strong> Dual core from Intel or AMD at 2.8 GHz<br></li><li><strong>内存:</strong> 8 GB RAM<br></li><li><strong>显卡:</strong> Nvidia GTX 460 / Radeon HD 7800 or better<br></li><li><strong>DirectX 版本:</strong> 12<br></li><li><strong>存储空间:</strong> 需要 2 GB 可用空间<br></li><li><strong>附注事项:</strong> DirectX 9.1+ or OpenGL 3.2+</li></ul>"
            },
            "mac_requirements": {
                "minimum": "<strong>最低配置:</strong><br><ul class=\"bb_ul\"><li><strong>操作系统:</strong> Mac OS X 10.12+<br></li><li><strong>处理器:</strong> Dual core from Intel or AMD at 2.8 GHz<br></li><li><strong>内存:</strong> 4 GB RAM<br></li><li><strong>显卡:</strong> Nvidia 450 GTS / Radeon HD 5750 or better<br></li><li><strong>存储空间:</strong> 需要 1 GB 可用空间<br></li><li><strong>附注事项:</strong> MacBook, MacBook Pro or iMac 2012 or later</li></ul>",
                "recommended": "<strong>推荐配置:</strong><br><ul class=\"bb_ul\"><li><strong>操作系统:</strong> Mac OS X 10.12+<br></li><li><strong>处理器:</strong> Dual core from Intel or AMD at 2.8 GHz<br></li><li><strong>内存:</strong> 8 GB RAM<br></li><li><strong>显卡:</strong> Nvidia GTX 460 / Radeon HD 7800 or better<br></li><li><strong>存储空间:</strong> 需要 2 GB 可用空间<br></li><li><strong>附注事项:</strong> MacBook, MacBook Pro or iMac 2012 or later</li></ul>"
            },
            "linux_requirements": {
                "minimum": "<strong>最低配置:</strong><br><ul class=\"bb_ul\"><li><strong>操作系统:</strong> Ubuntu<br></li><li><strong>处理器:</strong> Dual core from Intel or AMD at 2.8 GHz<br></li><li><strong>内存:</strong> 4 GB RAM<br></li><li><strong>显卡:</strong> Nvidia 450 GTS / Radeon HD 5750 or better<br></li><li><strong>存储空间:</strong> 需要 1 GB 可用空间<br></li><li><strong>附注事项:</strong> OpenGL 3.2+</li></ul>",
                "recommended": "<strong>推荐配置:</strong><br><ul class=\"bb_ul\"><li><strong>操作系统:</strong> Ubuntu<br></li><li><strong>处理器:</strong> Dual core from Intel or AMD at 2.8 GHz<br></li><li><strong>内存:</strong> 8 GB RAM<br></li><li><strong>显卡:</strong> Nvidia GTX 460 / Radeon HD 7800 or better<br></li><li><strong>存储空间:</strong> 需要 2 GB 可用空间<br></li><li><strong>附注事项:</strong> OpenGL 3.2+</li></ul>"
            },
            "legal_notice": "Developed by SouthPAW Games Corp, Ltd. Published by NEOWIZ. Skul: The Hero Slayer logos are trademarks of NEOWIZ, registered in the Republic of Korea and other countries. Skul: The Hero Slayer is a trademark of NEOWIZ. and may be registered in the Republic of Korea and other countries. All other marks and trademarks are the property of their respective owners. All rights reserved.",
            "developers": [
                "SOUTHPAW GAMES"
            ],
            "publishers": [
                "NEOWIZ"
            ],
            "price_overview": {
                "currency": "CNY",
                "initial": 7000,
                "final": 7000,
                "discount_percent": 0,
                "initial_formatted": "",
                "final_formatted": "¥ 70.00"
            },
            "packages": [
                390952
            ],
            "package_groups": [
                {
                    "name": "default",
                    "title": "购买 小骨：英雄杀手(Skul: The Hero Slayer)",
                    "description": "",
                    "selection_text": "选择一个购买选项",
                    "save_text": "",
                    "display_type": 0,
                    "is_recurring_subscription": "false",
                    "subs": [
                        {
                            "packageid": 390952,
                            "percent_savings_text": " ",
                            "percent_savings": 0,
                            "option_text": "Skul: The Hero Slayer - ¥ 70.00",
                            "option_description": "",
                            "can_get_free_license": "0",
                            "is_free_license": false,
                            "price_in_cents_with_discount": 7000
                        }
                    ]
                }
            ],
            "platforms": {
                "windows": true,
                "mac": true,
                "linux": true
            },
            "metacritic": {
                "score": 80,
                "url": "https://www.metacritic.com/game/pc/skul-the-hero-slayer?ftag=MCD-06-10aaa1f"
            },
            "categories": [
                {
                    "id": 2,
                    "description": "单人"
                },
                {
                    "id": 28,
                    "description": "完全支持控制器"
                },
                {
                    "id": 23,
                    "description": "Steam 云"
                },
                {
                    "id": 41,
                    "description": "在手机上远程畅玩"
                },
                {
                    "id": 42,
                    "description": "在平板上远程畅玩"
                },
                {
                    "id": 43,
                    "description": "在电视上远程畅玩"
                }
            ],
            "genres": [
                {
                    "id": "1",
                    "description": "动作"
                },
                {
                    "id": "23",
                    "description": "独立"
                }
            ],
            "screenshots": [
                {
                    "id": 0,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_b5ed9f9f5c95df4e168107d024cd4107bc2223e3.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_b5ed9f9f5c95df4e168107d024cd4107bc2223e3.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 1,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_4d085911571f127e48dc392c0db50d97e810fb39.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_4d085911571f127e48dc392c0db50d97e810fb39.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 2,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_119845ea870bb04a8c75abbef135f6a21cc0687c.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_119845ea870bb04a8c75abbef135f6a21cc0687c.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 3,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_44eae43480fa6d9c350bf6d1100e6d8dc911d8ee.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_44eae43480fa6d9c350bf6d1100e6d8dc911d8ee.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 4,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_c29cf7bfb3dfc5dd7ca0428f92c12a68c8c632cb.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_c29cf7bfb3dfc5dd7ca0428f92c12a68c8c632cb.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 5,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_0fdb27a3333b7c2acdd7803394c9b3237ec7894b.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_0fdb27a3333b7c2acdd7803394c9b3237ec7894b.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 6,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_8e5a7aa752779386252ff5b7f45ed86f9cac07d7.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_8e5a7aa752779386252ff5b7f45ed86f9cac07d7.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 7,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_eb69096a8d5b1febdf0b0374e1ce513c2b3549d9.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_eb69096a8d5b1febdf0b0374e1ce513c2b3549d9.1920x1080.jpg?t=1700130360"
                },
                {
                    "id": 8,
                    "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_43e7cf01e7f6066fadf8bd725aa437311820a755.600x338.jpg?t=1700130360",
                    "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/ss_43e7cf01e7f6066fadf8bd725aa437311820a755.1920x1080.jpg?t=1700130360"
                }
            ],
            "movies": [
                {
                    "id": 256982920,
                    "name": "Skul Demon King Castle Defense",
                    "thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/256982920/movie.293x165.jpg?t=1700104657",
                    "webm": {
                        "480": "http://cdn.akamai.steamstatic.com/steam/apps/256982920/movie480_vp9.webm?t=1700104657",
                        "max": "http://cdn.akamai.steamstatic.com/steam/apps/256982920/movie_max_vp9.webm?t=1700104657"
                    },
                    "mp4": {
                        "480": "http://cdn.akamai.steamstatic.com/steam/apps/256982920/movie480.mp4?t=1700104657",
                        "max": "http://cdn.akamai.steamstatic.com/steam/apps/256982920/movie_max.mp4?t=1700104657"
                    },
                    "highlight": true
                },
                {
                    "id": 256924565,
                    "name": "Skul Dark Mirror Trailer",
                    "thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/256924565/movie.293x165.jpg?t=1681111491",
                    "webm": {
                        "480": "http://cdn.akamai.steamstatic.com/steam/apps/256924565/movie480_vp9.webm?t=1681111491",
                        "max": "http://cdn.akamai.steamstatic.com/steam/apps/256924565/movie_max_vp9.webm?t=1681111491"
                    },
                    "mp4": {
                        "480": "http://cdn.akamai.steamstatic.com/steam/apps/256924565/movie480.mp4?t=1681111491",
                        "max": "http://cdn.akamai.steamstatic.com/steam/apps/256924565/movie_max.mp4?t=1681111491"
                    },
                    "highlight": true
                },
                {
                    "id": 256818846,
                    "name": "Skul 1.0 Trailer",
                    "thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/256818846/movie.293x165.jpg?t=1611132068",
                    "webm": {
                        "480": "http://cdn.akamai.steamstatic.com/steam/apps/256818846/movie480_vp9.webm?t=1611132068",
                        "max": "http://cdn.akamai.steamstatic.com/steam/apps/256818846/movie_max_vp9.webm?t=1611132068"
                    },
                    "mp4": {
                        "480": "http://cdn.akamai.steamstatic.com/steam/apps/256818846/movie480.mp4?t=1611132068",
                        "max": "http://cdn.akamai.steamstatic.com/steam/apps/256818846/movie_max.mp4?t=1611132068"
                    },
                    "highlight": true
                }
            ],
            "recommendations": {
                "total": 40937
            },
            "achievements": {
                "total": 100,
                "highlighted": [
                    {
                        "name": "传说的开始",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/905378d6b770947b341d8024695deb1febff10d7.jpg"
                    },
                    {
                        "name": "欢迎新手",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/e062cd00191759a2d133107192fa39c4e1fe5fda.jpg"
                    },
                    {
                        "name": "注意！",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/030c5c1f5014c20a137a1cf09540cc34c0baec41.jpg"
                    },
                    {
                        "name": "回家……",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/25238a05788aaeec21257771b384ac1969d15561.jpg"
                    },
                    {
                        "name": "魔王城收复战",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/26bb3180c19e436900d3de850c945f63db997c28.jpg"
                    },
                    {
                        "name": "被挽救的树精长老",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/587d5fdead9f488ad5045443ed35c21af770836a.jpg"
                    },
                    {
                        "name": "敏捷的身手",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/61bf2192daccb7766cb628918746a1d5824d3edc.jpg"
                    },
                    {
                        "name": "金鬃骑士团的末日",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/a6c52f139fdf71538a76bb2888b164dbfd103912.jpg"
                    },
                    {
                        "name": "闪电战的代价",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/cf05eb1ab7e3f5d37cd979880114c30a63404e1c.jpg"
                    },
                    {
                        "name": "冒牌女神消失",
                        "path": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/1147560/6f27f6bf62dcf512e950a32c7f182dfc1fb3ceae.jpg"
                    }
                ]
            },
            "release_date": {
                "coming_soon": false,
                "date": "2021 年 1 月 21 日"
            },
            "support_info": {
                "url": "https://playneowiz.com/skul",
                "email": "Skul_support@neowiz.com"
            },
            "background": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/page_bg_generated_v6b.jpg?t=1700130360",
            "background_raw": "https://cdn.akamai.steamstatic.com/steam/apps/1147560/page.bg.jpg?t=1700130360",
            "content_descriptors": {
                "ids": [],
                "notes": null
            }
        }
        """

        def __steam_game():
            """
            获取STEAM游戏信息
            """
            schinese_info = self.steamapi.game_detail(steamid).get(str(steamid)).get("data")
            english_info = self.steamapi.game_detail(steamid, lang="english").get(str(steamid)).get("data")
            schinese_info["original_title"] = english_info.get("name")
            return schinese_info
            
        if not steamid:
            return None
        logger.info(f"开始获取STEAM信息：{steamid} ...")
        if mtype == MediaType.GAME:
            return __steam_game()
        
        return None

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        搜索媒体信息
        :param meta:  识别的元数据
        :reutrn: 媒体信息
        """
        # 未启用STEAM搜索时返回None
        if settings.SEARCH_SOURCE and "steam" not in settings.SEARCH_SOURCE:
            return None

        if not meta.name:
            return []
        result = self.steamapi.search(meta.name)
        if not result:
            return []
        # 返回数据
        ret_medias = []
        for item_obj in result:
            ret_medias.append(MediaInfo(steam_info=item_obj))

        return ret_medias

    @retry(Exception, 5, 3, 3, logger=logger)
    def match(self, name: str, 
                         mtype: MediaType = None, year: str = None) -> dict:
        """
        搜索和匹配STEAM信息
        :param name:  名称
        :param mtype:  类型
        :param year:  年份
        """
        # 搜索
        logger.info(f"开始使用名称 {name} 匹配STEAM信息 ...")
        result = self.steamapi.search(f"{name}".strip())
        if not result:
            logger.warn(f"未找到 {name} 的STEAM信息")
            return {}
        for item in result:
            title = item.get("name")
            if not title:
                continue
            meta = MetaInfo(title)
            if meta.name == name:
                logger.info(f"{name} 匹配到STEAM信息：{item.get('steam_appid')} {item.get('title')}")
                return item
        return {}

    def scrape_metadata(self, path: Path, mediainfo: MediaInfo, transfer_type: str) -> None:
        """
        刮削元数据
        :param path: 媒体文件路径
        :param mediainfo:  识别的媒体信息
        :param transfer_type: 传输类型
        :return: 成功或失败
        """
        if not settings.SCRAP_SOURCE.__contains__("steam"):
            return None
        
        # 游戏目录
        logger.info(f"开始刮削游戏目录：{path} ...")
        meta = MetaInfo(path.stem)
        if not meta.name:
            return
        
        steaminfo = self.steam_info(steamid=mediainfo.steam_id,
                                            mtype=mediainfo.type)
        if not steaminfo:
            logger(f"未获取到 {mediainfo.steam_id} 的STEAM媒体信息，无法刮削！")
            return
        # STEAM媒体信息
        mediainfo = MediaInfo(steam_info=steaminfo)
        # 补充图片
        self.obtain_images(mediainfo)
        # 刮削路径
        scrape_path = path / path.name
        self.scraper.gen_scraper_files(meta=meta,
                                        mediainfo=mediainfo,
                                        file_path=scrape_path,
                                        transfer_type=transfer_type)

        logger.info(f"{path} 刮削完成")

    def scheduler_job(self) -> None:
        """
        定时任务，每10分钟调用一次
        """
        self.cache.save()

    def obtain_images(self, mediainfo: MediaInfo) -> Optional[MediaInfo]:
        """
        补充抓取媒体信息图片
        :param mediainfo:  识别的媒体信息
        :return: 更新后的媒体信息
        """
        if not "steam" in settings.RECOGNIZE_SOURCE:
            return None
        if not mediainfo.steam_id:
            return None
        if mediainfo.backdrop_path:
            # 没有图片缺失
            return mediainfo
        raise
        # return mediainfo

    def clear_cache(self):
        """
        清除缓存
        """
        logger.info("开始清除STEAM缓存 ...")
        self.steamapi.clear_cache()
        self.cache.clear()
        logger.info("STEAM缓存清除完成")
