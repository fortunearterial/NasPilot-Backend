import logging

import ray
from fastapi import FastAPI


def shutdown_ray(_: FastAPI):
    """
    服务关闭
    """
    # 停止RAY
    ray.shutdown()


def start_ray(_: FastAPI):
    """
    启动模块
    """
    # 启用RAY
    context = ray.init(
        # _node_ip_address ="10.1.16.75",  # Head 节点 IP（需物理机真实 IP）
        include_dashboard=True,  # 启用仪表盘
        dashboard_port=8265,  # 仪表盘端口
        ignore_reinit_error=True
    )
    # 打印Ray仪表板的URL
    logging.debug(f'Ray Dashboard URL: http://{context.dashboard_url}')
