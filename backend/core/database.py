#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database管理模块
================

这个模块负责database连接和会话管理
"""

from contextlib import contextmanager, asynccontextmanager
from typing import Optional, AsyncGenerator
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import asyncpg
import asyncio

from .config import DATABASE_URL
import os

# 标记应用是否正在关闭
is_shutting_down = False

# 创建同步数据库连接池
connection_pool = None

# 创建异步数据库连接池
async_connection_pool = None

try:
    # 初始化同步连接池
    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,  # 最小连接数
        maxconn=10,  # 最大连接数
        dsn=DATABASE_URL
    )
    print("✅ 同步数据库连接池初始化成功")
except Exception as e:
    print(f"❌ 同步数据库连接池初始化失败: {str(e)}")
    # 如果连接池初始化失败，仍然使用单连接模式
    connection_pool = None


async def init_async_pool():
    """
    初始化异步数据库连接池
    """
    global async_connection_pool
    try:
        # 解析DATABASE_URL获取连接参数
        import urllib.parse
        parsed = urllib.parse.urlparse(DATABASE_URL)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/')
        }
        # asyncpg 使用 ssl 参数而不是 sslmode
        if parsed.scheme == 'postgres':
            conn_params['ssl'] = True
        
        # 初始化异步连接池
        async_connection_pool = await asyncpg.create_pool(
            min_size=1,
            max_size=10,
            command_timeout=60,
            **conn_params
        )
        print("✅ 异步数据库连接池初始化成功")
    except Exception as e:
        print(f"❌ 异步数据库连接池初始化失败: {str(e)}")
        async_connection_pool = None


async def close_async_pool():
    """
    关闭异步数据库连接池
    """
    global async_connection_pool
    if async_connection_pool:
        await async_connection_pool.close()
        print("✅ 异步数据库连接池已关闭")


def set_shutting_down():
    """
    设置应用正在关闭
    """
    global is_shutting_down
    is_shutting_down = True


def init_db():
    """
    初始化database，创建必要的表
    
    Returns:
        bool: True表示数据库是新创建的，False表示数据库已存在
    """
    # 检查是否正在关闭
    global is_shutting_down
    if is_shutting_down:
        return False
    
    # 检查是否是热重载启动且不是主进程
    is_reload = os.getenv('UVICORN_RELOAD', 'false') == 'true'
    is_main_process = os.getenv('UVICORN_PROCESS_NAME', 'main') == 'main'
    
    # 检查是否已经执行过初始化
    if os.getenv('DATABASE_INITIALIZED', 'false') == 'true' and not (is_reload and is_main_process):
        return False
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
    print("🔍 检查 users 表...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMPTZ,
            banned_at TIMESTAMPTZ,
            ban_reason TEXT
        )
    ''')
    print("✅ users 表检查完成")
    
    # 检查并添加 users 表的必要字段（如果不存在）
    users_fields = [
        ('email', 'TEXT UNIQUE NOT NULL'),
        ('password_hash', 'TEXT NOT NULL'),
        ('salt', 'TEXT NOT NULL'),
        ('role', 'TEXT DEFAULT \'user\''),
        ('status', 'TEXT DEFAULT \'active\''),
        ('last_login', 'TIMESTAMPTZ'),
        ('banned_at', 'TIMESTAMPTZ'),
        ('ban_reason', 'TEXT')
    ]
    
    print("🔍 检查 users 表字段...")
    field_count = 0
    missing_count = 0
    
    for field_name, field_def in users_fields:
        field_count += 1
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = %s
        ''', (field_name,))
        
        if not cursor.fetchone():
            missing_count += 1
            print(f"⚠️  users 表缺失字段: {field_name}")
            print(f"🔧 创建 users 表字段: {field_name}")
            cursor.execute(f'''
                ALTER TABLE users 
                ADD COLUMN {field_name} {field_def}
            ''')
            print(f"✅ users 表字段创建完成: {field_name}")
    
    if missing_count == 0:
        print(f"✅ users 表所有 {field_count} 个字段都存在，跳过创建")
    else:
        print(f"✅ users 表字段检查完成，创建了 {missing_count} 个缺失字段")

    # 创建session表
    print("🔍 检查 sessions 表...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    print("✅ sessions 表检查完成")
    
    # 检查并添加 sessions 表的必要字段（如果不存在）
    sessions_fields = [
        ('user_id', 'INTEGER NOT NULL'),
        ('username', 'TEXT NOT NULL'),
        ('expires_at', 'TIMESTAMPTZ NOT NULL'),
        ('created_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP')
    ]
    
    print("🔍 检查 sessions 表字段...")
    field_count = 0
    missing_count = 0
    
    for field_name, field_def in sessions_fields:
        field_count += 1
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sessions' 
            AND column_name = %s
        ''', (field_name,))
        
        if not cursor.fetchone():
            missing_count += 1
            print(f"⚠️  sessions 表缺失字段: {field_name}")
            print(f"🔧 创建 sessions 表字段: {field_name}")
            cursor.execute(f'''
                ALTER TABLE sessions 
                ADD COLUMN {field_name} {field_def}
            ''')
            print(f"✅ sessions 表字段创建完成: {field_name}")
    
    if missing_count == 0:
        print(f"✅ sessions 表所有 {field_count} 个字段都存在，跳过创建")
    else:
        print(f"✅ sessions 表字段检查完成，创建了 {missing_count} 个缺失字段")

    # 创建feedbacks表
    print("🔍 检查 feedbacks 表...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedbacks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    print("✅ feedbacks 表检查完成")
    
    # 检查并添加 feedbacks 表的必要字段（如果不存在）
    feedbacks_fields = [
        ('user_id', 'INTEGER NOT NULL'),
        ('content', 'TEXT NOT NULL'),
        ('status', 'TEXT DEFAULT \'pending\''),
        ('created_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP')
    ]
    
    print("🔍 检查 feedbacks 表字段...")
    field_count = 0
    missing_count = 0
    
    for field_name, field_def in feedbacks_fields:
        field_count += 1
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'feedbacks' 
            AND column_name = %s
        ''', (field_name,))
        
        if not cursor.fetchone():
            missing_count += 1
            print(f"⚠️  feedbacks 表缺失字段: {field_name}")
            print(f"🔧 创建 feedbacks 表字段: {field_name}")
            cursor.execute(f'''
                ALTER TABLE feedbacks 
                ADD COLUMN {field_name} {field_def}
            ''')
            print(f"✅ feedbacks 表字段创建完成: {field_name}")
    
    if missing_count == 0:
        print(f"✅ feedbacks 表所有 {field_count} 个字段都存在，跳过创建")
    else:
        print(f"✅ feedbacks 表字段检查完成，创建了 {missing_count} 个缺失字段")

    # 创建categories表
    print("🔍 检查 categories 表...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'enabled',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ categories 表检查完成")
    
    # 检查并添加 categories 表的必要字段（如果不存在）
    categories_fields = [
        ('name', 'TEXT UNIQUE NOT NULL'),
        ('description', 'TEXT'),
        ('status', 'TEXT DEFAULT \'enabled\''),
        ('created_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP')
    ]
    
    print("🔍 检查 categories 表字段...")
    field_count = 0
    missing_count = 0
    
    for field_name, field_def in categories_fields:
        field_count += 1
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'categories' 
            AND column_name = %s
        ''', (field_name,))
        
        if not cursor.fetchone():
            missing_count += 1
            print(f"⚠️  categories 表缺失字段: {field_name}")
            print(f"🔧 创建 categories 表字段: {field_name}")
            cursor.execute(f'''
                ALTER TABLE categories 
                ADD COLUMN {field_name} {field_def}
            ''')
            print(f"✅ categories 表字段创建完成: {field_name}")
    
    if missing_count == 0:
        print(f"✅ categories 表所有 {field_count} 个字段都存在，跳过创建")
    else:
        print(f"✅ categories 表字段检查完成，创建了 {missing_count} 个缺失字段")

    # 创建images表
    print("🔍 检查 images 表...")
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
            last_viewed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'enabled',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    ''')
    print("✅ images 表检查完成")
    
    # 检查并添加 images 表的必要字段（如果不存在）
    images_fields = [
        ('filename', 'TEXT NOT NULL'),
        ('file_path', 'TEXT NOT NULL'),
        ('category_id', 'INTEGER'),
        ('file_size', 'BIGINT'),
        ('width', 'INTEGER'),
        ('height', 'INTEGER'),
        ('format', 'TEXT'),
        ('md5', 'TEXT'),
        ('uploader', 'TEXT'),
        ('upload_ip', 'TEXT'),
        ('view_count', 'INTEGER DEFAULT 0'),
        ('last_viewed_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP'),
        ('status', 'TEXT DEFAULT \'enabled\''),
        ('created_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP')
    ]
    
    print("🔍 检查 images 表字段...")
    field_count = 0
    missing_count = 0
    
    for field_name, field_def in images_fields:
        field_count += 1
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'images' 
            AND column_name = %s
        ''', (field_name,))
        
        if not cursor.fetchone():
            missing_count += 1
            print(f"⚠️  images 表缺失字段: {field_name}")
            print(f"🔧 创建 images 表字段: {field_name}")
            cursor.execute(f'''
                ALTER TABLE images 
                ADD COLUMN {field_name} {field_def}
            ''')
            print(f"✅ images 表字段创建完成: {field_name}")
    
    if missing_count == 0:
        print(f"✅ images 表所有 {field_count} 个字段都存在，跳过创建")
    else:
        print(f"✅ images 表字段检查完成，创建了 {missing_count} 个缺失字段")

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

    # 创建系统配置表
    print("🔍 检查 system_configs 表...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_configs (
            id SERIAL PRIMARY KEY,
            config_key TEXT UNIQUE NOT NULL,
            config_value TEXT NOT NULL,
            default_value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ system_configs 表检查完成")
    
    # 检查并添加 system_configs 表的必要字段（如果不存在）
    system_configs_fields = [
        ('config_key', 'TEXT UNIQUE NOT NULL'),
        ('config_value', 'TEXT NOT NULL'),
        ('default_value', 'TEXT NOT NULL'),
        ('description', 'TEXT'),
        ('created_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP')
    ]
    
    print("🔍 检查 system_configs 表字段...")
    field_count = 0
    missing_count = 0
    
    for field_name, field_def in system_configs_fields:
        field_count += 1
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'system_configs' 
            AND column_name = %s
        ''', (field_name,))
        
        if not cursor.fetchone():
            missing_count += 1
            print(f"⚠️  system_configs 表缺失字段: {field_name}")
            print(f"🔧 创建 system_configs 表字段: {field_name}")
            cursor.execute(f'''
                ALTER TABLE system_configs 
                ADD COLUMN {field_name} {field_def}
            ''')
            print(f"✅ system_configs 表字段创建完成: {field_name}")
            
            # 如果添加的是 default_value 字段，更新其值为 config_value
            if field_name == 'default_value':
                print("🔧 更新 system_configs 表的 default_value 字段值...")
                cursor.execute('''
                    UPDATE system_configs 
                    SET default_value = config_value
                ''')
                print("✅ system_configs 表的 default_value 字段值更新完成")
    
    if missing_count == 0:
        print(f"✅ system_configs 表所有 {field_count} 个字段都存在，跳过创建")
    else:
        print(f"✅ system_configs 表字段检查完成，创建了 {missing_count} 个缺失字段")
    


    # 插入默认配置
    default_configs = [
        # 基本设置
        ('site_name', '随机图API', '站点名称'),
        ('site_domain', 'https://api.example.com', '站点域名'),
        ('icp_beian', '京ICP备1234XXX号', 'ICP备案号'),
        ('beian_link', 'https://beian.miit.gov.cn', '备案信息链接'),
        ('timezone', 'Asia/Shanghai', '系统默认时区（东八区，北京时间）'),
        ('favicon_url', '', '站点图标地址'),
        
        # 安全设置（默认值全部为关闭状态）
        ('enable_access_log', 'false', '启用访问日志'),
        ('show_beian_info', 'false', '显示备案信息'),
        ('enable_path_traversal_protection', 'false', '启用路径穿越防护'),
        ('enable_hotlink_protection', 'false', '启用防盗链'),
        ('enable_ip_blacklist', 'false', '启用IP黑名单')
    ]
    
    # 批量插入或更新默认配置
    for config_key, config_value, description in default_configs:
        cursor.execute('''
            INSERT INTO system_configs (config_key, config_value, default_value, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (config_key) DO UPDATE SET
                default_value = %s,
                description = %s
        ''', (config_key, config_value, config_value, description, config_value, description))

    conn.commit()
    conn.close()

    # 数据库初始化完成，设置环境变量为 true
    os.environ['DATABASE_INITIALIZED'] = 'true'

    return is_new_database


@contextmanager
def get_db_connection():
    """
    获取同步database连接的上下文管理器

    使用示例:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
    """
    # 使用连接池获取连接
    if connection_pool:
        conn = connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            connection_pool.putconn(conn)
    else:
        # 连接池不可用时，使用单连接模式
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


@asynccontextmanager
async def get_async_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    获取异步database连接的上下文管理器

    使用示例:
        async with get_async_db_connection() as conn:
            result = await conn.fetch("SELECT * FROM users")
    """
    if async_connection_pool:
        conn = await async_connection_pool.acquire()
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await async_connection_pool.release(conn)
    else:
        # 连接池不可用时，使用单连接模式
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()
