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


# ==================== 站点个性化配置 ====================
# 站点名称
SITE_NAME = os.getenv('SITE_NAME', '随机图API')

# 站点图标URL
FAVICON_URL = os.getenv('FAVICON_URL', '')

# ICP备案信息
ICP_BEIAN_CODE = os.getenv('ICP_BEIAN_CODE', '')
ICP_BEIAN_URL = os.getenv('ICP_BEIAN_URL', 'https://beian.miit.gov.cn')


# ==================== 导航栏配置 ====================
# 导航栏各按钮的链接配置
NAV_HOME_URL = os.getenv('NAV_HOME_URL', '/')
NAV_BLOG_URL = os.getenv('NAV_BLOG_URL', '')
NAV_GITHUB_URL = os.getenv('NAV_GITHUB_URL', '')
NAV_CUSTOM_TEXT = os.getenv('NAV_CUSTOM_TEXT', '')
NAV_CUSTOM_URL = os.getenv('NAV_CUSTOM_URL', '')


# ==================== 页面内容配置 ====================
# 首页欢迎语
WELCOME_MESSAGE = os.getenv('WELCOME_MESSAGE', '欢迎使用是飞鱼随机图API')

# 版权声明信息
COPYRIGHT_NOTICE = os.getenv('COPYRIGHT_NOTICE', '本站所有图片均为用户上传，仅作学习所有，若有侵权，请与我联系我将及时删除！')


# ==================== 分页配置 ====================
# 分类详情页每页显示图片数量
CATEGORY_PAGE_SIZE = int(os.getenv('CATEGORY_PAGE_SIZE', 9))

# 首页每页显示分类数量
HOME_PAGE_SIZE = int(os.getenv('HOME_PAGE_SIZE', 9))


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
