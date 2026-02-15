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

# 图片根目录路径
IMG_ROOT_DIR = os.getenv('IMG_ROOT_DIR', '/app/images')

# 静态文件根目录
STATIC_ROOT_DIR = os.getenv('STATIC_ROOT_DIR', '/app/frontend/static')

# 前端模板根目录
FRONTEND_ROOT_DIR = os.getenv('FRONTEND_ROOT_DIR', '/app/frontend')


# ==================== 分页配置 ====================
# 分类详情页每页显示图片数量
CATEGORY_PAGE_SIZE = int(os.getenv('CATEGORY_PAGE_SIZE', 6))

# 首页每页显示分类数量
HOME_PAGE_SIZE = int(os.getenv('HOME_PAGE_SIZE', 6))


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
    Path(IMG_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(STATIC_ROOT_DIR).mkdir(parents=True, exist_ok=True)
