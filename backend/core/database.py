#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database管理模块
================

这个模块负责database连接和会话管理
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

from .config import DATABASE_URL
import os

# 标记应用是否正在关闭
is_shutting_down = False

# 创建异步数据库连接池
async_connection_pool = None


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


# 迁移名常量：改过一次就不要再改名字，否则老库会被要求重跑
MIGRATION_USER_ID = 'user_id_min_6_digits'
MIGRATION_FEEDBACK_THREAD = 'feedback_thread_backfill'


async def _migration_done(conn, name: str) -> bool:
    """判断某次结构迁移是否已经在这套数据库上跑过"""
    try:
        return bool(await conn.fetchval('SELECT 1 FROM schema_migrations WHERE name = $1', name))
    except Exception:
        return False


async def _mark_migration(conn, name: str) -> None:
    await conn.execute(
        'INSERT INTO schema_migrations (name) VALUES ($1) ON CONFLICT (name) DO NOTHING',
        name,
    )


USER_ID_BASE = 100000

# 可在管理后台在线修改的运行时配置（键 → 界面说明）
# 这些项存进 system_configs，由 core.runtime_config 读取，改完立即生效
RUNTIME_CONFIG_DESCRIPTIONS = {
    'enable_rate_limit': '启用接口限流',
    'rate_limit_per_minute': '每 IP 每分钟可请求图片接口的次数',
    'rate_limit_auth_per_minute': '每 IP 每分钟可尝试登录/注册的次数',
    'enable_login_guard': '启用登录防爆破（连续失败后锁定）',
    'login_max_failures': '同一账号连续失败多少次后锁定',
    'login_ip_max_failures': '同一 IP 在窗口期内失败多少次后锁定',
    'login_lock_base_seconds': '首次锁定秒数（之后逐次翻倍）',
    'login_lock_max_seconds': '单次锁定时长上限（秒）',
    'max_sessions_per_user': '单用户最多保留的会话数',
    'session_cleanup_interval': '过期会话清理间隔（秒）',
    'audit_retention_days': '审核日志保留天数',
    'enable_register_guard': '启用注册防批量（按 IP 配额）',
    'register_max_per_window': '同一 IP 在窗口期内最多注册账号数',
    'register_window_seconds': '注册配额窗口（秒）',
    'register_min_interval_seconds': '同一 IP 两次注册的最小间隔（秒）',
}


async def _ensure_long_user_ids(conn):
    """把用户 ID 抬到 6 位起步

    - 已有数据：在事务里临时摘掉引用 users(id) 的外键，子表与主表一起加偏移，
      再按「原始定义」把外键加回去（保留 ON DELETE/UPDATE 行为）
    - 空表或已迁移：只对齐序列，保证下一个 ID 从 100000 起
    幂等：所有 id 都 >= 100000 时不会再搬数据。
    """
    try:
        if await _migration_done(conn, MIGRATION_USER_ID):
            return

        async with conn.transaction():
            # 多 worker 会同时执行 init_db，拿锁后再复查一次，避免重复搬家
            await conn.execute('SELECT pg_advisory_xact_lock(918273646)')
            if await _migration_done(conn, MIGRATION_USER_ID):
                return

            stale = await conn.fetchval(
                'SELECT COUNT(*) FROM users WHERE id < $1', USER_ID_BASE
            )

            fkeys = await conn.fetch('''
                SELECT con.conname AS name,
                       rel.relname AS tbl,
                       pg_get_constraintdef(con.oid) AS definition
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_class frel ON frel.oid = con.confrelid
                WHERE con.contype = 'f' AND frel.relname = 'users'
            ''')

            if stale:
                for fk in fkeys:
                    await conn.execute(f'ALTER TABLE {fk["tbl"]} DROP CONSTRAINT "{fk["name"]}"')

                # 先改子表再改主表，避免引用悬空
                await conn.execute(
                    'UPDATE sessions SET user_id = user_id + $1 WHERE user_id < $1', USER_ID_BASE
                )
                await conn.execute(
                    'UPDATE feedbacks SET user_id = user_id + $1 WHERE user_id < $1', USER_ID_BASE
                )
                await conn.execute('UPDATE users SET id = id + $1 WHERE id < $1', USER_ID_BASE)

                for fk in fkeys:
                    await conn.execute(
                        f'ALTER TABLE {fk["tbl"]} ADD CONSTRAINT "{fk["name"]}" {fk["definition"]}'
                    )

                print(f"✅ 用户 ID 已抬到 {USER_ID_BASE} 起步（迁移 {stale} 个账号）")

            max_id = await conn.fetchval('SELECT COALESCE(MAX(id), 0) FROM users')
            await conn.execute(
                f'ALTER SEQUENCE users_id_seq RESTART WITH {max(max_id + 1, USER_ID_BASE)}'
            )
            await _mark_migration(conn, MIGRATION_USER_ID)
    except Exception as e:
        print(f"[WARN] 调整用户 ID 起始值失败（不影响启动）: {str(e)}")


async def init_db():
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
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ 数据库连接成功")
    except asyncpg.exceptions.InvalidCatalogNameError:
        print("⚠️  数据库不存在，正在创建...")
        # 目标数据库不存在，先连接到默认的postgres数据库
        # 构建连接到postgres数据库的URL
        postgres_url = f"{parsed_url.scheme}://{parsed_url.netloc}/postgres"
        # 连接到postgres数据库
        postgres_conn = await asyncpg.connect(postgres_url)
        # 创建目标数据库
        await postgres_conn.execute(f"CREATE DATABASE {dbname}")
        await postgres_conn.close()
        # 现在连接到新创建的数据库
        print("🔗 正在连接新创建的数据库...")
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ 新数据库连接成功")
        is_new_database = True
    except Exception as e:
        # 其他错误，直接抛出
        print(f"❌ 数据库连接失败: {str(e)}")
        raise
    
    try:
        # 迁移记录表：保证"一次性的数据搬迁"不会在每次启动时重跑，
        # 也让升级过程可追溯（老库第一次跑新版本时会自动补齐）
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建用户表
        print("🔍 检查 users 表...")
        await conn.execute('''
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
            result = await conn.fetchrow('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name = $1
            ''', field_name)
            
            if not result:
                missing_count += 1
                print(f"⚠️  users 表缺失字段: {field_name}")
                print(f"🔧 创建 users 表字段: {field_name}")
                await conn.execute(f'''
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
        await conn.execute('''
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

        # 清理与裁剪都靠这两个索引：没有索引时 DELETE ... WHERE expires_at < now()
        # 会全表扫，表一大清理任务本身就变成负担
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, created_at DESC)'
        )
        # 登录设备展示需要来源信息；last_seen 用于「最近活跃」
        await conn.execute('ALTER TABLE sessions ADD COLUMN IF NOT EXISTS ip TEXT')
        await conn.execute('ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_agent TEXT')
        await conn.execute(
            'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ'
        )

        # 登录防爆破：账号/IP 双维度的失败计数（详见 core/security/login_guard.py）
        print("🔍 检查 login_attempts 表...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                scope TEXT NOT NULL,
                key TEXT NOT NULL,
                failures INTEGER NOT NULL DEFAULT 0,
                window_started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                locked_until TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (scope, key)
            )
        ''')
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_login_attempts_locked
            ON login_attempts(locked_until)
        ''')
        print("✅ login_attempts 表检查完成")

        # 审核日志：记录管理员的关键操作，只增不改（到期由后台任务清理）
        print("🔍 检查 audit_logs 表...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL PRIMARY KEY,
                actor_id INTEGER,
                actor_name TEXT NOT NULL DEFAULT '',
                actor_role TEXT,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                detail TEXT,
                metadata JSONB,
                ip TEXT,
                user_agent TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action, created_at DESC)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id, created_at DESC)'
        )
        print("✅ audit_logs 表检查完成")

        # 注册配额：按 IP 计数，防止短时间批量注册
        print("🔍 检查 register_attempts 表...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS register_attempts (
                ip TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                window_started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                locked_until TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_register_attempts_window '
            'ON register_attempts(window_started_at)'
        )
        print("✅ register_attempts 表检查完成")

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
            result = await conn.fetchrow('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sessions' 
                AND column_name = $1
            ''', field_name)
            
            if not result:
                missing_count += 1
                print(f"⚠️  sessions 表缺失字段: {field_name}")
                print(f"🔧 创建 sessions 表字段: {field_name}")
                await conn.execute(f'''
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
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS feedbacks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reply TEXT,
                replied_at TIMESTAMPTZ,
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
            ('reply', 'TEXT'),
            ('replied_at', 'TIMESTAMPTZ'),
            # 谁关闭的：user / admin（用于后台区分"用户自行关闭"）
            ('closed_by', 'TEXT'),
            ('created_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP'),
            ('updated_at', 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP')
        ]
        
        print("🔍 检查 feedbacks 表字段...")
        field_count = 0
        missing_count = 0
        
        for field_name, field_def in feedbacks_fields:
            field_count += 1
            result = await conn.fetchrow('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'feedbacks' 
                AND column_name = $1
            ''', field_name)
            
            if not result:
                missing_count += 1
                print(f"⚠️  feedbacks 表缺失字段: {field_name}")
                print(f"🔧 创建 feedbacks 表字段: {field_name}")
                await conn.execute(f'''
                    ALTER TABLE feedbacks 
                    ADD COLUMN {field_name} {field_def}
                ''')
                print(f"✅ feedbacks 表字段创建完成: {field_name}")
        
        if missing_count == 0:
            print(f"✅ feedbacks 表所有 {field_count} 个字段都存在，跳过创建")
        else:
            print(f"✅ feedbacks 表字段检查完成，创建了 {missing_count} 个缺失字段")

        # 创建 反馈对话 表（用户与管理员可多轮往来）
        print("🔍 检查 feedback_messages 表...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id SERIAL PRIMARY KEY,
                feedback_id INTEGER NOT NULL,
                user_id INTEGER,
                author TEXT NOT NULL DEFAULT 'user',
                author_name TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (feedback_id) REFERENCES feedbacks(id) ON DELETE CASCADE
            )
        ''')
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_feedback_messages_feedback
            ON feedback_messages(feedback_id, created_at)
        ''')

        # 回填历史数据：老版本反馈只有 content / reply 两个字段，
        # 这里把它转成对话记录；只跑一次，用记录表 + advisory lock 双重保证。
        if await _migration_done(conn, MIGRATION_FEEDBACK_THREAD):
            print("✅ feedback_messages 表检查完成（历史数据已迁移过）")
        else:
            async with conn.transaction():
                await conn.execute('SELECT pg_advisory_xact_lock(918273645)')

                # 1) 反馈正文 → 用户的第一条消息
                inserted = await conn.execute('''
                    INSERT INTO feedback_messages (feedback_id, user_id, author, author_name, content, created_at)
                    SELECT f.id, f.user_id, 'user', u.username, f.content, f.created_at
                    FROM feedbacks f
                    LEFT JOIN users u ON f.user_id = u.id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM feedback_messages m WHERE m.feedback_id = f.id
                    )
                ''')

                # 2) 旧的管理员回复 → 管理员消息
                await conn.execute('''
                    INSERT INTO feedback_messages (feedback_id, user_id, author, author_name, content, created_at)
                    SELECT f.id, NULL, 'admin', '管理员', f.reply, COALESCE(f.replied_at, f.updated_at)
                    FROM feedbacks f
                    WHERE f.reply IS NOT NULL AND f.reply <> ''
                      AND NOT EXISTS (
                          SELECT 1 FROM feedback_messages m
                          WHERE m.feedback_id = f.id AND m.author = 'admin'
                      )
                ''')

                await _mark_migration(conn, MIGRATION_FEEDBACK_THREAD)

                if inserted and not inserted.endswith(' 0'):
                    print(f"✅ 已把历史反馈迁移为对话记录: {inserted}")

            print("✅ feedback_messages 表检查完成")

        # 用户 ID 抬到 6 位起步（100000），短 ID 看起来像测试数据也容易被猜
        await _ensure_long_user_ids(conn)

        # 创建categories表
        print("🔍 检查 categories 表...")
        await conn.execute('''
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
            result = await conn.fetchrow('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'categories' 
                AND column_name = $1
            ''', field_name)
            
            if not result:
                missing_count += 1
                print(f"⚠️  categories 表缺失字段: {field_name}")
                print(f"🔧 创建 categories 表字段: {field_name}")
                await conn.execute(f'''
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
        await conn.execute('''
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
            result = await conn.fetchrow('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'images' 
                AND column_name = $1
            ''', field_name)
            
            if not result:
                missing_count += 1
                print(f"⚠️  images 表缺失字段: {field_name}")
                print(f"🔧 创建 images 表字段: {field_name}")
                await conn.execute(f'''
                    ALTER TABLE images 
                    ADD COLUMN {field_name} {field_def}
                ''')
                print(f"✅ images 表字段创建完成: {field_name}")
        
        if missing_count == 0:
            print(f"✅ images 表所有 {field_count} 个字段都存在，跳过创建")
        else:
            print(f"✅ images 表字段检查完成，创建了 {missing_count} 个缺失字段")

        # 为images表创建索引以提高查询性能
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_category_id ON images(category_id)
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_status ON images(status)
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at DESC)
        ''')

        # 创建系统配置表
        print("🔍 检查 system_configs 表...")
        await conn.execute('''
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
            result = await conn.fetchrow('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'system_configs' 
                AND column_name = $1
            ''', field_name)
            
            if not result:
                missing_count += 1
                print(f"⚠️  system_configs 表缺失字段: {field_name}")
                print(f"🔧 创建 system_configs 表字段: {field_name}")
                await conn.execute(f'''
                    ALTER TABLE system_configs 
                    ADD COLUMN {field_name} {field_def}
                ''')
                print(f"✅ system_configs 表字段创建完成: {field_name}")
                
                # 如果添加的是 default_value 字段，更新其值为 config_value
                if field_name == 'default_value':
                    print("🔧 更新 system_configs 表的 default_value 字段值...")
                    await conn.execute('''
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

        # 运行时配置：管理后台「限流与安全」可改，保存后无需重启即生效。
        # 默认值来自环境变量（core.runtime_config.DEFAULTS），这里只负责落库与描述文案。
        from .runtime_config import DEFAULTS as RUNTIME_DEFAULTS
        for config_key, description in RUNTIME_CONFIG_DESCRIPTIONS.items():
            default_configs.append(
                (config_key, RUNTIME_DEFAULTS.get(config_key, ''), description)
            )
        
        # 批量插入或更新默认配置
        for config_key, config_value, description in default_configs:
            await conn.execute('''
                INSERT INTO system_configs (config_key, config_value, default_value, description)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (config_key) DO UPDATE SET
                    default_value = $3,
                    description = $4
            ''', config_key, config_value, config_value, description)

        # 兼容性摘要：升级后一眼能看出结构是否补齐
        try:
            table_count = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
            )
            migration_count = await conn.fetchval('SELECT COUNT(*) FROM schema_migrations')
            print(f"✅ 数据库就绪：{table_count} 张表 / {migration_count} 条迁移记录")
        except Exception:
            pass

        # asyncpg 默认自动提交，不需要手动调用 commit
    finally:
        await conn.close()

    # 数据库初始化完成，设置环境变量为 true
    os.environ['DATABASE_INITIALIZED'] = 'true'

    return is_new_database


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
        except Exception:
            raise
        finally:
            await async_connection_pool.release(conn)
    else:
        # 连接池不可用时，使用单连接模式
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            yield conn
        except Exception:
            raise
        finally:
            await conn.close()
