#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI Random Pictures API - 后端模块
==============================

这个包包含了使用FastAPI重构的随机图API服务的所有后端功能。

模块结构:
    - config.py: 配置管理
    - database.py: 数据库连接和会话管理
    - models.py: 数据库模型定义
    - schemas.py: Pydantic模型定义
    - auth.py: 认证和授权逻辑
    - image_service.py: 图片服务核心逻辑
    - user_service.py: 用户服务核心逻辑
    - utils.py: 工具函数
    - cache.py: 缓存管理
    - main.py: FastAPI应用入口

作者: 云笺
版本: 1.0.0 (FastAPI版)
"""

__version__ = "1.0.0"
__version_date__ = "2026-02-15"
__author__ = "云笺"
