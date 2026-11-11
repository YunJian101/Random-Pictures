#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录防爆破
==========

此前登录接口只有「每分钟 N 次」的 IP 限流（middlewares/rate_limit.py），
属于粗粒度的流量阀门：攻击者把速率压到阈值以下，就能长时间慢速撞库；
而且多 worker 下计数在各自进程内，实际上限会被放大 N 倍。

这里补的是**基于失败次数**的账号/IP 双维度锁定，状态落在数据库，
多进程、多实例共享同一份计数：

    账号维度：连续失败 5 次 → 先锁 60s，之后每次翻倍（上限 15 分钟）
    IP  维度：15 分钟内失败 20 次 → 直接锁 15 分钟（防同一来源横扫账号）

成功登录会清掉该账号与来源 IP 的失败记录。
账号键做 sha256 后存储，避免把邮箱/用户名明文再抄一份到这张表里。
"""

import hashlib
from datetime import datetime

from .. import runtime_config
from ..config import (
    LOGIN_IP_MAX_FAILURES,
    LOGIN_LOCK_BASE_SECONDS,
    LOGIN_LOCK_MAX_SECONDS,
    LOGIN_MAX_FAILURES,
    LOGIN_WINDOW_SECONDS,
)
from ..database import get_async_db_connection
from ...utils.utils import execute_count

__all__ = [
    'check_login_allowed',
    'record_login_failure',
    'record_login_success',
    'cleanup_login_attempts',
]

SCOPE_ACCOUNT = 'account'
SCOPE_IP = 'ip'


def _account_key(account: str) -> str:
    """账号键：统一小写后哈希，表里不落明文邮箱"""
    normalized = (account or '').strip().lower().encode('utf-8')
    return hashlib.sha256(normalized).hexdigest()


def _lock_seconds(failures: int, threshold: int) -> int:
    """指数退避：第 threshold 次锁定 base 秒，之后每次翻倍，封顶 max"""
    base = runtime_config.get_int('login_lock_base_seconds', LOGIN_LOCK_BASE_SECONDS)
    ceiling = runtime_config.get_int('login_lock_max_seconds', LOGIN_LOCK_MAX_SECONDS)
    over = max(0, failures - threshold)
    seconds = max(1, base) * (2 ** min(over, 6))
    return min(seconds, max(1, ceiling))


def _retry_after(locked_until, now: datetime) -> int:
    """距离解锁还剩多少秒（向上取整，最小 1）"""
    if not locked_until:
        return 0
    remaining = (locked_until - now).total_seconds()
    return max(1, int(remaining + 0.999)) if remaining > 0 else 0


async def check_login_allowed(account: str, ip: str) -> dict:
    """登录前检查是否处于锁定状态

    返回 {'allowed': bool, 'retry_after': int, 'msg': str}
    """
    await runtime_config.ensure_loaded()
    if not runtime_config.get_bool('enable_login_guard', True):
        return {'allowed': True, 'retry_after': 0, 'msg': ''}

    try:
        async with get_async_db_connection() as conn:
            rows = await conn.fetch('''
                SELECT scope, locked_until FROM login_attempts
                WHERE (scope = $1 AND key = $2) OR (scope = $3 AND key = $4)
            ''', SCOPE_ACCOUNT, _account_key(account), SCOPE_IP, ip or '-')

        now = datetime.now().astimezone()
        locked = [r for r in rows if r['locked_until'] and r['locked_until'] > now]
        if not locked:
            return {'allowed': True, 'retry_after': 0, 'msg': ''}

        # 锁定期内只回剩余时间，不累加失败次数。
        # 如果每次都 bump，用户刷新几下就会 60s→120s→240s 地翻倍，
        # 观感上像「惩罚刷新」，而不是「限制撞库」。
        #
        # 升级逻辑交给「锁定过期后的下一次失败」：那时 _bump 才 +1，
        # failures 从 5 变 6，下一轮锁自然变成 120s。
        wait = max(_retry_after(r['locked_until'], now) for r in locked)
        minutes = max(1, (wait + 59) // 60)
        return {
            'allowed': False,
            'retry_after': wait,
            'msg': f'登录失败次数过多，请在 {minutes} 分钟后重试',
        }

    except Exception as e:
        # 防爆破自身出问题时不能把登录一起拖垮：放行并记日志
        print(f"[WARN] 登录锁定检查失败: {str(e)}")
        return {'allowed': True, 'retry_after': 0, 'msg': ''}


async def _bump(conn, scope: str, key: str, threshold: int) -> dict:
    """失败计数 +1（窗口外自动重置），达到阈值则写锁定时间"""
    row = await conn.fetchrow('''
        INSERT INTO login_attempts (scope, key, failures, window_started_at, updated_at)
        VALUES ($1, $2, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (scope, key) DO UPDATE SET
            failures = CASE
                WHEN login_attempts.window_started_at
                     < CURRENT_TIMESTAMP - make_interval(secs => $3::double precision)
                THEN 1
                ELSE login_attempts.failures + 1
            END,
            window_started_at = CASE
                WHEN login_attempts.window_started_at
                     < CURRENT_TIMESTAMP - make_interval(secs => $3::double precision)
                THEN CURRENT_TIMESTAMP
                ELSE login_attempts.window_started_at
            END,
            updated_at = CURRENT_TIMESTAMP
        RETURNING failures
    ''', scope, key, LOGIN_WINDOW_SECONDS)

    failures = row['failures']
    if failures < threshold:
        return {'failures': failures, 'retry_after': 0, 'remaining': threshold - failures}

    wait = _lock_seconds(failures, threshold)
    await conn.execute('''
        UPDATE login_attempts
        SET locked_until = CURRENT_TIMESTAMP + make_interval(secs => $3::double precision)
        WHERE scope = $1 AND key = $2
    ''', scope, key, wait)

    return {'failures': failures, 'retry_after': wait, 'remaining': 0}


async def record_login_failure(account: str, ip: str) -> dict:
    """记录一次登录失败

    返回 {'retry_after': int, 'remaining': int}
        retry_after > 0 表示本次已触发锁定
        remaining 为距离锁定还可尝试的次数
    """
    try:
        await runtime_config.ensure_loaded()
        # 开关关闭时连计数都不做：否则第 N 次失败仍会写锁并返回 429，
        # 「关掉防爆破」就变成了「只关一半」
        if not runtime_config.get_bool('enable_login_guard', True):
            # remaining = -1 表示「不统计次数」，调用方据此不再提示剩余次数
            return {'retry_after': 0, 'remaining': -1}

        thresholds = (
            runtime_config.get_int('login_max_failures', LOGIN_MAX_FAILURES),
            runtime_config.get_int('login_ip_max_failures', LOGIN_IP_MAX_FAILURES),
        )

        async with get_async_db_connection() as conn:
            acc = await _bump(conn, SCOPE_ACCOUNT, _account_key(account), max(1, thresholds[0]))
            ipr = await _bump(conn, SCOPE_IP, ip or '-', max(1, thresholds[1]))

        return {
            'retry_after': max(acc['retry_after'], ipr['retry_after']),
            'remaining': min(acc['remaining'], ipr['remaining']),
        }

    except Exception as e:
        print(f"[WARN] 记录登录失败次数出错: {str(e)}")
        return {'retry_after': 0, 'remaining': 1}


async def record_login_success(account: str, ip: str) -> None:
    """登录成功：清空该账号与来源 IP 的失败记录"""
    try:
        async with get_async_db_connection() as conn:
            await conn.execute('''
                DELETE FROM login_attempts
                WHERE (scope = $1 AND key = $2) OR (scope = $3 AND key = $4)
            ''', SCOPE_ACCOUNT, _account_key(account), SCOPE_IP, ip or '-')
    except Exception as e:
        print(f"[WARN] 清理登录失败记录出错: {str(e)}")


async def cleanup_login_attempts() -> int:
    """清理已经解锁且窗口早已过期的记录，返回删除条数"""
    try:
        async with get_async_db_connection() as conn:
            return await execute_count(conn, '''
                DELETE FROM login_attempts
                WHERE COALESCE(locked_until, window_started_at)
                      < CURRENT_TIMESTAMP - make_interval(secs => $1::double precision)
            ''', max(LOGIN_WINDOW_SECONDS * 4, 3600))
    except Exception as e:
        print(f"清理登录尝试记录失败: {str(e)}")
        return 0
