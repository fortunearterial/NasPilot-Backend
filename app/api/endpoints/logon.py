import random
import re  # 导入正则表达式模块
import string
from datetime import timedelta
from typing import Any, Annotated, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from app import schemas
from app.chain.user import UserChain
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.db import get_db
from app.db.models.user import User
from app.helper.sites import SitesHelper

router = APIRouter()


class LogonRequestForm:

    def __init__(
            self,
            name: str = Form(),
            password: str = Form(),
            confirm_password: str = Form(),
            sms_code: str = Form(),
            recommend_code: Optional[str] = Form(default=None),
    ):
        self.name = name
        self.password = password
        self.confirm_password = confirm_password
        self.sms_code = sms_code
        self.recommend_code = recommend_code


@router.post("/mobile", summary="用户注册", response_model=Union[schemas.Response, schemas.Token])
def create_user(
        *,
        form_data: Annotated[LogonRequestForm, Depends()],
        db: Session = Depends(get_db),
) -> Any:
    """
    用户注册
    """
    # 使用正则表达式验证手机号格式，以中国手机号为例
    phone_pattern = re.compile(r'^1[3-9]\d{9}$')
    if not phone_pattern.match(form_data.name):
        return schemas.Response(success=False, message="请输入正确的手机号")
    if form_data.password != form_data.confirm_password:
        return schemas.Response(success=False, message="两次输入的密码不一致")

    user = User.get_by_name(db, name=form_data.name)
    if user:
        return schemas.Response(success=False, message="用户已存在")
    user_info = dict()
    user_info.update(form_data.__dict__)
    if user_info.get("password"):
        user_info["hashed_password"] = get_password_hash(user_info["password"])
        user_info.pop("password")
        user_info.pop("confirm_password")
    if user_info.get("sms_code"):
        # 验证短信验证码
        user_info.pop("sms_code")
    user_info["phone"] = user_info.get("name")
    user_info["invite_code"] = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    user = User(**user_info)
    user.create(db)

    # 获取认证Token
    success, user_or_message = UserChain().user_authenticate(username=form_data.name,
                                                             password=form_data.password,
                                                             mfa_code=None)

    if not success:
        raise HTTPException(status_code=401, detail=user_or_message)

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

@router.post("/", summary="发送短信", response_model=schemas.Token)
def send_sms():
    pass