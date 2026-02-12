#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员路由模块
处理管理员相关的API请求
"""

from fastapi import Depends, Request, HTTPException, Body
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
    user = get_user_by_id(user_id)

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


async def api_admin_user_ban(user_id: int, request: Request = None, current_user: dict = Depends(get_current_admin)):
    """管理员封禁用户API"""
    reason = None
    if request:
        try:
            body = await request.json()
            reason = body.get('reason')
        except:
            pass
    result = ban_user(user_id, reason=reason)
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
    # 检查是否已存在管理员
    from backend.database import get_db_connection
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = %s', ('admin',))
            admin_count = cursor.fetchone()[0]
            
            if admin_count > 0:
                return JSONResponse(content={
                    'code': 403,
                    'msg': '管理员账户已存在，此接口已禁用'
                }, status_code=403)
    except Exception as e:
        print(f"检查管理员账户时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '检查管理员账户时发生错误'
        }, status_code=500)

    # 继续原有逻辑
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


# 分类管理API
async def api_admin_create_category(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员创建分类API"""
    from ..database import get_db_connection
    
    try:
        data = await request.json()
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return JSONResponse(content={
                'code': 400,
                'msg': '分类名称不能为空'
            }, status_code=400)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 检查分类名称是否已存在
            cursor.execute('SELECT id FROM categories WHERE name = %s', (name,))
            if cursor.fetchone():
                return JSONResponse(content={
                    'code': 400,
                    'msg': '分类名称已存在'
                }, status_code=400)
            
            # 创建分类
            cursor.execute('''
                INSERT INTO categories (name, description) 
                VALUES (%s, %s) 
                RETURNING id, name, description, status, created_at, updated_at
            ''', (name, description))
            
            category = cursor.fetchone()
            
            return JSONResponse(content={
                'code': 200,
                'msg': '分类创建成功',
                'data': {
                    'id': category[0],
                    'name': category[1],
                    'description': category[2],
                    'status': category[3],
                    'created_at': category[4].isoformat(),
                    'updated_at': category[5].isoformat()
                }
            })
    except Exception as e:
        print(f"[ERROR] 创建分类时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '创建分类时发生错误'
        }, status_code=500)


async def api_admin_update_category(category_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员更新分类API"""
    from ..database import get_db_connection
    
    try:
        data = await request.json()
        name = data.get('name')
        description = data.get('description')
        status = data.get('status')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 检查分类是否存在
            cursor.execute('SELECT id FROM categories WHERE id = %s', (category_id,))
            if not cursor.fetchone():
                return JSONResponse(content={
                    'code': 404,
                    'msg': '分类不存在'
                }, status_code=404)
            
            # 检查分类名称是否已被其他分类使用
            if name:
                cursor.execute('SELECT id FROM categories WHERE name = %s AND id != %s', (name, category_id))
                if cursor.fetchone():
                    return JSONResponse(content={
                        'code': 400,
                        'msg': '分类名称已存在'
                    }, status_code=400)
            
            # 构建更新语句
            update_fields = []
            update_values = []
            
            if name is not None:
                update_fields.append('name = %s')
                update_values.append(name)
            if description is not None:
                update_fields.append('description = %s')
                update_values.append(description)
            if status is not None:
                update_fields.append('status = %s')
                update_values.append(status)
            
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(category_id)
            
            # 执行更新
            cursor.execute(f'''
                UPDATE categories 
                SET {', '.join(update_fields)} 
                WHERE id = %s 
                RETURNING id, name, description, status, created_at, updated_at
            ''', update_values)
            
            category = cursor.fetchone()
            
            return JSONResponse(content={
                'code': 200,
                'msg': '分类更新成功',
                'data': {
                    'id': category[0],
                    'name': category[1],
                    'description': category[2],
                    'status': category[3],
                    'created_at': category[4].isoformat(),
                    'updated_at': category[5].isoformat()
                }
            })
    except Exception as e:
        print(f"[ERROR] 更新分类时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '更新分类时发生错误'
        }, status_code=500)


async def api_admin_delete_category(category_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员删除分类API"""
    from ..database import get_db_connection
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 检查分类是否存在
            cursor.execute('SELECT id FROM categories WHERE id = %s', (category_id,))
            if not cursor.fetchone():
                return JSONResponse(content={
                    'code': 404,
                    'msg': '分类不存在'
                }, status_code=404)
            
            # 删除分类
            cursor.execute('DELETE FROM categories WHERE id = %s', (category_id,))
            
            return JSONResponse(content={
                'code': 200,
                'msg': '分类删除成功'
            })
    except Exception as e:
        print(f"[ERROR] 删除分类时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '删除分类时发生错误'
        }, status_code=500)
