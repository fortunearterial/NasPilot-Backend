import asyncio
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.startup.workflow_initializer import init_workflow, stop_workflow
from app.startup.modules_initializer import shutdown_modules, start_modules
from app.startup.plugins_initializer import init_plugins_async
from app.startup.routers_initializer import init_routers
from app.log import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    定义应用的生命周期事件
    """
    logger.debug("Starting up...")
    # 启动模块
    start_modules(app)
    logger.debug("启动模块完成")
    try:
        # 初始化工作流动作
        init_workflow(app)
        logger.debug("初始化工作流动作完成")
    except Exception as e:
        logger.error(f"初始化工作流动作失败: {e}")
    try:
        # 初始化路由
        init_routers(app)
        logger.debug("初始化路由完成")
        # 初始化插件
        plugin_init_task = asyncio.create_task(init_plugins_async())
        logger.debug("初始化插件完成")
    except Exception as e:
        logger.critical(f"Error during starting up: {e}")
        logger.debug(traceback.format_exc())
        return
    try:
        # 在此处 yield，表示应用已经启动，控制权交回 FastAPI 主事件循环
        yield
    finally:
        print("Shutting down...")
        try:
            # 取消插件初始化
            plugin_init_task.cancel()
            await plugin_init_task
        except asyncio.CancelledError:
            print("Plugin installation task cancelled.")
        except Exception as e:
            print(f"Error during plugin installation shutdown: {e}")
        # 清理模块
        shutdown_modules(app)
        # 关闭工作流
        stop_workflow(app)

