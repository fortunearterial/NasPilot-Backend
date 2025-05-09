import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Form, HTTPException, Depends

import schemas
from app.core import security
from app.core.cache import cache_backend
from app.core.config import settings
from app.db.user_oper import UserOper, get_current_active_user
from app.helper.sites import SitesHelper
from app.schemas import User

SECRET_KEY = "your-secret-key-32bytes"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = 7200

router = APIRouter()


@router.get("/authorize")
async def authorize(
        response_type: str,
        client_id: str,
        redirect_uri: str,
        state: str = None,
        # request: OAuth2AuthorizeRequestQuery,
        current_user: User = Depends(get_current_active_user),
):
    # 验证客户端
    # client = clients_db.get(client_id)
    # if not client or redirect_uri not in client["redirect_uris"]:
    #     raise HTTPException(status_code=400, detail="Invalid client")

    # 生成授权码（实际应存储并与用户会话关联）
    auth_code = secrets.token_urlsafe(32)
    cache_backend.set(auth_code, json.dumps({
        "response_type": response_type,
        "client_id": client_id,
        "state": state,
        "user_name": current_user.name,
    }), ttl=300)

    # 重定向到客户端回调地址
    # return RedirectResponse(f"{redirect_uri}?code={auth_code}&state={state}")
    return schemas.Response(success=True, data={
        "redirect_uri": f"{redirect_uri}?code={auth_code}&state={state}",
    })


@router.post("/token")
async def token(
        grant_type: str = Form(...),
        code: str = Form(...),
        code_verifier: str = Form(...),
        redirect_uri: str = Form(...),
        # form_data: OAuth2TokenRequestForm = Depends(),
):
    # 验证客户端凭证
    # client = clients_db.get(request.client_id)
    # if not client or client["client_secret"] != request.client_secret:
    #     raise HTTPException(status_code=401, detail="Invalid client credentials")

    # 验证授权码（此处简化，实际需验证code有效性）
    authorize_request = json.loads(cache_backend.get(code))
    cache_backend.delete(code)
    if not authorize_request:
        raise HTTPException(status_code=400, detail="Invalid authorization code")

    # success, user_or_message = UserChain().user_authenticate(
    #     code=code,
    #     grant_type=grant_type,
    # )
    user_or_message = UserOper().get_by_name(authorize_request.get("user_name"))
    success = user_or_message is not None

    if not success:
        raise HTTPException(status_code=401, detail=user_or_message)

    # 生成JWT
    level = SitesHelper().auth_level
    return schemas.Token(
        access_token=security.create_access_token(
            userid=user_or_message.id,
            username=user_or_message.name,
            super_user=user_or_message.is_superuser,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            level=level
        ),
        token_type="bearer",
        super_user=user_or_message.is_superuser,
        user_id=user_or_message.id,
        user_name=user_or_message.name,
        avatar=user_or_message.avatar,
        level=level
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE
    }
