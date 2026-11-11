#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户领域服务
============

注册、登录、资料、封禁、删除这些「用户生命周期」操作集中在这里。
会话与密码的细节分别委托给 core.security.session / core.security.password，
本模块不直接碰 token 生成和哈希算法。

返回值统一沿用项目约定：{'code': int, 'msg': str, 'data'?: dict}
"""

import re
from typing import Optional

from ..core.database import get_async_db_connection
from ..core.security import login_guard
from ..core.security.password import hash_password, verify_password
from ..core.security.session import (
    cleanup_if_due,
    create_session,
    revoke_user_sessions,
)
from ..utils.utils import execute_count

__all__ = [
    'register_user',
    'login_user',
    'get_user_by_id',
    'get_all_users',
    'update_user_info',
    'verify_user_password',
    'change_password',
    'ban_user',
    'unban_user',
    'delete_user',
    'update_user_role',
]

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,16}$')
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

ROLE_LABELS = {'admin': '管理员', 'vip': 'VIP用户'}
AVATAR_TEMPLATE = 'https://ui-avatars.com/api/?name={name}&background=random'


def _iso(value) -> str:
    """datetime → ISO 字符串，取不到就给空串"""
    if not value:
        return ''
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _role_label(role: str) -> str:
    return ROLE_LABELS.get(role, '普通用户')


def _display_status(status: str, last_login) -> str:
    if status == 'banned':
        return '封禁'
    return '活跃' if last_login else '未登录'


def _format_user_row(row) -> dict:
    """把 users 行格式化成前端用的字段（列表/详情共用，避免两份重复实现）"""
    username = row['username']
    return {
        'id': row['id'],
        'username': username,
        'email': row['email'],
        'avatar': AVATAR_TEMPLATE.format(name=username),
        'type': _role_label(row['role']),
        'status': _display_status(row['status'], row['last_login']),
        'registerDate': _iso(row['created_at']),
        'lastLogin': _iso(row['last_login']),
    }


async def register_user(username: str, email: str, password: str) -> dict:
    """用户注册（第一个注册的账号自动成为管理员）"""
    if not USERNAME_RE.match(username or ''):
        return {'code': 400, 'msg': '用户名格式不正确，需为3-16位字母、数字、下划线组合'}

    if not EMAIL_RE.match(email or ''):
        return {'code': 400, 'msg': '请输入有效的邮箱地址'}

    try:
        async with get_async_db_connection() as conn:
            if await conn.fetchrow('SELECT id FROM users WHERE username = $1', username):
                return {'code': 400, 'msg': '用户名已存在'}

            if await conn.fetchrow('SELECT id FROM users WHERE email = $1', email):
                return {'code': 400, 'msg': '邮箱已被注册'}

            user_count = await conn.fetchval('SELECT COUNT(*) FROM users')
            role = 'admin' if user_count == 0 else 'user'

            password_hash, salt = hash_password(password)
            user_id = await conn.fetchval('''
                INSERT INTO users (username, email, password_hash, salt, role)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            ''', username, email, password_hash, salt, role)

        if role == 'admin':
            print(f"🎉 第一个用户注册成功！用户 '{username}' 已自动设置为管理员")

        return {
            'code': 200,
            'msg': '注册成功' + ('（已自动设置为管理员）' if role == 'admin' else ''),
            'data': {'id': user_id, 'username': username, 'email': email, 'role': role},
        }

    except Exception as e:
        print(f"注册失败: {str(e)}")
        return {'code': 500, 'msg': '注册失败，请稍后重试'}


async def login_user(account: str, password: str, ip: str = '-', user_agent: str = '') -> dict:
    """登录（支持用户名或邮箱）

    锁定/计数逻辑见 core/security/login_guard.py；触发锁定时返回 code=429
    并带上 retry_after，由路由层写进 Retry-After 响应头。
    """
    try:
        guard = await login_guard.check_login_allowed(account, ip)
        if not guard['allowed']:
            return {
                'code': 429,
                'msg': guard['msg'],
                'retry_after': guard['retry_after'],
            }

        async with get_async_db_connection() as conn:
            user = await conn.fetchrow('''
                SELECT id, username, email, password_hash, salt, role, status
                FROM users
                WHERE username = $1 OR email = $1
            ''', account)

        # 账号不存在也走一次「失败计数」，让两种失败路径在耗时与提示上无法区分
        if not user:
            failure = await login_guard.record_login_failure(account, ip)
            return _fail_response(failure)

        if user['status'] == 'banned':
            return {'code': 403, 'msg': '账号已被封禁'}

        if not verify_password(password, user['password_hash'], user['salt']):
            failure = await login_guard.record_login_failure(account, ip)
            return _fail_response(failure)

        await login_guard.record_login_success(account, ip)

        async with get_async_db_connection() as conn:
            token, _ = await create_session(conn, user['id'], user['username'], ip=ip, user_agent=user_agent)
            await conn.execute(
                'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = $1', user['id']
            )

        # 顺带做一次过期会话清理（内部有节流，不会每次登录都扫表）
        await cleanup_if_due()

        return {
            'code': 200,
            'msg': '登录成功' + ('（管理员）' if user['role'] == 'admin' else ''),
            'data': {
                'token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'role': user['role'],
                },
            },
        }

    except Exception as e:
        print(f"登录失败: {str(e)}")
        return {'code': 500, 'msg': '登录失败，请稍后重试'}


def _fail_response(failure: dict) -> dict:
    """密码错误 / 账号不存在 的统一返回；带上剩余次数或锁定信息"""
    if failure['retry_after'] > 0:
        minutes = max(1, (failure['retry_after'] + 59) // 60)
        return {
            'code': 429,
            'msg': f'登录失败次数过多，请在 {minutes} 分钟后重试',
            'retry_after': failure['retry_after'],
        }

    remaining = failure.get('remaining', 0)
    hint = f'，还可尝试 {remaining} 次' if remaining > 0 else ''
    return {'code': 401, 'msg': f'账号或密码错误{hint}'}


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """按 ID 取用户详情（管理员接口用）"""
    try:
        async with get_async_db_connection() as conn:
            row = await conn.fetchrow('''
                SELECT id, username, email, role, created_at, last_login, status
                FROM users WHERE id = $1
            ''', user_id)

        return _format_user_row(row) if row else None

    except Exception as e:
        print(f"获取用户详情失败: {str(e)}")
        return None


async def get_all_users() -> list:
    """取全部用户（管理员接口用）"""
    try:
        async with get_async_db_connection() as conn:
            rows = await conn.fetch('''
                SELECT u.id, u.username, u.email, u.role, u.created_at, u.last_login, u.status
                FROM users u
                ORDER BY u.created_at DESC
            ''')

        return [_format_user_row(row) for row in rows]

    except Exception as e:
        print(f"获取用户列表失败: {str(e)}")
        return []


async def update_user_info(user_id: int, username: str, email: Optional[str] = None) -> dict:
    """更新用户名 / 邮箱（先做唯一性校验，避免撞约束只抛 500）"""
    try:
        async with get_async_db_connection() as conn:
            taken = await conn.fetchrow(
                'SELECT id FROM users WHERE username = $1 AND id <> $2', username, user_id
            )
            if taken:
                return {'code': 400, 'msg': '用户名已被占用'}

            updates = ['username = $1']
            params = [username]

            if email:
                taken_email = await conn.fetchrow(
                    'SELECT id FROM users WHERE email = $1 AND id <> $2', email, user_id
                )
                if taken_email:
                    return {'code': 400, 'msg': '邮箱已被其他账号使用'}
                params.append(email)
                updates.append(f'email = ${len(params)}')

            params.append(user_id)
            affected = await execute_count(
                conn,
                f"UPDATE users SET {', '.join(updates)} WHERE id = ${len(params)}",
                *params,
            )

        if affected == 0:
            return {'code': 404, 'msg': '用户不存在'}
        return {'code': 200, 'msg': '用户信息更新成功'}

    except Exception as e:
        print(f"更新用户信息失败: {str(e)}")
        return {'code': 500, 'msg': '更新失败'}


async def verify_user_password(user_id: int, password: str) -> bool:
    """校验某个用户的密码是否正确"""
    try:
        async with get_async_db_connection() as conn:
            row = await conn.fetchrow(
                'SELECT password_hash, salt FROM users WHERE id = $1', user_id
            )
        if not row:
            return False
        return verify_password(password, row['password_hash'], row['salt'])
    except Exception as e:
        print(f"校验密码失败: {str(e)}")
        return False


async def change_password(user_id: int, new_password: str, keep_token: Optional[str] = None) -> dict:
    """改密码，并把该用户其它会话全部注销（保留当前这一个）"""
    try:
        password_hash, salt = hash_password(new_password)

        async with get_async_db_connection() as conn:
            affected = await execute_count(conn, '''
                UPDATE users SET password_hash = $1, salt = $2 WHERE id = $3
            ''', password_hash, salt, user_id)

            if affected == 0:
                return {'code': 404, 'msg': '用户不存在'}

            await revoke_user_sessions(conn, user_id, keep_token)

        return {'code': 200, 'msg': '密码修改成功'}

    except Exception as e:
        print(f"修改密码失败: {str(e)}")
        return {'code': 500, 'msg': '密码修改失败'}


async def ban_user(user_id: int, reason: str = None) -> dict:
    """封禁用户并踢下线"""
    try:
        async with get_async_db_connection() as conn:
            if reason:
                affected = await execute_count(conn, '''
                    UPDATE users
                    SET status = 'banned', banned_at = CURRENT_TIMESTAMP, ban_reason = $1
                    WHERE id = $2
                ''', reason, user_id)
            else:
                affected = await execute_count(conn, '''
                    UPDATE users
                    SET status = 'banned', banned_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                ''', user_id)

            if affected == 0:
                return {'code': 404, 'msg': '用户不存在'}

            await revoke_user_sessions(conn, user_id)

        return {'code': 200, 'msg': '用户封禁成功'}

    except Exception as e:
        print(f"封禁用户失败: {str(e)}")
        return {'code': 500, 'msg': '封禁失败'}


async def unban_user(user_id: int) -> dict:
    """解封用户"""
    try:
        async with get_async_db_connection() as conn:
            affected = await execute_count(conn, '''
                UPDATE users SET status = 'active', banned_at = NULL WHERE id = $1
            ''', user_id)

        if affected == 0:
            return {'code': 404, 'msg': '用户不存在'}
        return {'code': 200, 'msg': '用户解封成功'}

    except Exception as e:
        print(f"解封用户失败: {str(e)}")
        return {'code': 500, 'msg': '解封失败'}


async def delete_user(user_id: int) -> dict:
    """删除用户及其关联数据（反馈先删，否则外键拦着）"""
    try:
        async with get_async_db_connection() as conn:
            await conn.execute('DELETE FROM feedbacks WHERE user_id = $1', user_id)
            await revoke_user_sessions(conn, user_id)
            affected = await execute_count(conn, 'DELETE FROM users WHERE id = $1', user_id)

        if affected == 0:
            return {'code': 404, 'msg': '用户不存在'}
        return {'code': 200, 'msg': '用户删除成功'}

    except Exception as e:
        print(f"删除用户失败: {str(e)}")
        return {'code': 500, 'msg': '删除失败'}


async def update_user_role(user_id: int, new_role: str) -> dict:
    """更新用户角色"""
    try:
        async with get_async_db_connection() as conn:
            affected = await execute_count(
                conn, 'UPDATE users SET role = $1 WHERE id = $2', new_role, user_id
            )

        if affected == 0:
            return {'code': 404, 'msg': '用户不存在'}
        return {'code': 200, 'msg': '用户角色更新成功'}

    except Exception as e:
        print(f"更新用户角色失败: {str(e)}")
        return {'code': 500, 'msg': '更新失败'}
