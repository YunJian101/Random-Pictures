#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话（sessions 表）
===================

这里只处理「登录凭证」本身：签发、校验、注销、清理。

关于 sessions 表只增不减的问题，本模块从三个层面兜住：
1. 校验时发现过期 → 立即删除该条；
2. 登录签发新会话时，顺手把该用户的历史会话裁剪到上限（默认 10 个），
   避免同一账号长期反复登录把表撑大；
3. 全局过期清理由 cleanup_expired_sessions() 负责，启动时跑一次、
   之后由 core.tasks.cleanup_loop 定时调用（见 backend/core/tasks.py）。

清理必须靠数据库而不是进程内字典：生产是多 worker 的，每个进程只认识自己
签发的那部分 token。
"""

import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

from .. import runtime_config
from ..config import MAX_SESSIONS_PER_USER, TOKEN_EXPIRE_DAYS
from ..database import get_async_db_connection
from ...utils.utils import execute_count

__all__ = [
    'generate_token',
    'create_session',
    'verify_session',
    'logout_user',
    'revoke_user_sessions',
    'cleanup_expired_sessions',
    'cleanup_if_due',
]

TOKEN_BYTES = 32

# 登录时顺带清理的节流：同一进程 60 秒内最多触发一次，避免每次登录都扫表
_opportunistic_cleanup_at = 0.0
OPPORTUNISTIC_CLEANUP_INTERVAL = 60.0


def generate_token() -> str:
    """生成随机的 session token"""
    return secrets.token_urlsafe(TOKEN_BYTES)


async def _prune_user_sessions(conn, user_id: int) -> int:
    """把同一用户超过上限的旧会话删掉，只保留最新的 N 条"""
    await runtime_config.ensure_loaded()
    limit = max(1, runtime_config.get_int('max_sessions_per_user', MAX_SESSIONS_PER_USER))
    return await execute_count(conn, '''
        DELETE FROM sessions
        WHERE user_id = $1
          AND token NOT IN (
              SELECT token FROM sessions
              WHERE user_id = $1
              ORDER BY created_at DESC
              LIMIT $2
          )
    ''', user_id, limit)


async def create_session(conn, user_id: int, username: str, ip: str = '', user_agent: str = '') -> tuple[str, datetime]:
    """签发会话，返回 (token, expires_at)

    调用方传入连接，便于和「更新 last_login」放在同一连接里完成。
    """
    token = generate_token()
    expires_at = datetime.now() + timedelta(days=TOKEN_EXPIRE_DAYS)

    await conn.execute('''
        INSERT INTO sessions (token, user_id, username, expires_at, ip, user_agent, last_seen)
        VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
    ''', token, user_id, username, expires_at, ip or None, (user_agent or '')[:200] or None)

    # 单用户会话数封顶，防止有人反复登录把表堆满
    try:
        await _prune_user_sessions(conn, user_id)
    except Exception as e:
        print(f"[WARN] 裁剪历史会话失败: {str(e)}")

    return token, expires_at


async def verify_session(token: str) -> dict:
    """校验 session token"""
    if not token:
        return {'code': 401, 'msg': '未登录'}

    try:
        async with get_async_db_connection() as conn:
            session = await conn.fetchrow('''
                SELECT s.user_id, s.username, s.expires_at, u.email, u.role, u.status
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = $1
            ''', token)

            if not session:
                return {'code': 401, 'msg': 'session无效'}

            expires_at = session['expires_at']
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)

            if datetime.now().astimezone() > expires_at:
                await conn.execute('DELETE FROM sessions WHERE token = $1', token)
                return {'code': 401, 'msg': 'session已过期'}

            if session['status'] == 'banned':
                return {'code': 403, 'msg': '账号已被封禁'}

            # 顺带刷新「最近活跃」：只在超过 5 分钟没更新时才写，避免每个请求都 UPDATE
            try:
                await conn.execute('''
                    UPDATE sessions SET last_seen = CURRENT_TIMESTAMP
                    WHERE token = $1
                      AND (last_seen IS NULL OR last_seen < CURRENT_TIMESTAMP - INTERVAL '5 minutes')
                ''', token)
            except Exception:
                pass

            return {
                'code': 200,
                'msg': '验证成功',
                'data': {
                    'user': {
                        'id': session['user_id'],
                        'username': session['username'],
                        'email': session['email'],
                        'role': session['role'],
                    }
                },
            }

    except Exception as e:
        print(f"验证session失败: {str(e)}")
        return {'code': 500, 'msg': '验证失败'}


async def logout_user(token: str) -> dict:
    """登出：删掉当前这一条会话"""
    if not token:
        return {'code': 400, 'msg': '未登录'}

    try:
        async with get_async_db_connection() as conn:
            await conn.execute('DELETE FROM sessions WHERE token = $1', token)
        return {'code': 200, 'msg': '登出成功'}
    except Exception as e:
        print(f"登出失败: {str(e)}")
        return {'code': 500, 'msg': '登出失败'}


async def revoke_user_sessions(conn, user_id: int, keep_token: Optional[str] = None) -> None:
    """注销某个用户的全部会话（keep_token 用于「改密码后保留当前登录」）"""
    if keep_token:
        await conn.execute(
            'DELETE FROM sessions WHERE user_id = $1 AND token <> $2', user_id, keep_token
        )
    else:
        await conn.execute('DELETE FROM sessions WHERE user_id = $1', user_id)


async def cleanup_expired_sessions() -> int:
    """清理所有已过期的会话，返回删除条数"""
    global _opportunistic_cleanup_at

    try:
        async with get_async_db_connection() as conn:
            removed = await execute_count(
                conn, 'DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP'
            )
        _opportunistic_cleanup_at = time.monotonic()
        return removed
    except Exception as e:
        print(f"清理过期session失败: {str(e)}")
        return 0


async def cleanup_if_due() -> int:
    """登录路径上的「顺手清理」：按间隔节流，失败不影响登录"""
    global _opportunistic_cleanup_at

    if time.monotonic() - _opportunistic_cleanup_at < OPPORTUNISTIC_CLEANUP_INTERVAL:
        return 0
    _opportunistic_cleanup_at = time.monotonic()

    try:
        async with get_async_db_connection() as conn:
            return await execute_count(
                conn, 'DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP'
            )
    except Exception:
        return 0
