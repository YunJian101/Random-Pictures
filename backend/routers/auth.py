#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证路由模块
处理所有用户认证相关的API请求
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from ..core.config import COOKIE_NAME, COOKIE_MAX_AGE
from ..core.security.auth import register_user, login_user, logout_user, verify_session
from ..schemas.schemas import RegisterRequest, LoginRequest


async def api_register(data: RegisterRequest, response: Response):
    """用户注册API"""
    result = register_user(data.username, data.email, data.password)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_login(data: LoginRequest, response: Response):
    """用户登录API"""
    result = login_user(data.account, data.password)

    # 设置token到cookie
    if result['code'] == 200:
        token = result['data']['token']
        max_age = COOKIE_MAX_AGE if data.remember else None
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite='lax',
            max_age=max_age,
            secure=False,  # 开发环境设为False，生产环境设为True
            domain=None    # None表示当前域名
        )

    status_code = 200 if result['code'] == 200 else 401
    json_response = JSONResponse(content=result, status_code=status_code)

    # 如果登录成功，设置cookie到响应头
    if result['code'] == 200:
        token = result['data']['token']
        max_age = COOKIE_MAX_AGE if data.remember else None
        json_response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite='lax',
            max_age=max_age,
            secure=False,
            domain=None
        )

    return json_response


async def api_logout(response: Response, request: Request):
    """用户登出API"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        logout_user(token)

    # 清除cookie
    json_response = JSONResponse(content={'code': 200, 'msg': '登出成功'})
    json_response.delete_cookie(key=COOKIE_NAME)
    return json_response


async def api_auth_verify(request: Request):
    """验证用户登录状态API"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return JSONResponse(content={'code': 401, 'msg': '未登录'}, status_code=401)

    result = verify_session(token)
    status_code = 200 if result['code'] == 200 else 401
    return JSONResponse(content=result, status_code=status_code)
