#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · users
============

管理员侧的账号管理：列表 / 详情 / 新建 / 改资料 / 封禁 / 删除
"""

from fastapi import (
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse
from ...api.dependencies import get_current_admin
from ...services.audit_service import record as audit
from ...schemas.schemas import (
    UserCreateRequest,
    UserUpdateRequest,
)
from ...core.security.auth import (
    ban_user,
    change_password,
    delete_user,
    get_all_users,
    get_user_by_id,
    register_user,
    unban_user,
    update_user_info,
    update_user_role,
)

async def api_admin_users(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户列表API"""
    users = await get_all_users()

    formatted_users = []
    for user in users:
        formatted_users.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': 'admin' if user['type'] == '管理员' else 'vip' if user['type'] == 'VIP用户' else 'user',
            'created_at': user['registerDate'],
            'last_login': user['lastLogin'],
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
    user = await get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    formatted_user = {
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'role': 'admin' if user['type'] == '管理员' else 'vip' if user['type'] == 'VIP用户' else 'user',
        'created_at': user['registerDate'],
        'last_login': user['lastLogin'],
        'is_banned': user['status'] == '封禁',
        'avatar_url': user['avatar']
    }

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'user': formatted_user}
    })


async def api_admin_users_create(data: UserCreateRequest, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员创建用户API"""
    result = await register_user(data.username, data.email or '', data.password)
    if result['code'] == 200:
        await audit(request, 'user.create', current_user,
                   target_type='user', target_id=(result.get('data') or {}).get('id'),
                   detail=f"新建用户 {data.username}")
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_update(user_id: int, data: UserUpdateRequest, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员更新用户信息（用户名 / 邮箱 / 可选重置密码与角色）"""
    result = await update_user_info(user_id, data.username, data.email)
    if result['code'] != 200:
        return JSONResponse(content=result, status_code=400)

    # 重置密码：管理员操作不需要旧密码，且会注销该用户所有会话
    if data.password:
        pw = await change_password(user_id, data.password, keep_token=None)
        if pw['code'] != 200:
            return JSONResponse(content=pw, status_code=400)

    if data.role:
        # 不允许把自己降级，避免把最后一个管理员锁在门外
        if user_id == current_user['id'] and data.role != 'admin':
            return JSONResponse(
                content={'code': 400, 'msg': '不能修改自己的管理员角色'}, status_code=400
            )
        role_result = await update_user_role(user_id, data.role)
        if role_result['code'] != 200:
            return JSONResponse(content=role_result, status_code=400)

    changed = []
    if data.password:
        changed.append('重置密码')
    if data.role:
        changed.append(f'角色改为 {data.role}')
    await audit(request, 'user.update', current_user,
               target_type='user', target_id=user_id,
               detail=f"修改用户 {data.username}" + (f"（{'、'.join(changed)}）" if changed else ''))

    return JSONResponse(content={'code': 200, 'msg': '用户信息已更新'})


async def api_admin_user_ban(user_id: int, request: Request = None, current_user: dict = Depends(get_current_admin)):
    """管理员封禁用户API"""
    reason = None
    if request:
        try:
            body = await request.json()
            reason = body.get('reason')
        except:
            pass
    result = await ban_user(user_id, reason=reason)
    if result['code'] == 200 and request is not None:
        await audit(request, 'user.ban', current_user,
                   target_type='user', target_id=user_id,
                   detail=f"封禁用户 #{user_id}" + (f"，原因：{reason}" if reason else ''))
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_unban(user_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员解封用户API"""
    result = await unban_user(user_id)
    if result['code'] == 200:
        await audit(request, 'user.unban', current_user,
                   target_type='user', target_id=user_id, detail=f"解封用户 #{user_id}")
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_delete(user_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员删除用户API"""
    # 删之前先记下用户名，否则日志里只剩一个 id
    target = await get_user_by_id(user_id)
    username = (target or {}).get('username') or f'#{user_id}'
    result = await delete_user(user_id)
    if result['code'] == 200:
        await audit(request, 'user.delete', current_user,
                   target_type='user', target_id=user_id, detail=f"删除用户 {username}")
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


# 分类管理API
