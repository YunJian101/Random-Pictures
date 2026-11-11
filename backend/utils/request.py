#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
请求辅助
========

限流和登录防爆破都要判「这个请求从哪个 IP 来」，此前这段逻辑只写在限流中间件里，
复制第二份很容易两边规则跑偏（比如一处信了 X-Forwarded-For、另一处没信）。
统一放这里，谁要谁调。
"""

from fastapi import Request

from ..core.config import TRUST_PROXY
from .utils import get_client_ip

__all__ = ['client_ip']


def client_ip(request: Request) -> str:
    """取客户端 IP

    TRUST_PROXY=false（默认）时只认 TCP 连接的对端地址：直连部署下
    X-Forwarded-For 完全由客户端伪造，信了就等于限流形同虚设。
    """
    remote = request.client.host if request.client else 'unknown'
    if not TRUST_PROXY:
        return remote
    return get_client_ip(request.headers.get('X-Forwarded-For', ''), remote)
