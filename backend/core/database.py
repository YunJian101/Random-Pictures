#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database管理模块
================

这个模块负责database连接和会话管理
"""

from contextlib import contextmanager
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from .config import DATABASE_URL


def init_db():
    """
    初始化database，创建必要的表
    
    Returns:
        bool: True表示数据库是新创建的，False表示数据库已存在
    """
    # 使用PostgreSQL
    is_new_database = False
    
    # 解析DATABASE_URL获取连接信息
    import urllib.parse
    parsed_url = urllib.parse.urlparse(DATABASE_URL)
    db_type = parsed_url.scheme
    netloc = parsed_url.netloc
    dbname = parsed_url.path[1:] if parsed_url.path else ''  # 去掉开头的'/'
    
    # 提取主机和端口
    if '@' in netloc:
        # 格式: username:password@host:port
        auth_part, host_part = netloc.split('@', 1)
    else:
        # 格式: host:port 或 只有host
        host_part = netloc
    
    if ':' in host_part:
        host, port = host_part.split(':', 1)
    else:
        host = host_part
        port = '5432'  # PostgreSQL默认端口
    
    # 输出数据库连接信息
    print(f"📦 数据库配置:")
    print(f"   类型: {db_type}")
    print(f"   地址: {host}")
    print(f"   端口: {port}")
    print(f"   数据库: {dbname}")
    
    try:
        # 尝试直接连接目标数据库
        print("🔗 正在连接数据库...")
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ 数据库连接成功")
    except psycopg2.OperationalError as e:
        if "database \"random_pictures\" does not exist" in str(e):
            print("⚠️  数据库不存在，正在创建...")
            # 目标数据库不存在，先连接到默认的postgres数据库
            # 构建连接到postgres数据库的URL
            postgres_url = f"{parsed_url.scheme}://{parsed_url.netloc}/postgres"
            # 连接到postgres数据库
            postgres_conn = psycopg2.connect(postgres_url)
            postgres_conn.autocommit = True
            postgres_cursor = postgres_conn.cursor()
            # 创建目标数据库
            postgres_cursor.execute(f"CREATE DATABASE {dbname}")
            postgres_cursor.close()
            postgres_conn.close()
            # 现在连接到新创建的数据库
            print("🔗 正在连接新创建的数据库...")
            conn = psycopg2.connect(DATABASE_URL)
            print("✅ 新数据库连接成功")
            is_new_database = True
        else:
            # 其他错误，直接抛出
            print(f"❌ 数据库连接失败: {str(e)}")
            raise
    
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            banned_at TIMESTAMP,
            ban_reason TEXT
        )
    ''')

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

    # 创建feedbacks表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedbacks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 创建categories表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'enabled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建images表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            category_id INTEGER,
            file_size BIGINT,
            width INTEGER,
            height INTEGER,
            format TEXT,
            md5 TEXT,
            uploader TEXT,
            upload_ip TEXT,
            view_count INTEGER DEFAULT 0,
            last_viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'enabled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    ''')

    # 为images表创建索引以提高查询性能
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_category_id ON images(category_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_status ON images(status)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at DESC)
    ''')

    conn.commit()
    conn.close()

    return is_new_database


@contextmanager
def get_db_connection():
    """
    获取database连接的上下文管理器

    使用示例:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
    """
    # 使用PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
