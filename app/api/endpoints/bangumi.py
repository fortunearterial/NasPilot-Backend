from typing import List, Any, Optional

from fastapi import APIRouter, Depends

from app import schemas
from app.chain.bangumi import BangumiChain
from app.core.context import MediaInfo
from app.core.security import verify_token

router = APIRouter()


@router.get("/credits/{bangumiid}", summary="查询Bangumi演职员表", response_model=List[schemas.MediaPerson])
def bangumi_credits(bangumiid: int,
                    page: Optional[int] = 1,
                    count: Optional[int] = 20,
                    _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询Bangumi演职员表
    """
    persons = BangumiChain().bangumi_credits(bangumiid)
    if persons:
        return persons[(page - 1) * count: page * count]
    return []


@router.get("/recommend/{bangumiid}", summary="查询Bangumi推荐", response_model=List[schemas.MediaInfo])
def bangumi_recommend(bangumiid: int,
                      page: Optional[int] = 1,
                      count: Optional[int] = 20,
                      _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询Bangumi推荐
    """
    medias = BangumiChain().bangumi_recommend(bangumiid)
    if medias:
        return [media.to_dict() for media in medias[(page - 1) * count: page * count]]
    return []


@router.get("/person/{person_id}", summary="人物详情", response_model=schemas.MediaPerson)
def bangumi_person(person_id: int,
                   _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    根据人物ID查询人物详情
    """
    return BangumiChain().person_detail(person_id=person_id)


@router.get("/person/credits/{person_id}", summary="人物参演作品", response_model=List[schemas.MediaInfo])
def bangumi_person_credits(person_id: int,
                           page: Optional[int] = 1,
                           count: Optional[int] = 20,
                           _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    根据人物ID查询人物参演作品
    """
    medias = BangumiChain().person_credits(person_id=person_id)
    if medias:
        return [media.to_dict() for media in medias[(page - 1) * count: page * count]]
    return []


@router.get("/{bangumiid}", summary="查询Bangumi详情", response_model=schemas.MediaInfo)
def bangumi_info(bangumiid: int,
                 _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询Bangumi详情
    """
    info = BangumiChain().bangumi_info(bangumiid)
    if info:
        return MediaInfo(bangumi_info=info).to_dict()
    else:
        return schemas.MediaInfo()

@router.get("/{bangumiid}/{season}", summary="Bangumi季所有集") # , response_model=List[schemas.BangumiEpisode]
def bangumi_season_episodes(bangumiid: int, season: int,
                         _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    根据Bangumi查询某季的所有信信息
    """
    return BangumiChain().bangumi_episodes(bangumiid=bangumiid, season=season)
