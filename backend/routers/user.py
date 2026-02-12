#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户路由模块
处理用户相关的API请求
"""

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from ..auth import get_user_by_id
from ..dependencies import get_current_user


async def api_users(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息API"""
    user = get_user_by_id(current_user['id'])

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
