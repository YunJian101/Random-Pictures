#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志中间件
"""

from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils import get_client_ip


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()

        # 获取客户端IP
        x_forwarded_for = request.headers.get('X-Forwarded-For', '')
        client_ip = get_client_ip(x_forwarded_for, request.client.host if request.client else '')

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = (datetime.now() - start_time).total_seconds()

        # 记录日志
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {client_ip} - {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

        return response
