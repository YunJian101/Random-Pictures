#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缩略图服务
==========

列表 / 卡片只需要几十像素宽的预览，却去拉几 MB 的原图，是这类图库站最容易被
忽视的带宽黑洞。这里按需生成缩略图并落盘缓存：

    /thumb?path=风景/a.jpg&w=320
    /random?type=风景&w=320        （随机接口也支持带宽度）

同一张图 + 同一宽度只生成一次，之后直接走文件缓存。
"""

import asyncio
import hashlib
import os
import time
from typing import Optional

from ..core.config import IMG_ROOT_DIR, THUMB_CACHE_DIR, THUMB_QUALITY, THUMB_SIZES

# 命中缓存时给一个很长的强缓存，URL 里已经带了宽度和路径，内容不会变
THUMB_CACHE_CONTROL = 'public, max-age=2592000'   # 30 天

# 格式白名单：webp 比 jpeg 小 25%~35%，浏览器 Accept 里声明支持时优先给 webp
THUMB_FORMATS = ('webp', 'jpeg')
WEBP_QUALITY = 80


def normalize_width(width: Optional[int]) -> Optional[int]:
    """把请求的宽度吸附到白名单内（防止被刷出无数尺寸撑爆磁盘）"""
    if not width:
        return None
    try:
        value = int(width)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    # 取最接近的允许宽度
    return min(THUMB_SIZES, key=lambda s: abs(s - value))


def pick_format(accept: str) -> str:
    """按 Accept 头挑输出格式；不支持 webp 的老客户端继续给 jpeg"""
    return 'webp' if 'image/webp' in (accept or '').lower() else 'jpeg'


def _cache_path(rel_path: str, width: int, fmt: str = 'jpeg') -> str:
    digest = hashlib.sha1(rel_path.encode('utf-8')).hexdigest()
    ext = os.path.splitext(rel_path)[1].lower().lstrip('.') or 'img'
    suffix = 'webp' if fmt == 'webp' else 'jpg'
    return os.path.join(THUMB_CACHE_DIR, str(width), f'{digest}.{ext}.{suffix}')


def _build_thumb(source: str, target: str, width: int, fmt: str = 'jpeg') -> None:
    """同步生成缩略图（调用方放进线程池执行，避免阻塞事件循环）"""
    from PIL import Image

    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + '.tmp'

    with Image.open(source) as img:
        # 动图取第一帧；带透明通道的转白底
        if getattr(img, 'is_animated', False):
            img.seek(0)
        img = img.convert('RGBA')

        # 只缩不放：原图本来就窄就保持原尺寸
        if img.width > width:
            height = max(1, round(img.height * width / img.width))
            img = img.resize((width, height), Image.LANCZOS)

        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])

        if fmt == 'webp':
            # method=6 是 Pillow 里压缩率最高的一档，缩略图尺寸小、值得多花点 CPU
            background.save(tmp, 'WEBP', quality=WEBP_QUALITY, method=6)
        else:
            background.save(tmp, 'JPEG', quality=THUMB_QUALITY, optimize=True, progressive=True)

    os.replace(tmp, target)


def _expected_names(rel_paths) -> set:
    """由图片路径反推出「应该存在」的缓存文件名（不含宽度目录）"""
    names = set()
    for rel in rel_paths:
        digest = hashlib.sha1(rel.encode('utf-8')).hexdigest()
        ext = os.path.splitext(rel)[1].lower().lstrip('.') or 'img'
        for suffix in ('jpg', 'webp'):
            names.add(f'{digest}.{ext}.{suffix}')
    return names


async def cleanup_orphan_thumbs() -> int:
    """清理源图已删除、但缓存还留着的缩略图（含残留的 .tmp 文件）

    缓存文件名是 sha1(相对路径)，本身不可逆；这里反过来用 images 表里的
    全部 file_path 算出「该有哪些文件」，再删掉目录里多出来的，避免误删。
    """
    try:
        from ..core.database import get_async_db_connection

        async with get_async_db_connection() as conn:
            rows = await conn.fetch('SELECT file_path FROM images')

        valid = _expected_names([r['file_path'] for r in rows if r['file_path']])

        removed = 0
        if not os.path.isdir(THUMB_CACHE_DIR):
            return 0

        for width_dir in os.scandir(THUMB_CACHE_DIR):
            if not width_dir.is_dir():
                continue
            for entry in os.scandir(width_dir.path):
                if not entry.is_file():
                    continue
                name = entry.name
                # 半成品文件：生成过程崩了留下的
                if name.endswith('.tmp'):
                    if os.path.getmtime(entry.path) < time.time() - 3600:
                        os.remove(entry.path)
                        removed += 1
                    continue
                if name not in valid:
                    os.remove(entry.path)
                    removed += 1

        return removed

    except Exception as e:
        print(f'[WARN] 清理孤儿缩略图失败: {str(e)}')
        return 0


async def ensure_thumb(rel_path: str, width: int, fmt: str = 'jpeg') -> Optional[str]:
    """确保缩略图存在，返回缓存文件路径；失败返回 None

    rel_path 必须是相对图片根目录的路径（已通过安全校验）。
    """
    source = os.path.join(IMG_ROOT_DIR, rel_path)
    if not os.path.isfile(source):
        return None

    if fmt not in THUMB_FORMATS:
        fmt = 'jpeg'
    target = _cache_path(rel_path, width, fmt)
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        # 源文件更新后让缓存失效（按修改时间比对）
        try:
            if os.path.getmtime(target) >= os.path.getmtime(source):
                return target
        except OSError:
            pass

    try:
        await asyncio.to_thread(_build_thumb, source, target, width, fmt)
        return target
    except Exception as e:
        print(f'[ERROR] 生成缩略图失败 {rel_path}: {str(e)}')
        return None
