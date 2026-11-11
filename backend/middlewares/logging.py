#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志中间件
==========

干两件事：
1. 打一行访问日志（标准输出，容器里 docker logs 能看）；
2. 把「有安全含义的异常请求」写进审核日志（见 middlewares/security_events.py）。
"""

from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.request import client_ip
from .security_events import maybe_record


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()

        # 取客户端 IP 统一走 utils.request：TRUST_PROXY=false 时不会信 X-Forwarded-For
        ip = client_ip(request)

        response = await call_next(request)

        process_time = (datetime.now() - start_time).total_seconds()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {ip} - {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

        # 401/403/429/5xx 这类请求进审核日志，便于事后追溯扫描与越权尝试
        await maybe_record(request, response.status_code, ip)

        return response
