from typing import Optional

from fastapi import HTTPException, BackgroundTasks, APIRouter, FastAPI
from fastapi.params import Depends
from pydantic import BaseModel
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright.async_api._generated import Playwright as AsyncPlaywright
import asyncio
import uuid

from app import schemas
from app.core.config import settings
from app.log import logger
from app.core.security import verify_token

router = APIRouter()

# 简化的会话存储 (生产环境建议使用 Redis 或其他持久化存储)
# key: session_id (str), value: dict containing context_info or page_info
# 注意：直接存储 Playwright 对象可能存在序列化和管理问题，
# 更推荐的方式是管理 BrowserContext 的生命周期，并在需要时从中创建 Page。
active_login_sessions = {}
playwright_manager: Optional[AsyncPlaywright] = None


class LoginInitiatePayload(BaseModel):
    username: str
    password: str


class LoginCompletePayload(BaseModel):
    session_id: str
    sms_code: str


async def close_context_after_delay(context: BrowserContext, session_id: str, delay: int = 300):
    """延迟关闭 context 并清理会话"""
    global playwright_manager
    await asyncio.sleep(delay)
    if context and context.pages:  # 检查 context 是否仍然有效
        await context.close()
    if session_id in active_login_sessions:
        del active_login_sessions[session_id]
    if not active_login_sessions and playwright_manager:
        await playwright_manager.stop()
        playwright_manager = None
    print(f"Session {session_id} context closed and cleaned up after delay.")


@router.post("/test/initiate")
async def initiate_login(payload: LoginInitiatePayload,
                         background_tasks: BackgroundTasks,
                         _: schemas.TokenPayload = Depends(verify_token)):
    global playwright_manager
    if not playwright_manager:
        playwright_manager = await async_playwright().start()

    session_data = active_login_sessions.get(payload.username)
    if session_data:
        context: BrowserContext = session_data["context"]
    else:
        context = await playwright_manager.chromium.launch_persistent_context(
            user_data_dir=str(settings.CONFIG_PATH / "thunder/browser_data" / payload.username),
            headless=not settings.DEBUG, )
        active_login_sessions[payload.username] = {"context": context}
        # 设置一个超时自动清理任务
        background_tasks.add_task(close_context_after_delay, context, payload.username, 300)  # 5分钟后清理

    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()

    try:
        await page.goto("https://pan.xunlei.com/yc/home")
        # 未登录
        if await page.is_visible("span.button-login:has-text('立即登录')"):
            logger.info(f"开始登录")
            # 跳转登录页面
            await page.click("span.button-login:has-text('立即登录')")
            # 点击账号密码登录
            await page.click("span:has-text('账号密码登录')")
            # 输入账号密码
            await page.fill("input.xlubase-login-input[type='text']", payload.username)
            await page.fill("input.xlubase-login-input[type='password']", payload.password)
            await page.click("input.xlucommon-login-checkbox")
            # 点击登录
            await page.click("button.xlucommon-login-button")
            await page.wait_for_load_state("networkidle")
            # 检测是否有错误信息
            if await page.is_visible("p.xlucommon-login-note"):
                raise Exception(await page.text_content("p.xlucommon-login-note"))
            # 是否有短信验证
            frame = page.frame_locator("iframe")
            if await frame.locator("h3:has-text('请进行短信验证')").is_visible():
                # 点击获取验证码
                await frame.locator("#get-mobile-smscode").click()
                # 返回提示信息
                return schemas.Response(success=False,
                                        message="downloader.ext.sms_code_required",
                                        data={"session_id": payload.username})

        # 已登录
        await page.close()
        del active_login_sessions[payload.username]
        await context.close()  # 成功后关闭 context

        if not active_login_sessions and playwright_manager:
            await playwright_manager.stop()
            playwright_manager = None
        return schemas.Response(success=True)
    except Exception as e:
        if context:
            await context.close()  # 出错时也尝试关闭
        print(f"Error during login initiation for session {payload.username}: {e}")
        raise HTTPException(status_code=500, detail=f"Login initiation failed: {str(e)}")


@router.post("/test/complete")
async def complete_login(payload: LoginCompletePayload,
                         _: schemas.TokenPayload = Depends(verify_token)):
    global playwright_manager

    session_data = active_login_sessions.get(payload.session_id)
    if not session_data or not session_data.get("context"):
        raise HTTPException(status_code=404, detail="Login session not found, expired, or invalid.")

    context: BrowserContext = session_data["context"]
    page: Optional[Page] = None
    # 尝试获取context中的一个页面，或者基于之前的URL重新创建一个
    if context.pages:
        page = context.pages[0]  # 假设是第一个页面
    else:  # 如果没有页面，可能context已关闭或出错
        await context.close()
        if payload.session_id in active_login_sessions:
            del active_login_sessions[payload.session_id]
        raise HTTPException(status_code=410, detail="Login session context is no longer valid.")

    try:
        frame = page.frame_locator("iframe")
        # 填写验证码
        await frame.locator("#verification_code").fill(payload.sms_code)
        # 点击确定
        await frame.locator("a.next-step-btn").click()
        if await frame.locator("div.error-tips").is_visible() and \
                await frame.locator("div.error-tips").text_content():
            return schemas.Response(success=False, message=await frame.locator("div.error-tips").text_content())

        # 清理会话
        await page.close()
        if payload.session_id in active_login_sessions:
            del active_login_sessions[payload.session_id]
        await context.close()  # 成功后关闭 context

        if not active_login_sessions and playwright_manager:
            await playwright_manager.stop()
            playwright_manager = None

        return schemas.Response(success=True)
    except Exception as e:
        # 登录失败或发生其他错误，也需要清理
        if payload.session_id in active_login_sessions:
            del active_login_sessions[payload.session_id]
        if context:  # 确保 context 存在再关闭
            await context.close()
        print(f"Error during login completion for session {payload.session_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Login completion failed: {str(e)}")
