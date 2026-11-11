#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
限流中间件
==========

文档里一直写着"每 IP 每分钟 N 次，超限返回 429"，但此前并没有真正实现。
这里用进程内的滑动窗口计数器兜住随机图 / 直链 / 缩略图这三个最耗资源的接口。

注意：
- 计数在进程内存里，多 worker 部署时每个进程各算一份（总限额 = 单进程 × worker 数）。
  如果需要全局精确限额，应换成 Redis；这里作为"防刷"的第一道闸足够。
- 默认不信任 X-Forwarded-For（TRUST_PROXY=false），否则客户端伪造就绕过限流了。
"""

import time
from collections import deque
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..core import runtime_config
from ..core.config import (
    RATE_LIMIT_AUTH_PATHS,
    RATE_LIMIT_AUTH_PER_MINUTE,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_PATHS,
    RATE_LIMIT_PER_MINUTE,
)
from ..handlers.error_handlers import is_html_request
from ..utils.request import client_ip
from ..utils.utils import get_error_page

WINDOW_SECONDS = 60.0
# 每处理这么多次请求做一次全量清理，避免大量一次性 IP 把字典撑大
CLEANUP_EVERY = 500


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 IP + 路径的滑动窗口限流"""

    def __init__(self, app, limit: int = 0, paths=None, auth_limit: int = 0, auth_paths=None):
        super().__init__(app)
        self.limit = limit or RATE_LIMIT_PER_MINUTE
        self.paths = tuple(paths or RATE_LIMIT_PATHS)
        # 登录 / 注册：单独一档，防撞库
        self.auth_limit = auth_limit or RATE_LIMIT_AUTH_PER_MINUTE
        self.auth_paths = tuple(auth_paths or RATE_LIMIT_AUTH_PATHS)

        # 计数桶：key = ip|path，value = 时间戳队列
        self.buckets: Dict[str, Deque[float]] = {}
        self.served = 0

    def _is_limited(self, path: str) -> bool:
        return path in self.paths or path in self.auth_paths

    def _client_key(self, request: Request, path: str) -> str:
        return f'{client_ip(request)}|{path}'

    def _cleanup(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        for key in list(self.buckets.keys()):
            bucket = self.buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if not bucket:
                self.buckets.pop(key, None)

    async def _too_many(self, request: Request, retry_after: int, limit: int) -> Response:
        headers = {
            'Retry-After': str(retry_after),
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': '0',
        }

        # 浏览器直接访问图片时给错误页，程序调用给 JSON
        if is_html_request(request):
            html = await get_error_page('429请求速率限制', {
                'limit': f'{limit} 次 / 分钟',
                'wait_time': f'{retry_after} 秒',
                'wait_seconds': str(retry_after),
            })
            if html:
                return Response(content=html, status_code=429,
                                media_type='text/html; charset=utf-8', headers=headers)

        return JSONResponse(
            content={
                'code': 429,
                'msg': '请求过于频繁，请稍后再试',
                'data': {'limit': limit, 'window': '60s', 'retry_after': retry_after},
            },
            status_code=429,
            headers=headers,
        )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not self._is_limited(path):
            return await call_next(request)

        # 阈值优先取数据库里的运行时配置（管理后台可改，改完 5 秒内生效），
        # 读不到就回落到环境变量默认值
        await runtime_config.ensure_loaded()

        if not runtime_config.get_bool('enable_rate_limit', RATE_LIMIT_ENABLED):
            return await call_next(request)

        if path in self.auth_paths:
            limit = runtime_config.get_int('rate_limit_auth_per_minute', self.auth_limit)
        else:
            limit = runtime_config.get_int('rate_limit_per_minute', self.limit)
        limit = max(1, limit)

        key = self._client_key(request, path)
        now = time.monotonic()

        bucket = self.buckets.get(key)
        if bucket is None:
            bucket = deque()
            self.buckets[key] = bucket

        cutoff = now - WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(WINDOW_SECONDS - (now - bucket[0])) + 1)
            return await self._too_many(request, retry_after, limit)

        bucket.append(now)

        self.served += 1
        if self.served % CLEANUP_EVERY == 0:
            self._cleanup(now)

        response = await call_next(request)
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(max(0, limit - len(bucket)))
        return response
