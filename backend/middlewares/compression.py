#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本响应压缩
============

Starlette 自带的 GZipMiddleware 只看响应体大小，不看类型，会把 JPEG/PNG 也压一遍——
图片本来就已经压缩过，再 gzip 既省不了字节又白烧 CPU。图片站的主要流量恰恰是图片，
所以这里自己判一下 Content-Type，只压文本类：

    text/*、application/json、application/javascript、image/svg+xml

压缩阈值 1KB：再小的响应，gzip 头（约 20 字节）都不一定赚得回来。
"""

import gzip

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

__all__ = ['TextCompressionMiddleware']

COMPRESSIBLE = (
    'text/',
    'application/json',
    'application/javascript',
    'application/xml',
    'image/svg+xml',
)
MIN_SIZE = 1024


class TextCompressionMiddleware(BaseHTTPMiddleware):
    """只对文本类响应做 gzip（省带宽，不拖累图片）"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if response.status_code != 200:
            return response
        if 'gzip' not in (request.headers.get('accept-encoding') or '').lower():
            return response
        if response.headers.get('content-encoding'):
            return response

        content_type = (response.headers.get('content-type') or '').lower()
        if not content_type.startswith(COMPRESSIBLE):
            return response

        body = b''
        async for chunk in response.body_iterator:
            body += chunk if isinstance(chunk, bytes) else chunk.encode()

        if len(body) < MIN_SIZE:
            # 太小不值得压，但要原样回写（body_iterator 已经被消费）
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        compressed = gzip.compress(body, compresslevel=6)
        headers = dict(response.headers)
        headers['content-encoding'] = 'gzip'
        headers['content-length'] = str(len(compressed))
        # 代理/CDN 需要知道同一 URL 可能返回两种编码
        headers['vary'] = 'Accept-Encoding'

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
