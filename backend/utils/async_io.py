#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步IO操作工具模块
==================

提供异步的文件IO操作和其他IO相关的异步工具函数
"""

import asyncio
import os
from pathlib import Path
import aiofiles


async def async_exists(path: str) -> bool:
    """
    异步检查文件或目录是否存在
    
    Args:
        path: 文件或目录路径
    
    Returns:
        bool: 存在返回True，否则返回False
    """
    return await asyncio.to_thread(os.path.exists, path)


async def async_isfile(path: str) -> bool:
    """
    异步检查路径是否为文件
    
    Args:
        path: 路径
    
    Returns:
        bool: 是文件返回True，否则返回False
    """
    return await asyncio.to_thread(os.path.isfile, path)


async def async_isdir(path: str) -> bool:
    """
    异步检查路径是否为目录
    
    Args:
        path: 路径
    
    Returns:
        bool: 是目录返回True，否则返回False
    """
    return await asyncio.to_thread(os.path.isdir, path)


async def async_makedirs(path: str, exist_ok: bool = False) -> None:
    """
    异步创建目录
    
    Args:
        path: 目录路径
        exist_ok: 如果目录已存在，是否抛出异常
    """
    await asyncio.to_thread(os.makedirs, path, exist_ok=exist_ok)


async def async_remove(path: str) -> None:
    """
    异步删除文件
    
    Args:
        path: 文件路径
    """
    await asyncio.to_thread(os.remove, path)


async def async_rename(src: str, dst: str) -> None:
    """
    异步重命名文件或目录
    
    Args:
        src: 源路径
        dst: 目标路径
    """
    await asyncio.to_thread(os.rename, src, dst)


async def async_stat(path: str) -> os.stat_result:
    """
    异步获取文件状态
    
    Args:
        path: 文件路径
    
    Returns:
        os.stat_result: 文件状态
    """
    return await asyncio.to_thread(os.stat, path)


async def async_getsize(path: str) -> int:
    """
    异步获取文件大小
    
    Args:
        path: 文件路径
    
    Returns:
        int: 文件大小（字节）
    """
    return await asyncio.to_thread(os.path.getsize, path)


async def async_open_read(path: str, encoding: str = None) -> str:
    """
    异步读取文件内容
    
    Args:
        path: 文件路径
        encoding: 编码格式，None表示二进制读取
    
    Returns:
        str: 文件内容
    """
    async with aiofiles.open(path, 'r', encoding=encoding) as f:
        return await f.read()


async def async_open_write(path: str, content: str, encoding: str = None) -> None:
    """
    异步写入文件内容
    
    Args:
        path: 文件路径
        content: 要写入的内容
        encoding: 编码格式，None表示二进制写入
    """
    async with aiofiles.open(path, 'w', encoding=encoding) as f:
        await f.write(content)


async def async_open_append(path: str, content: str, encoding: str = None) -> None:
    """
    异步追加文件内容
    
    Args:
        path: 文件路径
        content: 要追加的内容
        encoding: 编码格式，None表示二进制追加
    """
    async with aiofiles.open(path, 'a', encoding=encoding) as f:
        await f.write(content)


async def async_listdir(path: str) -> list:
    """
    异步列出目录内容
    
    Args:
        path: 目录路径
    
    Returns:
        list: 目录中的文件和子目录列表
    """
    return await asyncio.to_thread(os.listdir, path)


async def async_relpath(path: str, start: str = os.curdir) -> str:
    """
    异步获取相对路径
    
    Args:
        path: 绝对路径
        start: 起始路径
    
    Returns:
        str: 相对路径
    """
    return await asyncio.to_thread(os.path.relpath, path, start)


async def async_abspath(path: str) -> str:
    """
    异步获取绝对路径
    
    Args:
        path: 相对路径
    
    Returns:
        str: 绝对路径
    """
    return await asyncio.to_thread(os.path.abspath, path)


async def async_joinpath(*paths) -> str:
    """
    异步连接路径
    
    Args:
        *paths: 要连接的路径部分
    
    Returns:
        str: 连接后的路径
    """
    return os.path.join(*paths)
