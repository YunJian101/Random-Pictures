#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密码哈希
========

单一职责：只负责「把明文密码变成可存储的哈希」以及「校验明文是否匹配」。

注意：这里沿用历史实现（SHA-256 + 每用户随机 salt），目的是不破坏已有账号的
密码校验。若将来要换成 bcrypt/argon2，正确做法是在 users 表加 hash_algo 字段，
登录成功时按旧算法校验、再用新算法重写一次，而不是整体替换。
"""

import hashlib
import secrets
from typing import Optional

__all__ = ['hash_password', 'verify_password']

SALT_BYTES = 16


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """生成密码哈希

    参数:
        password: 明文密码
        salt: 复用已有 salt（校验时必须传入，否则算出来的哈希对不上）

    返回:
        (password_hash, salt)
    """
    if salt is None:
        salt = secrets.token_hex(SALT_BYTES)

    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return password_hash, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """校验明文密码是否与已存储的哈希匹配（常量时间比较，避免时序侧信道）"""
    if not stored_hash or not salt:
        return False

    candidate, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate, stored_hash)
