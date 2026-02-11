#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存管理模块
============

这个模块提供简单的内存缓存功能
"""

import time
from typing import Any, Dict, Optional


class CacheManager:
    """缓存管理器"""

    def __init__(self):
        # 全局缓存字典
        self._cache: Dict[str, Any] = {
            "dir_mtime": {},     # 目录修改时间缓存
            "image_cache": {},   # 图片路径缓存
        }

    def get(self, key: Optional[str] = None) -> Any:
        """
        获取缓存数据

        参数:
            key: 缓存键名，如果为None则返回整个缓存字典

        返回:
            缓存数据或None
        """
        if key is None:
            return self._cache.copy()
        return self._cache.get(key, None)

    def update(self, key: str, value: Any) -> None:
        """
        更新缓存数据

        参数:
            key: 缓存键名
            value: 要存储的值
        """
        self._cache[key] = value

    def clear(self, key: Optional[str] = None) -> None:
        """
        清除缓存数据

        参数:
            key: 缓存键名，如果为None则清除所有缓存
        """
        if key is None:
            self._cache.clear()
            self._cache.update({
                "dir_mtime": {},
                "image_cache": {}
            })
        else:
            if key in self._cache:
                del self._cache[key]

    def get_dir_mtime(self, path: str) -> float:
        """获取目录的缓存修改时间"""
        return self._cache.get("dir_mtime", {}).get(path, 0)

    def set_dir_mtime(self, path: str, mtime: float) -> None:
        """设置目录的缓存修改时间"""
        if "dir_mtime" not in self._cache:
            self._cache["dir_mtime"] = {}
        self._cache["dir_mtime"][path] = mtime

    def get_image_cache(self, path: str) -> Optional[Dict]:
        """获取目录的图片缓存"""
        return self._cache.get("image_cache", {}).get(path)

    def set_image_cache(self, path: str, data: list) -> None:
        """设置目录的图片缓存"""
        if "image_cache" not in self._cache:
            self._cache["image_cache"] = {}
        self._cache["image_cache"][path] = {
            "time": time.time(),
            "data": data
        }


# 全局缓存实例
global_cache = CacheManager()
