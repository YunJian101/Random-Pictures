#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
请求辅助
========

限流、登录防爆破、审核日志、错误页都要判「这个请求从哪个 IP 来」，此前这段逻辑
散落在各处（有的读 X-Forwarded-For、有的不读），会出现「登录设备里是局域网 IP、
上传 IP 却是公网 IP」这种自相矛盾的结果。统一放这里，谁要谁调。

「信不信反代」是运行时配置 trust_proxy：管理后台「系统设置」可改，改完 5 秒内生效。
环境变量 TRUST_PROXY 只作为出厂默认值。
"""

from fastapi import Request

from ..core import runtime_config
from ..core.config import TRUST_PROXY
from .utils import get_client_ip

__all__ = ['client_ip']


async def client_ip(request: Request) -> str:
    """取客户端 IP

    trust_proxy=false（默认）时只认 TCP 连接的对端地址：直连部署下
    X-Forwarded-For 完全由客户端伪造，信了就等于限流形同虚设。

    trust_proxy=true 时取 X-Forwarded-For 里第一个公网地址（取不到则回落到对端）。

    这里每次调用前刷新一次运行时配置快照，所以后台切开关不用重启容器；
    快照有 5 秒缓存，不会真的每个请求都查库。
    """
    await runtime_config.ensure_loaded()

    remote = request.client.host if request.client else 'unknown'
    if not runtime_config.get_bool('trust_proxy', TRUST_PROXY):
        return remote
    return get_client_ip(request.headers.get('X-Forwarded-For', ''), remote)
