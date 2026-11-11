#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
============

这个模块集中管理所有应用程序配置参数，包括:
- 服务器配置（端口、主机等）
- 数据库配置
- 图片相关配置
- 站点个性化配置
- 认证配置

配置优先级: 环境变量 > 默认值
"""

import os
from pathlib import Path

# ==================== 服务器基础配置 ====================
# 服务器监听端口
PORT = int(os.getenv('PORT', 8081))

# 服务器监听主机
HOST = os.getenv('HOST', '0.0.0.0')

# 请求超时时间（秒）
TIMEOUT = int(os.getenv('TIMEOUT', 10))


# ==================== 数据库配置 ====================
# 数据库URL（优先使用环境变量）
DATABASE_URL = os.getenv('DATABASE_URL')

# 数据库目录（SQLite备用）
DB_DIR = os.getenv('DB_DIR', '/app/data')

# 数据库文件路径（SQLite备用）
DB_PATH = os.path.join(DB_DIR, 'users.db')


# ==================== 图片相关配置 ====================
# 图片缓存时间（秒）
IMAGE_CACHE_SECONDS = int(os.getenv('IMAGE_CACHE_SECONDS', 604800))

# 支持的图片格式元组
SUPPORTED_IMAGE_FORMATS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

# 单张图片上传大小上限（MB）的出厂默认值
# 实际生效值取运行时配置 max_upload_mb（管理后台「系统设置」可改，保存即生效）
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', 5))

# 项目创建日期（YYYY-MM-DD）的出厂默认值
# 首页「稳定交付 N 天」按它计算；实际生效值取运行时配置 site_launch_date
SITE_LAUNCH_DATE = os.getenv('SITE_LAUNCH_DATE', '2026-02-11')

# 图片根目录路径
IMG_ROOT_DIR = os.getenv('IMG_ROOT_DIR', '/app/images')

# 静态文件根目录
STATIC_ROOT_DIR = os.getenv('STATIC_ROOT_DIR', '/app/frontend/static')

# 前端模板根目录
FRONTEND_ROOT_DIR = os.getenv('FRONTEND_ROOT_DIR', '/app/frontend')


# ==================== 缩略图配置 ====================
# 缩略图缓存目录（与图片目录分开，避免污染图库）
THUMB_CACHE_DIR = os.getenv('THUMB_CACHE_DIR', '/app/data/thumbs')

# 允许的缩略图宽度（不在白名单内的一律取最近值，防止被刷出无数尺寸）
THUMB_SIZES = (160, 320, 480, 640, 960)

# 缩略图 JPEG 质量
THUMB_QUALITY = int(os.getenv('THUMB_QUALITY', 82))


# ==================== 会话清理 ====================
# 过期会话清理间隔（秒），默认 30 分钟
# 让 sessions 表的行数稳定在「活跃用户数」量级，而不是随登录次数线性增长
SESSION_CLEANUP_INTERVAL = int(os.getenv('SESSION_CLEANUP_INTERVAL', 30 * 60))

# 单用户最多保留几个会话（超出后登录会淘汰最旧的）
# 防止同一账号反复登录把 sessions 堆成历史垃圾场
MAX_SESSIONS_PER_USER = int(os.getenv('MAX_SESSIONS_PER_USER', 10))


# ==================== 登录防爆破 ====================
# 同一账号在窗口期内允许的连续失败次数
LOGIN_MAX_FAILURES = int(os.getenv('LOGIN_MAX_FAILURES', 5))

# 同一 IP 在窗口期内允许的失败次数（防换账号横扫）
LOGIN_IP_MAX_FAILURES = int(os.getenv('LOGIN_IP_MAX_FAILURES', 20))

# 计数窗口（秒）：窗口内没达到阈值就重新计数
LOGIN_WINDOW_SECONDS = int(os.getenv('LOGIN_WINDOW_SECONDS', 15 * 60))

# 首次锁定时长（秒），之后每次翻倍
LOGIN_LOCK_BASE_SECONDS = int(os.getenv('LOGIN_LOCK_BASE_SECONDS', 60))

# 单次锁定上限（秒）
LOGIN_LOCK_MAX_SECONDS = int(os.getenv('LOGIN_LOCK_MAX_SECONDS', 15 * 60))


# ==================== 注册防批量 ====================
# 总开关
REGISTER_GUARD_ENABLED = os.getenv('REGISTER_GUARD_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')

# 同一 IP 在窗口期内最多注册几个账号
REGISTER_MAX_PER_WINDOW = int(os.getenv('REGISTER_MAX_PER_WINDOW', 5))

# 配额窗口（秒），默认 1 小时
REGISTER_WINDOW_SECONDS = int(os.getenv('REGISTER_WINDOW_SECONDS', 3600))

# 同一 IP 两次注册之间的最小间隔（秒）
REGISTER_MIN_INTERVAL_SECONDS = int(os.getenv('REGISTER_MIN_INTERVAL_SECONDS', 30))


# ==================== 限流配置 ====================
# 是否启用限流
RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')

# 每个 IP 每分钟允许的请求数（按路径分别计数）
RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 120))

# 应用限流的路径（逗号分隔）
RATE_LIMIT_PATHS = tuple(
    p.strip() for p in os.getenv('RATE_LIMIT_PATHS', '/random,/image,/thumb').split(',') if p.strip()
)

# 登录 / 注册单独一档：这两个接口最容易被拿来撞库，限额要比看图严格得多
RATE_LIMIT_AUTH_PATHS = tuple(
    p.strip() for p in os.getenv('RATE_LIMIT_AUTH_PATHS', '/api/login,/api/register').split(',') if p.strip()
)

# 每个 IP 每分钟允许的登录/注册次数
RATE_LIMIT_AUTH_PER_MINUTE = int(os.getenv('RATE_LIMIT_AUTH_PER_MINUTE', 10))

# 是否信任反向代理传来的 X-Forwarded-For
# 直连部署时务必保持 false，否则客户端可以伪造该头绕过限流
TRUST_PROXY = os.getenv('TRUST_PROXY', 'false').lower() in ('1', 'true', 'yes', 'on')


# ==================== 分页配置 ====================
# 分类详情页每页显示图片数量
CATEGORY_PAGE_SIZE = int(os.getenv('CATEGORY_PAGE_SIZE', 6))

# 首页每页显示分类数量
HOME_PAGE_SIZE = int(os.getenv('HOME_PAGE_SIZE', 6))

# 管理后台列表每页条数（后台看列表，6 条太小）
ADMIN_PAGE_SIZE = int(os.getenv('ADMIN_PAGE_SIZE', 20))


# ==================== 缓存配置 ====================
# 缓存过期时间（秒）
CACHE_EXPIRE_SECONDS = int(os.getenv('CACHE_EXPIRE_SECONDS', 10))


# ==================== 认证配置 ====================
# JWT密钥（生产环境应从环境变量读取）
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Token过期时间（天）
TOKEN_EXPIRE_DAYS = float(os.getenv('TOKEN_EXPIRE_DAYS', 0.5))  # 改为12小时

# Cookie配置
COOKIE_NAME = 'token'
COOKIE_MAX_AGE = int(TOKEN_EXPIRE_DAYS * 24 * 60 * 60)  # 转换为秒


# ==================== CORS配置 ====================
# 允许的源（生产环境应限制具体域名）
# 注意：当使用credentials: 'include'时，不能使用通配符*作为allow_origins
# 但我们在main.py中使用了特殊处理，允许所有域名的请求
ALLOW_ORIGINS = os.getenv('ALLOW_ORIGINS', '*').split(',')

# 允许的HTTP方法
ALLOW_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']

# 允许的请求头
ALLOW_HEADERS = ['Content-Type', 'Authorization']


# ==================== 日志配置 ====================
# 日志级别
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


# 确保必要的目录存在
def ensure_directories():
    """确保必要的目录存在"""
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)
    Path(THUMB_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    Path(IMG_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(STATIC_ROOT_DIR).mkdir(parents=True, exist_ok=True)
