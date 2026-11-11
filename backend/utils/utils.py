#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
============
"""

import os
import asyncio
import ipaddress
from urllib.parse import unquote

from ..core.config import SUPPORTED_IMAGE_FORMATS


def validate_safe_path(base_path: str, target_path: str) -> bool:
    """
    验证路径是否安全,防止路径遍历攻击
    
    Args:
        base_path: 基础路径，目标路径应该在这个路径内
        target_path: 需要验证的目标路径
        
    Returns:
        bool: 路径是否安全
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



async def execute_count(conn, sql: str, *args) -> int:
    """执行写操作并返回受影响行数

    注意：asyncpg 的 ``Connection.execute()`` 返回的是 ``'DELETE 1'`` 这类
    状态字符串，**没有** ``rowcount`` 属性（沿用 psycopg2 的写法会直接抛
    AttributeError，被 except 吞掉后表现为"操作成功却提示失败"）。
    """
    status = await conn.execute(sql, *args)
    if not status:
        return 0
    try:
        return int(str(status).split()[-1])
    except (IndexError, ValueError):
        return 0


def validate_local_path(path: str) -> tuple[bool, str]:
    """
    验证本地路径是否安全,防止路径遍历攻击
    
    Args:
        path: 需要验证的本地路径
        
    Returns:
        tuple[bool, str]: (是否安全, 错误信息)
    """
    try:
        # 1. 检查路径是否为空
        if not path:
            return True, ""

        # 2. 解析URL编码的路径
        decoded_path = path
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
                return False, "本地路径不能包含路径遍历字符（../）"

        # 4. 检查空字节
        if '\x00' in decoded_path:
            return False, "本地路径不能包含空字节"

        return True, ""
    except Exception as e:
        return False, f"路径验证失败: {str(e)}"


def is_remote_url(url: str) -> bool:
    """
    检查字符串是否为远程URL
    
    Args:
        url: 需要检查的字符串
        
    Returns:
        bool: 是否为远程URL
    """
    import re
    url_pattern = r'^https?://[^/$.?#]+[^ ]*$'
    return bool(re.match(url_pattern, url))


async def validate_image_file(file_path: str) -> bool:
    """
    验证文件是否为有效的图片文件
    """
    if not await asyncio.to_thread(os.path.isfile, file_path):
        return False

    _, ext = os.path.splitext(file_path.lower())
    if ext not in SUPPORTED_IMAGE_FORMATS:
        return False

    # 检查文件魔数
    try:
        def read_header():
            with open(file_path, 'rb') as f:
                return f.read(12)
        
        header = await asyncio.to_thread(read_header)

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


async def get_error_page(error_type: str, context: dict = None) -> str:
    """
    获取错误页面内容
    
    Args:
        error_type: 错误类型，如 "404分类不存在"、"404图片不存在" 等
        context: 错误页面模板上下文，用于替换占位符
        
    Returns:
        错误页面HTML内容，如果页面不存在则返回空字符串
    """
    # 使用容器路径构建错误页面路径
    # 从项目根目录开始构建绝对路径
    error_page_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "Status_Code", f"{error_type}.html"))
    if not await asyncio.to_thread(os.path.exists, error_page_path):
        print(f"[ERROR] 错误页面不存在: {error_page_path}")
        return ""
    
    try:
        def read_error_page():
            with open(error_page_path, "r", encoding="utf-8") as f:
                return f.read()
        
        content = await asyncio.to_thread(read_error_page)
        
        # 替换占位符
        if context:
            for key, value in context.items():
                placeholder = "{{" + key + "}}"
                content = content.replace(placeholder, str(value) if value is not None else "")
        
        return content
    except Exception as e:
        print(f"[ERROR] 读取错误页面失败: {str(e)}")
        return ""
