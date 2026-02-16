#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI依赖项 - 方案一：参数化依赖
================================
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, Cookie

from ..core.config import COOKIE_NAME
from ..core.security.auth import verify_session


def _get_token_from_request(request: Request) -> Optional[str]:
    """从请求中获取token（Cookie或Header）"""
    # 优先从Cookie获取
    token = request.cookies.get(COOKIE_NAME)
    
    # 如果没有，从Authorization header获取
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
    
    return token


async def get_current_user(
    request: Request,
    optional: bool = False,
    require_admin: bool = False
) -> Optional[dict]:
    """
    统一认证依赖
    
    Args:
        optional: 是否可选认证（True: 未登录返回None）
        require_admin: 是否需要管理员权限
    
    Returns:
        用户信息字典，optional=True时未登录返回None
    
    Raises:
        HTTPException: 401未登录 / 403权限不足
    """
    token = _get_token_from_request(request)
    
    # 没有token
    if not token:
        if optional:
            return None
        raise HTTPException(status_code=401, detail="未登录")
    
    # 验证token
    result = await verify_session(token)
    if result['code'] != 200:
        if optional:
            return None
        raise HTTPException(status_code=401, detail=result['msg'])
    
    user = result['data']['user']
    
    # 检查管理员权限
    if require_admin and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="权限不足")
    
    return user


# ========== 便捷的依赖工厂函数 ==========

def require_auth() -> type:
    """工厂函数：创建必须登录的依赖"""
    return lambda: Depends(lambda r: get_current_user(r, optional=False))


def require_admin() -> type:
    """工厂函数：创建管理员权限的依赖"""
    return lambda: Depends(lambda r: get_current_user(r, optional=False, require_admin=True))


def optional_auth() -> type:
    """工厂函数：创建可选认证的依赖"""
    return lambda: Depends(lambda r: get_current_user(r, optional=True))


# ========== 向后兼容的别名（可选） ==========

async def get_current_user_optional(
    request: Request
) -> Optional[dict]:
    """可选认证依赖 - 向后兼容"""
    return await get_current_user(request, optional=True)


async def get_current_user_required(
    request: Request
) -> dict:
    """必须认证依赖 - 向后兼容"""
    return await get_current_user(request, optional=False)


async def get_current_admin(
    request: Request
) -> dict:
    """管理员依赖 - 向后兼容"""
    return await get_current_user(request, optional=False, require_admin=True)
