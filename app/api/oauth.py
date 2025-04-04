from fastapi import APIRouter

from app.api.endpoints import oauth

oauth_router = APIRouter()
oauth_router.include_router(oauth.router, prefix="", tags=["oauth2.0"])
