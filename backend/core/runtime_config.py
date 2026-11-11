#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行时配置
==========

有些参数必须「改完立刻生效」，不能靠重启：限流阈值、登录锁定策略、会话上限。
它们存在 system_configs 表里，由管理后台读写；环境变量只作为**出厂默认值**。

缓存策略：
- 进程内缓存一份快照，默认 5 秒过期，避免每个请求都查库；
- 更新配置的接口会调用 invalidate()，本进程立即失效；
- 多 worker 场景下，其它进程最多晚 5 秒看到新值，够用了。

读不到库（启动早期 / 数据库抖动）时一律回落到环境变量默认值，
保证「配置系统坏了也不会把服务带崩」。
"""

import time
from typing import Optional

from .config import (
    LOGIN_IP_MAX_FAILURES,
    LOGIN_LOCK_BASE_SECONDS,
    LOGIN_LOCK_MAX_SECONDS,
    LOGIN_MAX_FAILURES,
    MAX_SESSIONS_PER_USER,
    MAX_UPLOAD_MB,
    RATE_LIMIT_AUTH_PER_MINUTE,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_PER_MINUTE,
    REGISTER_GUARD_ENABLED,
    REGISTER_MAX_PER_WINDOW,
    REGISTER_MIN_INTERVAL_SECONDS,
    REGISTER_WINDOW_SECONDS,
    SESSION_CLEANUP_INTERVAL,
    SITE_LAUNCH_DATE,
    TRUST_PROXY,
)

__all__ = [
    'DEFAULTS',
    'ensure_loaded',
    'get',
    'get_bool',
    'get_int',
    'invalidate',
]

# 出厂默认值：环境变量 > 代码默认
DEFAULTS: dict[str, str] = {
    'enable_rate_limit': 'true' if RATE_LIMIT_ENABLED else 'false',
    'rate_limit_per_minute': str(RATE_LIMIT_PER_MINUTE),
    'rate_limit_auth_per_minute': str(RATE_LIMIT_AUTH_PER_MINUTE),
    'enable_login_guard': 'true',
    'login_max_failures': str(LOGIN_MAX_FAILURES),
    'login_ip_max_failures': str(LOGIN_IP_MAX_FAILURES),
    'login_lock_base_seconds': str(LOGIN_LOCK_BASE_SECONDS),
    'login_lock_max_seconds': str(LOGIN_LOCK_MAX_SECONDS),
    'max_sessions_per_user': str(MAX_SESSIONS_PER_USER),
    'session_cleanup_interval': str(SESSION_CLEANUP_INTERVAL),
    'audit_retention_days': '90',
    'max_upload_mb': str(MAX_UPLOAD_MB),
    'trust_proxy': 'true' if TRUST_PROXY else 'false',
    'site_launch_date': SITE_LAUNCH_DATE,
    'enable_register_guard': 'true' if REGISTER_GUARD_ENABLED else 'false',
    'register_max_per_window': str(REGISTER_MAX_PER_WINDOW),
    'register_window_seconds': str(REGISTER_WINDOW_SECONDS),
    'register_min_interval_seconds': str(REGISTER_MIN_INTERVAL_SECONDS),
}

CACHE_TTL = 5.0

_values: dict[str, str] = {}
_loaded_at = 0.0
_last_attempt = 0.0
_failed = False
_warned = False


def invalidate() -> None:
    """让本进程的缓存立即失效（更新配置后调用）"""
    global _loaded_at, _values, _failed
    _values = {}
    _loaded_at = 0.0
    _failed = False


async def ensure_loaded(force: bool = False) -> dict:
    """按需从 system_configs 拉一次快照"""
    global _loaded_at, _values, _last_attempt, _failed, _warned

    now = time.monotonic()

    if not force:
        if _values and (now - _loaded_at) < CACHE_TTL:
            return _values
        # 上次查库失败：同样按 TTL 退避，避免数据库抖动时每个请求都去撞一次
        if _failed and (now - _last_attempt) < CACHE_TTL:
            return _values

    _last_attempt = now

    try:
        # 延迟导入，避免 core.runtime_config ← core.database ← ... 的循环
        from .database import get_async_db_connection

        async with get_async_db_connection() as conn:
            rows = await conn.fetch(
                'SELECT config_key, config_value FROM system_configs WHERE config_key = ANY($1::text[])',
                list(DEFAULTS.keys()),
            )
        _values = {row['config_key']: row['config_value'] for row in rows}
        _loaded_at = time.monotonic()
        _failed = False
    except Exception as e:
        _failed = True
        # 启动早期数据库还没就绪，只提示一次，之后静默回落默认值
        if _loaded_at == 0.0 and not _warned:
            _warned = True
            print(f"[INFO] 运行时配置暂不可用，先使用默认值: {str(e)}")

    return _values


def get(key: str, default: Optional[str] = None) -> str:
    """取字符串值（同步，读缓存）"""
    if key in _values:
        return _values[key]
    if default is not None:
        return default
    return DEFAULTS.get(key, '')


def get_int(key: str, default: int) -> int:
    """取整数，解析失败就用默认值（配置写坏了不该让服务报错）"""
    raw = get(key, str(default))
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def get_bool(key: str, default: bool) -> bool:
    """取布尔值，接受 true/false/1/0/on/off/yes/no"""
    raw = str(get(key, 'true' if default else 'false')).strip().lower()
    return raw in ('1', 'true', 'yes', 'on')
