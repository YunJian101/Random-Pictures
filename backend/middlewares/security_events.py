#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常请求审计
============

把「被拒绝的请求」也记进审核日志，否则日志里只剩成功操作，出事时看不出
有人在扫接口。判定规则刻意保守，只记有安全含义的状态码：

    401 / 403  → security.denied      未登录访问管理接口、越权
    429        → security.rate_limit  触发限流
    422        → security.rejected    路径穿越、非法参数（仅图片接口）
    5xx        → security.server_error 服务端错误

404 一律不记：扫描器随便打几个路径就能把表刷满，收益极低。

为避免攻击者用同一个路径狂刷把日志表打爆，同一个 (IP, 动作, 路径, 状态码)
在 THROTTLE_SECONDS 内只记第一条。被压掉的次数不累计——审计要的是「发生了」，
不是精确计数，精确计数有 login_attempts 和限流桶负责。
"""

import time

from starlette.requests import Request

__all__ = ['decide', 'maybe_record']

THROTTLE_SECONDS = 30
# 记录条数上限，防止内存里堆太多临时键
THROTTLE_MAX_KEYS = 5000

# 只有这些前缀的请求才值得进安全日志（静态资源、页面 404 不记）
WATCHED_PREFIXES = ('/api/', '/random', '/image', '/thumb')

# 这些路径的 401 是正常业务反馈，不是安全事件：
#   登录/注册失败 → 已由 login_attempts 单独统计
#   会话校验 → 首页每次加载都会问一次，记了就是噪音
NORMAL_401_PATHS = ('/api/login', '/api/register', '/api/auth/verify')

_recent: dict[tuple, float] = {}


def decide(path: str, status: int) -> tuple[str, str] | None:
    """判断这次请求要不要记安全日志，返回 (动作码, 原因)"""
    if not path.startswith(WATCHED_PREFIXES):
        return None

    if status == 401:
        if path in NORMAL_401_PATHS:
            return None
        return ('security.denied', '未登录或会话失效')
    if status == 403:
        return ('security.denied', '权限不足')
    if status == 429:
        return ('security.rate_limit', '触发限流或登录锁定')
    if status == 422 and (path.startswith('/image') or path.startswith('/thumb')):
        return ('security.rejected', '非法路径或参数')
    if status >= 500:
        return ('security.server_error', '服务端处理失败')
    return None


def _throttled(key: tuple) -> bool:
    now = time.monotonic()

    if len(_recent) > THROTTLE_MAX_KEYS:
        cutoff = now - THROTTLE_SECONDS
        for k in [k for k, t in _recent.items() if t < cutoff]:
            _recent.pop(k, None)

    last = _recent.get(key)
    if last is not None and (now - last) < THROTTLE_SECONDS:
        return True

    _recent[key] = now
    return False


async def _resolve_actor(request: Request):
    """尽力解析操作人；解析不到就按匿名处理（401 本来就没人）"""
    from ..core.config import COOKIE_NAME

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    try:
        from ..core.database import get_async_db_connection

        async with get_async_db_connection() as conn:
            row = await conn.fetchrow('''
                SELECT u.id, u.username, u.role
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = $1 AND s.expires_at > CURRENT_TIMESTAMP
            ''', token)
        return dict(row) if row else None
    except Exception:
        return None


async def maybe_record(request: Request, status: int, ip: str) -> None:
    """按规则把异常请求写进审核日志（自身绝不抛异常）"""
    try:
        path = request.url.path
        rule = decide(path, status)
        if not rule:
            return

        action, reason = rule
        if _throttled((ip, action, path, status)):
            return

        from ..services.audit_service import record

        actor = await _resolve_actor(request)
        await record(
            request,
            action,
            actor,
            target_type='request',
            target_id=path,
            detail=f'{request.method} {path} → {status}（{reason}）',
            metadata={
                'method': request.method,
                'path': path,
                'status': status,
                'query': str(request.url.query or '')[:200],
            },
        )
    except Exception as e:
        print(f'[WARN] 记录异常请求失败: {str(e)}')
