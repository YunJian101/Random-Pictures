#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证和授权模块
==============
"""

import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict

from .config import SECRET_KEY, TOKEN_EXPIRE_DAYS
from .database import get_db_connection


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    密码哈希函数（使用SHA-256 + salt）

    返回:
        (password_hash, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return password_hash, salt


def generate_token() -> str:
    """生成随机的session token"""
    return secrets.token_urlsafe(32)


def register_user(username: str, email: str, password: str) -> dict:
    """
    用户注册
    """
    # 验证用户名格式
    username_regex = re.compile(r'^[a-zA-Z0-9_]{3,16}$')
    if not username_regex.match(username):
        return {'code': 400, 'msg': '用户名格式不正确，需为3-16位字母、数字、下划线组合'}

    # 验证邮箱格式
    email_regex = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    if not email_regex.match(email):
        return {'code': 400, 'msg': '请输入有效的邮箱地址'}

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 检查用户名是否已存在
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                return {'code': 400, 'msg': '用户名已存在'}

            # 检查邮箱是否已存在
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                return {'code': 400, 'msg': '邮箱已被注册'}

            # 检查是否是第一个用户
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            role = 'admin' if user_count == 0 else 'user'

            # 哈希密码
            password_hash, salt = hash_password(password)

            # 插入用户数据
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, salt, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, password_hash, salt, role))

            user_id = cursor.lastrowid

            result_data = {
                'id': user_id,
                'username': username,
                'email': email,
                'role': role
            }

            if role == 'admin':
                print(f"🎉 第一个用户注册成功！用户 '{username}' 已自动设置为管理员")

            return {
                'code': 200,
                'msg': '注册成功' + ('（已自动设置为管理员）' if role == 'admin' else ''),
                'data': result_data
            }

    except Exception as e:
        print(f"注册失败: {str(e)}")
        return {'code': 500, 'msg': '注册失败，请稍后重试'}


def login_user(account: str, password: str) -> dict:
    """
    用户登录（支持用户名或邮箱登录）
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, username, email, password_hash, salt, role, status
                FROM users
                WHERE username = ? OR email = ?
            ''', (account, account))

            user = cursor.fetchone()

            if not user:
                return {'code': 401, 'msg': '账号或密码错误'}

            user_id, username, email, stored_hash, salt, role, status = user

            # 检查用户是否被封禁
            if status == 'banned':
                return {'code': 403, 'msg': '账号已被封禁'}

            # 验证密码
            password_hash, _ = hash_password(password, salt)

            if password_hash != stored_hash:
                return {'code': 401, 'msg': '账号或密码错误'}

            # 生成session token
            token = generate_token()
            expires_at = datetime.now() + timedelta(days=TOKEN_EXPIRE_DAYS)

            # 存储session
            cursor.execute('''
                INSERT INTO sessions (token, user_id, username, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (token, user_id, username, expires_at.strftime('%Y-%m-%d %H:%M:%S')))

            # 更新最后登录时间
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))

            return {
                'code': 200,
                'msg': '登录成功' + ('（管理员）' if role == 'admin' else ''),
                'data': {
                    'token': token,
                    'user': {
                        'id': user_id,
                        'username': username,
                        'email': email,
                        'role': role
                    }
                }
            }

    except Exception as e:
        print(f"登录失败: {str(e)}")
        return {'code': 500, 'msg': '登录失败，请稍后重试'}


def verify_session(token: str) -> dict:
    """
    验证session token
    """
    if not token:
        return {'code': 401, 'msg': '未登录'}

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT s.user_id, s.username, s.expires_at, u.email, u.role, u.status
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ?
            ''', (token,))

            session = cursor.fetchone()

            if not session:
                return {'code': 401, 'msg': 'session无效'}

            user_id, username, expires_at_str, email, role, status = session
            expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')

            # 检查是否过期
            if datetime.now() > expires_at:
                cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
                return {'code': 401, 'msg': 'session已过期'}

            # 检查用户是否被封禁
            if status == 'banned':
                return {'code': 403, 'msg': '账号已被封禁'}

            return {
                'code': 200,
                'msg': '验证成功',
                'data': {
                    'user': {
                        'id': user_id,
                        'username': username,
                        'email': email,
                        'role': role
                    }
                }
            }

    except Exception as e:
        print(f"验证session失败: {str(e)}")
        return {'code': 500, 'msg': '验证失败'}


def logout_user(token: str) -> dict:
    """
    用户登出
    """
    if not token:
        return {'code': 400, 'msg': '未登录'}

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
            return {'code': 200, 'msg': '登出成功'}

    except Exception as e:
        print(f"登出失败: {str(e)}")
        return {'code': 500, 'msg': '登出失败'}


def cleanup_expired_sessions() -> int:
    """清理过期的session"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP')
            deleted = cursor.rowcount
            return deleted
    except Exception as e:
        print(f"清理过期session失败: {str(e)}")
        return 0


def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    根据用户ID获取用户详细信息
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, username, email, role, created_at, last_login, status
                FROM users
                WHERE id = ?
            ''', (user_id,))

            user = cursor.fetchone()

            if not user:
                return None

            user_id, username, email, role, created_at, last_login, status = user

            # 生成用户ID显示格式
            user_display_id = f"U{created_at.replace('-', '').replace(':', '').replace(' ', '')[:12]}"

            # 判断用户状态
            display_status = '封禁' if status == 'banned' else ('活跃' if last_login else '未登录')

            # 格式化注册时间
            try:
                register_date = created_at.split()[0]
            except:
                register_date = created_at

            # 最后登录时间
            last_login_time = last_login.split()[1][:5] if last_login else '-'

            return {
                'id': user_id,
                'userId': user_display_id,
                'username': username,
                'email': email,
                'avatar': f"https://ui-avatars.com/api/?name={username}&background=random",
                'type': '管理员' if role == 'admin' else 'VIP用户' if role == 'vip' else '普通用户',
                'status': display_status,
                'registerDate': register_date,
                'lastLogin': last_login_time
            }

    except Exception as e:
        print(f"获取用户详情失败: {str(e)}")
        return None


def get_all_users() -> list:
    """
    获取所有用户信息（管理员专用）
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT u.id, u.username, u.email, u.role, u.created_at, u.last_login, u.status
                FROM users u
                ORDER BY u.created_at DESC
            ''')

            users = cursor.fetchall()

            user_list = []
            for user in users:
                user_id, username, email, role, created_at, last_login, status = user

                user_display_id = f"U{created_at.replace('-', '').replace(':', '').replace(' ', '')[:12]}"
                display_status = '封禁' if status == 'banned' else ('活跃' if last_login else '未登录')

                try:
                    register_date = created_at.split()[0]
                except:
                    register_date = created_at

                last_login_time = last_login.split()[1][:5] if last_login else '-'

                user_list.append({
                    'id': user_id,
                    'userId': user_display_id,
                    'username': username,
                    'email': email,
                    'avatar': f"https://ui-avatars.com/api/?name={username}&background=random",
                    'type': '管理员' if role == 'admin' else 'VIP用户' if role == 'vip' else '普通用户',
                    'registerDate': register_date,
                    'lastLogin': last_login_time,
                    'status': display_status
                })

            return user_list

    except Exception as e:
        print(f"获取用户列表失败: {str(e)}")
        return []


def update_user_info(user_id: int, username: str, email: Optional[str] = None) -> dict:
    """
    更新用户信息
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            updates = []
            params = []

            updates.append("username = ?")
            params.append(username)

            if email is not None:
                updates.append("email = ?")
                params.append(email)

            params.append(user_id)

            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)

            if cursor.rowcount == 0:
                return {'code': 404, 'msg': '用户不存在'}

            return {'code': 200, 'msg': '用户信息更新成功'}

    except Exception as e:
        print(f"更新用户信息失败: {str(e)}")
        return {'code': 500, 'msg': '更新失败'}


def ban_user(user_id: int) -> dict:
    """
    封禁用户
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE users
                SET status = 'banned', banned_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (user_id,))

            if cursor.rowcount == 0:
                return {'code': 404, 'msg': '用户不存在'}

            # 删除该用户的session
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))

            return {'code': 200, 'msg': '用户封禁成功'}

    except Exception as e:
        print(f"封禁用户失败: {str(e)}")
        return {'code': 500, 'msg': '封禁失败'}


def unban_user(user_id: int) -> dict:
    """
    解封用户
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE users
                SET status = 'active', banned_at = NULL
                WHERE id = ?
            ''', (user_id,))

            if cursor.rowcount == 0:
                return {'code': 404, 'msg': '用户不存在'}

            return {'code': 200, 'msg': '用户解封成功'}

    except Exception as e:
        print(f"解封用户失败: {str(e)}")
        return {'code': 500, 'msg': '解封失败'}


def delete_user(user_id: int) -> dict:
    """
    删除用户及其相关数据
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('BEGIN TRANSACTION')

            # 删除用户的session
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))

            # 删除用户
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))

            if cursor.rowcount == 0:
                conn.rollback()
                return {'code': 404, 'msg': '用户不存在'}

            return {'code': 200, 'msg': '用户删除成功'}

    except Exception as e:
        print(f"删除用户失败: {str(e)}")
        return {'code': 500, 'msg': '删除失败'}


def update_user_role(user_id: int, new_role: str) -> dict:
    """
    更新用户角色
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))

            if cursor.rowcount == 0:
                return {'code': 404, 'msg': '用户不存在'}

            return {'code': 200, 'msg': '用户角色更新成功'}

    except Exception as e:
        print(f"更新用户角色失败: {str(e)}")
        return {'code': 500, 'msg': '更新失败'}
