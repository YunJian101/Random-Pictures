#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本管理模块
=============

存储和管理应用版本信息
"""

# 当前应用版本号
__version__ = "1.2.0"

# 版本历史
VERSION_HISTORY = [
    "1.2.0"  # 增强功能版本
]

# 版本描述
VERSION_DESCRIPTION = {
    "1.2.0": "随机图API - 功能增强版"
}


def get_version() -> str:
    """
    获取当前版本号
    
    Returns:
        str: 当前版本号
    """
    return __version__


def get_version_description(version: str = None) -> str:
    """
    获取版本描述
    
    Args:
        version: 版本号，默认为当前版本
    
    Returns:
        str: 版本描述
    """
    if version is None:
        version = __version__
    return VERSION_DESCRIPTION.get(version, "未知版本")


def get_version_history() -> list:
    """
    获取版本历史
    
    Returns:
        list: 版本历史列表
    """
    return VERSION_HISTORY.copy()