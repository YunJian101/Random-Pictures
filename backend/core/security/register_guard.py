#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
注册防批量
==========

限流中间件只能管「每分钟多少次请求」，挡不住脚本把节奏放慢后批量注册：
每分钟 5 次，一小时就是 300 个账号。注册和登录不一样——注册是**不可逆的资源消耗**
（占用户名、占邮箱、进用户表），所以单独按 IP 做配额：

    同一 IP 在窗口期内最多注册 N 个账号（默认 5 个 / 小时）
    两次注册之间至少间隔 M 秒（默认 30 秒）
    超限后锁到本窗口结束

状态落库（register_attempts 表），多 worker 共享同一份计数。
配额与窗口都能在管理后台「系统设置」里改。
"""

from datetime import datetime

from .. import runtime_config
from ..config import (
    REGISTER_MAX_PER_WINDOW,
    REGISTER_MIN_INTERVAL_SECONDS,
    REGISTER_WINDOW_SECONDS,
)
from ..database import get_async_db_connection
from ...utils.utils import execute_count

__all__ = ['check_register_allowed', 'record_register', 'cleanup_register_attempts']


async def check_register_allowed(ip: str) -> dict:
    """注册前检查：是否超配额 / 间隔太短

    返回 {'allowed': bool, 'retry_after': int, 'msg': str}
    """
    try:
        await runtime_config.ensure_loaded()
        if not runtime_config.get_bool('enable_register_guard', True):
            return {'allowed': True, 'retry_after': 0, 'msg': ''}

        key = ip or '-'

        async with get_async_db_connection() as conn:
            row = await conn.fetchrow(
                'SELECT count, window_started_at, locked_until FROM register_attempts WHERE ip = $1',
                key,
            )

        if not row:
            return {'allowed': True, 'retry_after': 0, 'msg': ''}

        now = datetime.now().astimezone()
        window = max(60, runtime_config.get_int('register_window_seconds', REGISTER_WINDOW_SECONDS))

        # 窗口已过：计数作废，放行
        if row['window_started_at'] and (now - row['window_started_at']).total_seconds() >= window:
            return {'allowed': True, 'retry_after': 0, 'msg': ''}

        if row['locked_until'] and row['locked_until'] > now:
            wait = max(1, int((row['locked_until'] - now).total_seconds() + 0.999))
            minutes = max(1, (wait + 59) // 60)
            return {
                'allowed': False,
                'retry_after': wait,
                'msg': f'该网络注册过于频繁，请在 {minutes} 分钟后重试',
            }

        # 间隔限制：防同一 IP 连续秒注
        min_interval = max(0, runtime_config.get_int(
            'register_min_interval_seconds', REGISTER_MIN_INTERVAL_SECONDS
        ))
        if min_interval and row['window_started_at']:
            elapsed = (now - row['window_started_at']).total_seconds()
            if row['count'] and elapsed < min_interval:
                wait = int(min_interval - elapsed) + 1
                return {
                    'allowed': False,
                    'retry_after': wait,
                    'msg': f'注册太频繁，请 {wait} 秒后再试',
                }

        return {'allowed': True, 'retry_after': 0, 'msg': ''}

    except Exception as e:
        # 守卫自身故障不能把注册功能整个拦死
        print(f'[WARN] 注册配额检查失败: {str(e)}')
        return {'allowed': True, 'retry_after': 0, 'msg': ''}


async def record_register(ip: str) -> dict:
    """记录一次成功注册，返回 {'count': int, 'locked': bool}"""
    try:
        await runtime_config.ensure_loaded()
        if not runtime_config.get_bool('enable_register_guard', True):
            return {'allowed': True, 'retry_after': 0, 'msg': ''}

        key = ip or '-'
        window = max(60, runtime_config.get_int('register_window_seconds', REGISTER_WINDOW_SECONDS))
        quota = max(1, runtime_config.get_int('register_max_per_window', REGISTER_MAX_PER_WINDOW))

        async with get_async_db_connection() as conn:
            row = await conn.fetchrow('''
                INSERT INTO register_attempts (ip, count, window_started_at, updated_at)
                VALUES ($1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (ip) DO UPDATE SET
                    count = CASE
                        WHEN register_attempts.window_started_at
                             < CURRENT_TIMESTAMP - make_interval(secs => $2::double precision)
                        THEN 1
                        ELSE register_attempts.count + 1
                    END,
                    window_started_at = CASE
                        WHEN register_attempts.window_started_at
                             < CURRENT_TIMESTAMP - make_interval(secs => $2::double precision)
                        THEN CURRENT_TIMESTAMP
                        ELSE register_attempts.window_started_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING count, window_started_at
            ''', key, window)

            count = row['count']
            locked = count >= quota

            if locked:
                # 锁到窗口结束，别让攻击者「下一秒再来一次」
                await conn.execute('''
                    UPDATE register_attempts
                    SET locked_until = window_started_at + make_interval(secs => $2::double precision)
                    WHERE ip = $1
                ''', key, window)

        return {'count': count, 'locked': locked, 'quota': quota}

    except Exception as e:
        print(f'[WARN] 记录注册配额失败: {str(e)}')
        return {'count': 0, 'locked': False, 'quota': 0}


async def cleanup_register_attempts() -> int:
    """清理早已过窗口且未锁定的记录"""
    try:
        await runtime_config.ensure_loaded()
        window = max(60, runtime_config.get_int('register_window_seconds', REGISTER_WINDOW_SECONDS))
        async with get_async_db_connection() as conn:
            return await execute_count(conn, '''
                DELETE FROM register_attempts
                WHERE COALESCE(locked_until, window_started_at)
                      < CURRENT_TIMESTAMP - make_interval(secs => $1::double precision)
            ''', window * 2)
    except Exception as e:
        print(f'[WARN] 清理注册配额记录失败: {str(e)}')
        return 0
