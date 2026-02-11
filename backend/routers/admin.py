#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员路由模块
处理管理员相关的API请求
"""

from fastapi import Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from ..auth import (
    get_all_users,
    get_user_by_id,
    update_user_info,
    ban_user,
    unban_user,
    delete_user,
    update_user_role,
    register_user
)
from ..dependencies import get_current_admin
from ..schemas import UserCreateRequest, UserUpdateRequest, CreateAdminRequest


async def api_admin_users(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户列表API"""
    users = get_all_users()

    formatted_users = []
    for user in users:
        formatted_users.append({
            'id': user['id'],
            'user_id': user['userId'],
            'username': user['username'],
            'email': user['email'],
            'role': 'admin' if user['type'] == '管理员' else 'user',
            'created_at': user['registerDate'] + ' 00:00:00',
            'last_login_ip': user['lastLogin'],
            'is_banned': user['status'] == '封禁',
            'avatar_url': user['avatar']
        })

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'users': formatted_users}
    })


async def api_admin_user_detail(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户详情API"""
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    formatted_user = {
        'id': user['id'],
        'user_id': user['userId'],
        'username': user['username'],
        'email': user['email'],
        'role': 'admin' if user['type'] == '管理员' else 'user',
        'created_at': user['registerDate'] + ' 00:00:00',
        'last_login_ip': user['lastLogin'],
        'is_banned': user['status'] == '封禁',
        'avatar_url': user['avatar']
    }

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'user': formatted_user}
    })


async def api_admin_users_create(data: UserCreateRequest, current_user: dict = Depends(get_current_admin)):
    """管理员创建用户API"""
    result = register_user(data.username, data.email or '', data.password)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_update(user_id: int, data: UserUpdateRequest, current_user: dict = Depends(get_current_admin)):
    """管理员更新用户信息API"""
    result = update_user_info(user_id, data.username, data.email)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_ban(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员封禁用户API"""
    result = ban_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_unban(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员解封用户API"""
    result = unban_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_delete(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员删除用户API"""
    result = delete_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_create_admin(data: CreateAdminRequest):
    """创建管理员用户API（仅用于初始化）"""
    result = register_user(data.username, data.email or '', data.password)

    if result['code'] == 200:
        user_id = result['data']['id']
        update_result = update_user_role(user_id, 'admin')
        if update_result['code'] == 200:
            result['msg'] = '管理员用户创建成功'
            result['data']['role'] = 'admin'
        else:
            result = update_result

    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)
