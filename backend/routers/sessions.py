#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录设备（我的会话）
==============

用户自助查看「账号在哪些设备上登录过」，并可把不认识的设备踢下线。

安全约定：
- 永远不返回 token 本身，只给一个由 token 派生的短标识（sha256 前 12 位），
  既能定位会话，泄露了也无法用来登录；
- 只能操作自己的会话（WHERE user_id = 当前用户），越权一律 404；
- 踢掉「当前设备」也允许，但会连带清掉自己的 Cookie，前端需提示。

设备名由 UA 粗略解析，不做指纹识别——这里的目标是「让你认出这是不是自己的设备」，
不是精确识别机型。
"""

import hashlib

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..api.dependencies import get_current_user
from ..core.config import COOKIE_NAME
from ..core.database import get_async_db_connection
from ..services.audit_service import record as audit
from ..utils.utils import execute_count

__all__ = ['api_my_sessions', 'api_revoke_session', 'api_revoke_other_sessions']


def _sid(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


# 顺序有讲究：很多浏览器 UA 里同时含 Chrome/Safari，必须先判更具体的
UA_RULES = (
    ('micromessenger', '微信'),
    ('qqbrowser', 'QQ 浏览器'),
    ('ucbrowser', 'UC 浏览器'),
    ('edga/', 'Edge'),
    ('edg/', 'Edge'),
    ('opr/', 'Opera'),
    ('opera', 'Opera'),
    ('fxios', 'Firefox'),
    ('crios', 'Chrome'),
    ('firefox/', 'Firefox'),
    ('chrome/', 'Chrome'),
    ('safari/', 'Safari'),
    ('curl/', 'curl'),
    ('wget/', 'wget'),
    ('python', 'Python 脚本'),
    ('okhttp', 'App 客户端'),
)


def _describe_ua(ua: str, is_current: bool = False) -> dict:
    """把 UA 粗分成「浏览器 + 系统」，够用户认出设备即可"""
    ua = ua or ''
    low = ua.lower()

    if not low:
        # 加字段之前建立的老会话确实没有 UA；当前会话则用本次请求头兜底（见调用方）
        return {'browser': '未知设备', 'os': ''}

    browser = '其它浏览器'
    for token, label in UA_RULES:
        if token in low:
            browser = label
            break

    if 'windows' in low:
        os_name = 'Windows'
    elif 'android' in low:
        os_name = 'Android'
    elif 'iphone' in low or 'ipad' in low or 'ios' in low:
        os_name = 'iOS'
    elif 'mac os' in low or 'macintosh' in low:
        os_name = 'macOS'
    elif 'linux' in low:
        os_name = 'Linux'
    else:
        os_name = '未知系统'

    return {'browser': browser, 'os': os_name}


async def api_my_sessions(request: Request, current_user: dict = Depends(get_current_user)):
    """列出当前账号的所有有效会话"""
    current_token = request.cookies.get(COOKIE_NAME) or ''

    try:
        async with get_async_db_connection() as conn:
            rows = await conn.fetch('''
                SELECT token, created_at, last_seen, expires_at, ip, user_agent
                FROM sessions
                WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP
                ORDER BY COALESCE(last_seen, created_at) DESC
            ''', current_user['id'])

        # 当前请求的 UA 就是「当前设备」的 UA：老会话没存 UA 时用它兜底，
        # 否则会显示成「未知客户端」，用户根本判断不出是不是自己
        current_ua = (request.headers.get('user-agent') or '')[:200]

        sessions = []
        for row in rows:
            is_current = row['token'] == current_token
            ua = row['user_agent'] or (current_ua if is_current else '')
            info = _describe_ua(ua, is_current)
            sessions.append({
                'id': _sid(row['token']),
                'is_current': is_current,
                'ip': row['ip'] or '',
                'browser': info['browser'],
                'os': info['os'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else '',
                'last_seen': (row['last_seen'] or row['created_at']).isoformat()
                if (row['last_seen'] or row['created_at']) else '',
                'expires_at': row['expires_at'].isoformat() if row['expires_at'] else '',
            })

        return JSONResponse(content={
            'code': 200,
            'msg': 'success',
            'data': {'sessions': sessions, 'total': len(sessions)},
        })

    except Exception as e:
        print(f"[ERROR] 获取登录设备失败: {str(e)}")
        return JSONResponse(content={'code': 500, 'msg': '获取登录设备失败'}, status_code=500)


async def api_revoke_session(sid: str, request: Request, current_user: dict = Depends(get_current_user)):
    """踢掉一个指定会话（只能是自己账号的）"""
    try:
        async with get_async_db_connection() as conn:
            rows = await conn.fetch(
                'SELECT token FROM sessions WHERE user_id = $1', current_user['id']
            )
            target = next((r['token'] for r in rows if _sid(r['token']) == sid), None)

            if not target:
                raise HTTPException(status_code=404, detail="会话不存在或已失效")

            await conn.execute('DELETE FROM sessions WHERE token = $1', target)

        is_current = target == (request.cookies.get(COOKIE_NAME) or '')
        await audit(request, 'session.revoke', current_user,
                    target_type='session', target_id=sid,
                    detail='退出一个登录设备' + ('（当前设备）' if is_current else ''))

        return JSONResponse(content={
            'code': 200,
            'msg': '设备已退出登录',
            'data': {'is_current': is_current},
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 退出登录设备失败: {str(e)}")
        return JSONResponse(content={'code': 500, 'msg': '操作失败'}, status_code=500)


async def api_revoke_other_sessions(request: Request, current_user: dict = Depends(get_current_user)):
    """退出除当前设备外的所有会话"""
    current_token = request.cookies.get(COOKIE_NAME) or ''

    try:
        async with get_async_db_connection() as conn:
            removed = await execute_count(conn, '''
                DELETE FROM sessions WHERE user_id = $1 AND token <> $2
            ''', current_user['id'], current_token)

        await audit(request, 'session.revoke', current_user,
                    target_type='session', target_id='others',
                    detail=f'退出其它 {removed} 个登录设备')

        return JSONResponse(content={
            'code': 200,
            'msg': f'已退出其它 {removed} 个设备',
            'data': {'removed': removed},
        })

    except Exception as e:
        print(f"[ERROR] 退出其它设备失败: {str(e)}")
        return JSONResponse(content={'code': 500, 'msg': '操作失败'}, status_code=500)
