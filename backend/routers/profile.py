#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人资料路由
============

登录用户管理自己的账号：
  GET  /api/me            → 当前账号信息
  PUT  /api/me            → 改用户名 / 邮箱
  PUT  /api/me/password   → 改密码（需校验原密码，改完注销其它会话）

管理员改他人信息走 /api/users/{id}，不在这里。
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from ..api.dependencies import get_current_user
from ..core.config import COOKIE_NAME
from ..core.database import get_async_db_connection
from ..core.security.auth import change_password, update_user_info, verify_user_password


# ==================== 请求模型 ====================
class ProfileUpdateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=16, description="3-16 位字母、数字、下划线")
    email: Optional[EmailStr] = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码，至少 6 位")


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


# ==================== 内部工具 ====================
async def _profile_payload(user_id: int) -> Optional[dict]:
    async with get_async_db_connection() as conn:
        row = await conn.fetchrow('''
            SELECT id, username, email, role, status, created_at, last_login
            FROM users WHERE id = $1
        ''', user_id)

    if not row:
        return None

    return {
        'id': row['id'],
        'username': row['username'],
        'email': row['email'],
        'role': row['role'],
        'is_banned': row['status'] == 'banned',
        'created_at': _iso(row['created_at']),
        'last_login': _iso(row['last_login']),
    }


# ==================== 接口 ====================
async def api_me(current_user: dict = Depends(get_current_user)):
    """当前登录账号的信息"""
    try:
        user = await _profile_payload(current_user['id'])
    except Exception as e:
        print(f'[ERROR] 读取个人资料失败: {str(e)}')
        raise HTTPException(status_code=500, detail="读取个人资料失败")

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return JSONResponse(content={'code': 200, 'msg': 'success', 'data': {'user': user}})


async def api_update_me(data: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    """修改自己的用户名 / 邮箱"""
    result = await update_user_info(current_user['id'], data.username.strip(), data.email)
    if result['code'] != 200:
        raise HTTPException(status_code=result['code'], detail=result['msg'])

    user = await _profile_payload(current_user['id'])
    return JSONResponse(content={
        'code': 200,
        'msg': '资料已更新',
        'data': {'user': user},
    })


async def api_change_my_password(
    data: PasswordChangeRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """修改自己的密码（需要原密码）"""
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    if not await verify_user_password(current_user['id'], data.current_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")

    # 保留当前会话，注销其它设备上的登录
    keep_token = request.cookies.get(COOKIE_NAME)
    result = await change_password(current_user['id'], data.new_password, keep_token=keep_token)
    if result['code'] != 200:
        raise HTTPException(status_code=result['code'], detail=result['msg'])

    return JSONResponse(content={
        'code': 200,
        'msg': '密码修改成功，其它设备上的登录已失效',
    })
