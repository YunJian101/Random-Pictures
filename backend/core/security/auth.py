#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证门面（向后兼容层）
======================

历史上这里是一个 560 行的「什么都管」模块：密码哈希、token、会话、
用户增删改查、封禁全挤在一起。现已按职责拆开：

    core/security/password.py    密码哈希与校验
    core/security/session.py     会话签发 / 校验 / 注销 / 清理
    core/security/login_guard.py 登录失败锁定
    services/user_service.py     用户生命周期（注册/登录/资料/封禁/删除）

本文件只做转发，保证既有的 `from ..core.security.auth import xxx` 不用改。
新代码请直接 import 上面几个模块，别在这里加新逻辑。
"""

from .password import hash_password, verify_password  # noqa: F401
from ...services.user_service import (  # noqa: F401
    ban_user,
    change_password,
    delete_user,
    get_all_users,
    get_user_by_id,
    login_user,
    register_user,
    unban_user,
    update_user_info,
    update_user_role,
    verify_user_password,
)
from .session import (  # noqa: F401
    cleanup_expired_sessions,
    generate_token,
    logout_user,
    verify_session,
)

__all__ = [
    'hash_password',
    'verify_password',
    'generate_token',
    'register_user',
    'login_user',
    'verify_session',
    'logout_user',
    'cleanup_expired_sessions',
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
