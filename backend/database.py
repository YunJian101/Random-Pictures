#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理模块
================

这个模块负责数据库连接和会话管理
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional

from .config import DB_PATH


def init_db():
    """
    初始化数据库，创建必要的表
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            banned_at TIMESTAMP
        )
    ''')

    # 检查是否需要添加status列（兼容旧数据库）
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'status' not in columns:
        print("正在为现有数据库添加status字段...")
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        conn.commit()
    if 'banned_at' not in columns:
        print("正在为现有数据库添加banned_at字段...")
        cursor.execute("ALTER TABLE users ADD COLUMN banned_at TIMESTAMP")
        conn.commit()

    # 创建session表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()


@contextmanager
def get_db_connection():
    """
    获取数据库连接的上下文管理器

    使用示例:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_factory(cursor, row):
    """将查询结果转换为字典"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
