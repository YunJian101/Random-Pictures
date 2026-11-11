#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 认证依赖
================

三个依赖各自只接受 `request`，权限语义固定在函数里。
（旧实现把 optional / require_admin 写成带默认值的函数参数，
  FastAPI 会把它们当成查询参数暴露出来，请求方可以传 `?optional=true`
  绕过 401 —— 这里改成内部函数，杜绝该问题。）
"""

from typing import Optional

from fastapi import HTTPException, Request

from ..core.config import COOKIE_NAME
from ..core.security.auth import verify_session


def _get_token_from_request(request: Request) -> Optional[str]:
    """从 Cookie 或 Authorization: Bearer 中取 token"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
    return token


async def _resolve_user(request: Request, optional: bool = False, require_admin: bool = False) -> Optional[dict]:
    """内部实现：解析当前用户并按需校验权限"""
    token = _get_token_from_request(request)

    if not token:
        if optional:
            return None
        raise HTTPException(status_code=401, detail="未登录")

    result = await verify_session(token)
    if result.get('code') != 200:
        if optional:
            return None
        raise HTTPException(status_code=401, detail=result.get('msg', '登录状态无效'))

    user = result['data']['user']

    if require_admin and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="权限不足")

    return user


async def get_current_user(request: Request) -> dict:
    """必须登录"""
    return await _resolve_user(request, optional=False)


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """可选登录：未登录返回 None"""
    return await _resolve_user(request, optional=True)


async def get_current_admin(request: Request) -> dict:
    """必须是管理员"""
    return await _resolve_user(request, optional=False, require_admin=True)


__all__ = [
    'get_current_user',
    'get_current_user_optional',
    'get_current_admin',
]
