#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后台维护任务
============

把「定期打扫卫生」的事情从 main.py 里挪出来。目前包括：

- 清理过期会话（sessions 表只增不减的根治手段）
- 清理过期的登录失败记录（login_attempts 表）

设计要点：
- 启动时先跑一次，之后按 SESSION_CLEANUP_INTERVAL 循环（默认 30 分钟）。
  间隔缩短到 30 分钟，是为了让表里长期只剩「还未过期的会话」，
  而不是攒一整天的死数据等半夜清。
- 任何一次失败都只打日志，不影响主服务。
"""

import asyncio

from . import runtime_config
from .config import SESSION_CLEANUP_INTERVAL

__all__ = ['run_cleanup_once', 'cleanup_loop']


async def run_cleanup_once() -> dict:
    """跑一轮清理，返回各表的删除条数（便于日志/排查）"""
    # 延迟导入：避免 core.tasks ← main ← ... 的循环导入
    from .security.register_guard import cleanup_register_attempts
    from ..services.thumb_service import cleanup_orphan_thumbs
    from ..services.audit_service import cleanup_logs
    from .security.login_guard import cleanup_login_attempts
    from .security.session import cleanup_expired_sessions

    removed_sessions = await cleanup_expired_sessions()
    removed_attempts = await cleanup_login_attempts()
    removed_register = await cleanup_register_attempts()

    await runtime_config.ensure_loaded()
    retention_days = runtime_config.get_int('audit_retention_days', 90)
    removed_logs = await cleanup_logs(retention_days)
    removed_thumbs = await cleanup_orphan_thumbs()

    if removed_sessions or removed_attempts or removed_logs or removed_thumbs:
        print(
            f"🧹 清理完成：过期会话 {removed_sessions} 条 / 登录记录 {removed_attempts} 条 / "
            f"审核日志 {removed_logs} 条（保留 {retention_days} 天）/ 孤儿缩略图 {removed_thumbs} 个"
        )

    return {
        'sessions': removed_sessions,
        'login_attempts': removed_attempts,
        'register_attempts': removed_register,
        'audit_logs': removed_logs,
        'orphan_thumbs': removed_thumbs,
    }


async def cleanup_loop() -> None:
    """常驻任务：启动即清理一次，之后按当前配置的间隔循环

    间隔每轮重新读一次运行时配置，后台把「清理间隔」从 30 分钟改成 5 分钟，
    下一轮就按新间隔走，不需要重启。
    """
    try:
        await run_cleanup_once()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"[WARN] 启动清理失败: {str(e)}")

    while True:
        await runtime_config.ensure_loaded()
        interval = max(60, runtime_config.get_int('session_cleanup_interval', SESSION_CLEANUP_INTERVAL))
        await asyncio.sleep(interval)
        try:
            await run_cleanup_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[WARN] 定期清理失败: {str(e)}")
