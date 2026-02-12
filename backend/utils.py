#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
============
"""

import os
import time
import ipaddress
from pathlib import Path
from typing import List, Tuple
from urllib.parse import unquote

from .config import SUPPORTED_IMAGE_FORMATS, CACHE_EXPIRE_SECONDS
from .cache import global_cache


def validate_safe_path(base_path: str, target_path: str) -> bool:
    """
    验证路径是否安全,防止路径遍历攻击
    """
    try:
        # 1. 基础路径规范化
        base_path = os.path.abspath(base_path)

        # 2. 解析URL编码的路径
        decoded_path = target_path
        for _ in range(3):
            decoded_path = unquote(decoded_path)

        # 3. 检查路径遍历模式
        dangerous_patterns = [
            '..', '%2e%2e', '%2e.', '.%2e', '%252e%252e',
            '..\\', '%2e%2e\\', '\\.\\', '%2e%2e%5c',
        ]
        decoded_lower = decoded_path.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in decoded_lower:
                return False

        # 4. 规范化路径
        normalized = os.path.normpath(decoded_path)

        # 5. 检查绝对路径
        if os.path.isabs(normalized):
            if not normalized.startswith(base_path):
                return False
            safe_path = normalized
        else:
            safe_path = os.path.normpath(os.path.join(base_path, normalized))

        # 6. 再次规范化并验证
        safe_path = os.path.abspath(safe_path)

        # 7. 检查是否在基础目录内
        if not safe_path.startswith(base_path + os.sep) and safe_path != base_path:
            return False

        # 8. 检查软链接逃逸
        if os.path.lexists(safe_path):
            real_path = os.path.realpath(safe_path)
            if not real_path.startswith(base_path + os.sep) and real_path != base_path:
                return False

        # 9. 检查空字节
        if '\x00' in decoded_path or '\x00' in safe_path:
            return False

        return True
    except Exception:
        return False


def validate_image_file(file_path: str) -> bool:
    """
    验证文件是否为有效的图片文件
    """
    if not os.path.isfile(file_path):
        return False

    _, ext = os.path.splitext(file_path.lower())
    if ext not in SUPPORTED_IMAGE_FORMATS:
        return False

    # 检查文件魔数
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)

        if len(header) < 2:
            return False

        # JPEG: FF D8
        if header[:2] == b'\xff\xd8':
            return True

        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return True

        # GIF: 47 49 46 38 (GIF8)
        if header[:4] == b'GIF8':
            return True

        # WebP: 52 49 46 46 ... 57 45 42 50 (RIFF....WEBP)
        if header[:4] == b'RIFF' and len(header) >= 12:
            if header[8:12] == b'WEBP':
                return True

        return False
    except Exception:
        return False


def safe_listdir(dir_path: str) -> List[str]:
    """
    安全的目录列表函数,过滤软链接
    """
    if not os.path.isdir(dir_path):
        return []

    entries = []
    try:
        for name in os.listdir(dir_path):
            full_path = os.path.join(dir_path, name)
            if os.path.islink(full_path):
                continue
            entries.append(name)
    except Exception:
        return []

    return entries


def get_directory_modify_time(dir_path: str) -> float:
    """
    获取目录最后修改时间（递归检测子文件/目录）
    """
    if not os.path.exists(dir_path):
        return 0

    try:
        max_mtime = os.path.getmtime(dir_path)

        if os.path.isdir(dir_path):
            for root, dirs, files in os.walk(dir_path):
                for d in dirs:
                    try:
                        mtime = os.path.getmtime(os.path.join(root, d))
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except Exception:
                        continue

                for f in files:
                    try:
                        mtime = os.path.getmtime(os.path.join(root, f))
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except Exception:
                        continue

        return max_mtime
    except Exception:
        return 0


def get_all_images_in_dir(target_dir: str) -> List[str]:
    """
    获取目录下所有图片路径（带缓存，保证实时性）
    """
    cache_key = f"img_{target_dir}"
    current_mtime = get_directory_modify_time(target_dir)
    last_mtime = global_cache.get_dir_mtime(cache_key)

    need_refresh = False

    if current_mtime != last_mtime:
        need_refresh = True
        global_cache.set_dir_mtime(cache_key, current_mtime)
    else:
        cache_info = global_cache.get_image_cache(cache_key)
        if not cache_info or time.time() - cache_info["time"] >= CACHE_EXPIRE_SECONDS:
            need_refresh = True

    if need_refresh:
        image_paths = []
        if os.path.isdir(target_dir):
            for root, _, files in os.walk(target_dir):
                for file_name in files:
                    if file_name.lower().endswith(SUPPORTED_IMAGE_FORMATS):
                        image_paths.append(os.path.join(root, file_name))

        global_cache.set_image_cache(cache_key, image_paths)
        return image_paths

    return global_cache.get_image_cache(cache_key)["data"]


def scan_image_directory(directory_path: str) -> List[str]:
    """
    扫描目录中的所有图片文件
    """
    image_paths = []

    if not os.path.exists(directory_path):
        return image_paths

    try:
        for root, dirs, files in os.walk(directory_path):
            for file_name in files:
                if file_name.lower().endswith(SUPPORTED_IMAGE_FORMATS):
                    full_path = os.path.join(root, file_name)
                    image_paths.append(full_path)
    except Exception as e:
        print(f"扫描目录时出错: {e}")

    return image_paths


def is_valid_public_ip(ip_str: str) -> bool:
    """验证是否为有效的公网IP地址"""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            return False
        if ip.version == 4:
            if ip.is_unspecified:
                return False
            first_octet = int(ip.packed[0])
            if first_octet >= 224 and first_octet <= 255:
                return False
        return True
    except ValueError:
        return False


def get_mime_type(file_path: str) -> str:
    """根据文件扩展名获取MIME类型"""
    _, ext = os.path.splitext(file_path.lower())
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    return mime_types.get(ext, 'application/octet-stream')


def get_client_ip(x_forwarded_for: str, remote_addr: str) -> str:
    """
    获取客户端真实IP地址

    优先从 X-Forwarded-For 头获取真实IP
    """
    if x_forwarded_for:
        ip_list = [ip.strip() for ip in x_forwarded_for.split(',')]
        for ip in ip_list:
            if is_valid_public_ip(ip):
                return ip
    return remote_addr
