#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证路由模块
============

登录成功后只在一个响应对象上设置 Cookie（旧实现同时给 FastAPI 注入的
Response 和 JSONResponse 各设一次，前者实际不会生效）。
"""

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from ..core.config import COOKIE_MAX_AGE, COOKIE_NAME
from ..core.security.auth import login_user, logout_user, register_user, verify_session
from ..schemas.schemas import LoginRequest, RegisterRequest
from ..services.audit_service import record as audit
from ..utils.request import client_ip

# 生产环境（HTTPS）下应开启；本地 http 调试默认关闭
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes', 'on')


def _set_token_cookie(response: JSONResponse, token: str, remember: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite='lax',
        max_age=COOKIE_MAX_AGE if remember else None,
        secure=COOKIE_SECURE,
        domain=None,
    )


async def api_register(data: RegisterRequest, request: Request):
    """用户注册

    先查 IP 配额（防批量注册），成功后再计入配额。
    配额见 core/security/register_guard.py。
    """
    from ..core.security.register_guard import check_register_allowed, record_register

    ip = await client_ip(request)
    guard = await check_register_allowed(ip)
    if not guard['allowed']:
        resp = JSONResponse(
            content={'code': 429, 'msg': guard['msg'], 'retry_after': guard['retry_after']},
            status_code=429,
        )
        resp.headers['Retry-After'] = str(guard['retry_after'])
        return resp

    result = await register_user(data.username, data.email, data.password)
    if result['code'] == 200:
        quota = await record_register(ip)
        if quota.get('locked'):
            print(f"⚠️ IP {ip} 注册配额已用尽（{quota['count']}/{quota['quota']}）")

    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_login(data: LoginRequest, request: Request):
    """用户登录

    失败次数过多时由 login_guard 给出 429 + Retry-After，浏览器/前端可以据此
    倒计时，而不是傻等一个「密码错误」。
    """
    result = await login_user(
        data.account, data.password,
        ip=await client_ip(request),
        user_agent=request.headers.get('user-agent', ''),
    )

    status_map = {200: 200, 403: 403, 429: 429}
    status_code = status_map.get(result['code'], 401)
    response = JSONResponse(content=result, status_code=status_code)

    if status_code == 429 and result.get('retry_after'):
        response.headers['Retry-After'] = str(result['retry_after'])

    if result['code'] == 200:
        _set_token_cookie(response, result['data']['token'], bool(data.remember))
        await audit(request, 'auth.login', result['data']['user'],
                    target_type='session',
                    detail=f"登录成功（{result['data']['user'].get('role')}）")

    return response


async def api_logout(request: Request):
    """用户登出"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        # 先取一次用户信息，登出后才好写审计（此时会话还在）
        session = await verify_session(token)
        user = (session.get('data') or {}).get('user') if session.get('code') == 200 else None
        await logout_user(token)
        if user:
            await audit(request, 'auth.logout', user, target_type='session', detail='主动退出登录')

    response = JSONResponse(content={'code': 200, 'msg': '登出成功'})
    response.delete_cookie(key=COOKIE_NAME)
    return response


async def api_auth_verify(request: Request):
    """验证登录状态"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return JSONResponse(content={'code': 401, 'msg': '未登录'}, status_code=401)

    result = await verify_session(token)
    status_code = 200 if result['code'] == 200 else 401
    return JSONResponse(content=result, status_code=status_code)
