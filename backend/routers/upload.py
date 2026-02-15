#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传路由模块
处理图片上传相关的API请求
"""

import os
import re
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import Depends, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from ..api.dependencies import get_current_admin
from ..core.config import IMG_ROOT_DIR
from ..utils.utils import validate_safe_path, get_client_ip
from ..core.database import get_db_connection


def _get_image_resolution(file_path: str) -> tuple:
    """
    获取图片分辨率

    Args:
        file_path: 图片文件路径

    Returns:
        tuple: (width, height) 或 (0, 0)
    """
    try:
        print(f"[INFO] 正在获取图片分辨率: {file_path}")
        from PIL import Image
        print("[INFO] PIL库导入成功")
        with Image.open(file_path) as img:
            width, height = img.width, img.height
            print(f"[INFO] 成功获取图片分辨率: {width}x{height}")
            return (width, height)
    except ImportError as e:
        print(f"[ERROR] PIL库未安装，无法获取图片分辨率: {str(e)}")
        return (0, 0)
    except Exception as e:
        print(f"[ERROR] 获取图片分辨率失败: {str(e)}")
        return (0, 0)


def _get_category_id(category_name: str) -> Optional[int]:
    """
    根据分类名称获取分类ID

    Args:
        category_name: 分类名称

    Returns:
        int: 分类ID，如果分类不存在返回None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM categories WHERE name = %s', (category_name,))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        print(f"[ERROR] 获取分类ID失败: {str(e)}")
        return None


async def api_upload_images(
    request: Request,
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    current_user: dict = Depends(get_current_admin)
):
    """
    管理员上传图片API

    Args:
        request: 请求对象，用于获取上传IP地址
        files: 上传的图片文件列表
        category: 目标分类名称
        current_user: 当前登录的管理员用户

    Returns:
        JSONResponse: 上传结果
    """
    try:
        # 获取上传IP地址
        x_forwarded_for = request.headers.get('X-Forwarded-For', '')
        upload_ip = get_client_ip(x_forwarded_for, request.client.host if request.client else '')
        # 获取上传者信息
        uploader = current_user.get('username', 'admin')
        # 验证输入参数
        if not files:
            raise HTTPException(status_code=400, detail="请选择要上传的图片文件")

        if len(files) > 10:
            raise HTTPException(status_code=400, detail="单次最多上传10张图片")

        # 支持的图片格式
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

        # 验证分类名称安全性
        if not validate_safe_path(IMG_ROOT_DIR, category):
            raise HTTPException(status_code=422, detail="非法的分类名称")

        # 获取分类ID
        category_id = _get_category_id(category)

        # 创建分类目录（如果不存在）
        if category == "根目录":
            target_dir = IMG_ROOT_DIR
        else:
            target_dir = os.path.join(IMG_ROOT_DIR, category)
            os.makedirs(target_dir, exist_ok=True)

        # 检查目录是否存在且可写
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if not os.access(target_dir, os.W_OK):
            raise HTTPException(status_code=500, detail="目录无写入权限")

        uploaded_files = []
        failed_files = []

        # 处理每个上传的文件
        for file in files:
            try:
                # 验证文件
                if not file.filename:
                    failed_files.append({"filename": "未知文件", "error": "文件名为空"})
                    continue

                # 检查文件扩展名
                file_ext = os.path.splitext(file.filename)[1].lower()
                if file_ext not in allowed_extensions:
                    failed_files.append({"filename": file.filename, "error": f"不支持的文件格式: {file_ext}"})
                    continue

                # 清理文件名，移除特殊字符
                safe_filename = _sanitize_filename(file.filename)
                file_name_without_ext = os.path.splitext(safe_filename)[0]

                # 智能生成文件名，避免冲突
                unique_filename = _get_unique_filename(target_dir, file_name_without_ext, file_ext)
                file_path = os.path.join(target_dir, unique_filename)

                # 保存文件
                with open(file_path, "wb") as buffer:
                    content = await file.read()
                    # 简单的文件大小检查（5MB限制）
                    if len(content) > 5 * 1024 * 1024:
                        failed_files.append({"filename": file.filename, "error": "文件大小超过5MB限制"})
                        continue
                    buffer.write(content)
                
                # 计算文件MD5值
                import hashlib
                md5_hash = hashlib.md5(content).hexdigest()
                
                # 获取文件格式
                file_format = file_ext[1:]  # 移除点号，例如 .webp -> webp

                # 验证是否为有效的图片文件
                if not _validate_image_file(file_path):
                    os.remove(file_path)  # 删除无效文件
                    failed_files.append({"filename": file.filename, "error": "不是有效的图片文件"})
                    continue

                # 获取图片分辨率
                width, height = _get_image_resolution(file_path)

                # 计算相对路径
                rel_path = os.path.relpath(file_path, IMG_ROOT_DIR)

                # 写入数据库
                try:
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO images (filename, file_path, category_id, file_size, width, height, format, md5, uploader, upload_ip)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        ''', (unique_filename, rel_path, category_id, len(content), width, height, file_format, md5_hash, uploader, upload_ip))
                        image_id = cursor.fetchone()[0]
                        print(f"[INFO] 图片已写入数据库: ID={image_id}, 文件名={unique_filename}")
                except Exception as db_error:
                    print(f"[ERROR] 写入数据库失败: {str(db_error)}")
                    # 数据库写入失败，删除已保存的文件
                    os.remove(file_path)
                    failed_files.append({"filename": file.filename, "error": "数据库写入失败"})
                    continue

                uploaded_files.append({
                    "filename": file.filename,
                    "saved_name": unique_filename,
                    "path": rel_path,
                    "url": f"/image?path={rel_path}",
                    "size": len(content)
                })

            except Exception as e:
                failed_files.append({"filename": file.filename, "error": str(e)})
                # 清理可能创建的文件
                if 'file_path' in locals() and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass

        # 构造响应
        response_data = {
            "code": 200,
            "msg": "上传完成",
            "data": {
                "uploaded_count": len(uploaded_files),
                "failed_count": len(failed_files),
                "uploaded_files": uploaded_files,
                "failed_files": failed_files
            }
        }

        # 如果所有文件都失败，返回400状态码
        if len(uploaded_files) == 0 and len(failed_files) > 0:
            response_data["code"] = 400
            response_data["msg"] = "上传失败"

        status_code = 200 if response_data["code"] == 200 else 400
        return JSONResponse(content=response_data, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传过程中发生错误: {str(e)}")


def _validate_image_file(file_path: str) -> bool:
    """
    验证文件是否为有效的图片文件（简单的魔数检查）

    Args:
        file_path: 文件路径

    Returns:
        bool: 是否为有效图片
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)

        # 常见图片格式的魔数
        magic_numbers = [
            b'\xff\xd8\xff',  # JPEG
            b'\x89PNG\r\n\x1a\n',  # PNG
            b'GIF87a',  # GIF
            b'GIF89a',  # GIF
            b'RIFF',  # WebP (需要进一步检查)
        ]

        for magic in magic_numbers:
            if header.startswith(magic):
                return True

        # WebP格式特殊处理
        if header.startswith(b'RIFF') and len(header) >= 12:
            if header[8:12] == b'WEBP':
                return True

        return False
    except:
        return False


def _sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不安全字符

    Args:
        filename: 原始文件名

    Returns:
        str: 安全的文件名
    """
    # 获取文件名和扩展名
    name, ext = os.path.splitext(filename)

    # 移除危险字符，只保留中文、字母、数字、下划线、横线和点
    # 使用正则表达式替换不安全字符为下划线
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)

    # 移除开头和结尾的空格和点
    safe_name = safe_name.strip('. ')

    # 如果清理后为空，使用默认名称
    if not safe_name:
        safe_name = 'unnamed'

    return safe_name + ext


def _get_unique_filename(target_dir: str, name_without_ext: str, ext: str) -> str:
    """
    生成唯一文件名，避免冲突

    Args:
        target_dir: 目标目录
        name_without_ext: 不含扩展名的文件名
        ext: 文件扩展名（包含点）

    Returns:
        str: 唯一的文件名
    """
    base_filename = name_without_ext + ext
    file_path = os.path.join(target_dir, base_filename)

    # 如果文件不存在，直接使用原文件名
    if not os.path.exists(file_path):
        return base_filename

    # 如果文件已存在，添加序号
    counter = 1
    while True:
        new_filename = f"{name_without_ext}_{counter}{ext}"
        new_file_path = os.path.join(target_dir, new_filename)

        if not os.path.exists(new_file_path):
            return new_filename

        counter += 1
        # 防止无限循环
        if counter > 1000:
            # 如果尝试1000次仍然失败，使用UUID作为后备方案
            return f"{name_without_ext}_{uuid.uuid4().hex[:8]}{ext}"