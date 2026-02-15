#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片服务模块 - 核心业务逻辑
==========================
"""

import os
import random
from datetime import datetime
from typing import List, Optional, Dict
from urllib.parse import quote

from ..core.config import IMG_ROOT_DIR, HOME_PAGE_SIZE, CATEGORY_PAGE_SIZE
from ..utils.utils import safe_listdir, get_all_images_in_dir, get_directory_modify_time
from ..utils.cache import global_cache


def get_all_categories() -> List[str]:
    """
    获取所有分类名称列表
    """
    categories_data = get_image_categories()
    return list(categories_data.keys())


def get_images_by_category(category_name: str) -> List[dict]:
    """
    获取指定分类下的所有图片
    """
    images = []

    if category_name == "根目录":
        if os.path.isdir(IMG_ROOT_DIR):
            for file_name in safe_listdir(IMG_ROOT_DIR):
                file_path = os.path.join(IMG_ROOT_DIR, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    rel_path = os.path.relpath(file_path, IMG_ROOT_DIR)
                    images.append({
                        "name": file_name,
                        "url": f"/image?path={quote(rel_path)}",
                        "path": rel_path
                    })
    else:
        dir_path = os.path.join(IMG_ROOT_DIR, category_name)
        if os.path.isdir(dir_path):
            dir_images = get_all_images_in_dir(dir_path)
            for img_path in dir_images:
                rel_path = os.path.relpath(img_path, IMG_ROOT_DIR)
                images.append({
                    "name": os.path.basename(img_path),
                    "url": f"/image?path={quote(rel_path)}",
                    "path": rel_path
                })

    return images


def get_image_categories() -> Dict[str, List[dict]]:
    """
    获取所有图片分类（从数据库读取）
    所有分类必须是数据库中存在的分类
    """
    try:
        from ..core.database import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        categories = {}
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 从数据库查询所有启用状态的分类
            cursor.execute('''
                SELECT id, name FROM categories 
                WHERE status = 'enabled'
                ORDER BY created_at DESC
            ''')
            db_categories = cursor.fetchall()
            
            # 为每个分类查询对应的图片
            for category in db_categories:
                cursor.execute('''
                    SELECT filename, file_path FROM images 
                    WHERE category_id = %s AND status = 'enabled'
                    ORDER BY created_at DESC
                ''', (category['id'],))
                images = cursor.fetchall()
                
                img_list = []
                for img in images:
                    img_list.append({
                        "name": img['filename'],
                        "url": f"/image?path={quote(img['file_path'])}",
                        "path": img['file_path']
                    })
                
                if img_list:
                    categories[category['name']] = img_list
        
        return categories
    except Exception as e:
        print(f"[ERROR] 从数据库获取分类失败: {str(e)}")
        # 发生错误时回退到文件系统扫描，但不包含根目录分类
        categories = {}
        
        # 处理子文件夹分类
        if os.path.isdir(IMG_ROOT_DIR):
            for dir_name in safe_listdir(IMG_ROOT_DIR):
                dir_path = os.path.join(IMG_ROOT_DIR, dir_name)
                if os.path.isdir(dir_path):
                    dir_images = get_all_images_in_dir(dir_path)
                    img_list = []
                    for img_path in dir_images:
                        rel_path = os.path.relpath(img_path, IMG_ROOT_DIR)
                        img_list.append({
                            "name": os.path.basename(img_path),
                            "url": f"/image?path={quote(rel_path)}",
                            "path": rel_path
                        })

                    if img_list:
                        categories[dir_name] = img_list

        return categories


def get_paginated_categories(page: int = 1) -> dict:
    """
    分页获取分类列表（从数据库读取）
    所有分类必须是数据库中存在的分类
    """
    try:
        from ..core.database import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 查询所有启用状态的分类，带图片数量
            cursor.execute('''
                SELECT 
                    c.id, 
                    c.name, 
                    c.description, 
                    c.status, 
                    c.created_at, 
                    c.updated_at,
                    COUNT(i.id) as image_count
                FROM categories c
                LEFT JOIN images i ON c.id = i.category_id AND i.status = 'enabled'
                WHERE c.status = 'enabled'
                GROUP BY c.id
                ORDER BY c.created_at DESC
            ''')
            all_categories = cursor.fetchall()
            
            # 计算分页信息
            total_categories = len(all_categories)
            total_pages = (total_categories + HOME_PAGE_SIZE - 1) // HOME_PAGE_SIZE
            page = max(1, min(page, total_pages))
            
            # 计算分页范围
            start = (page - 1) * HOME_PAGE_SIZE
            end = start + HOME_PAGE_SIZE
            paginated_categories = all_categories[start:end]
            
            # 构建分类字典
            categories_dict = {}
            for category in paginated_categories:
                # 查询该分类下的图片
                cursor.execute('''
                    SELECT filename, file_path FROM images 
                    WHERE category_id = %s AND status = 'enabled'
                    ORDER BY created_at DESC
                ''', (category['id'],))
                images = cursor.fetchall()
                
                img_list = []
                for img in images:
                    img_list.append({
                        "name": img['filename'],
                        "url": f"/image?path={quote(img['file_path'])}",
                        "path": img['file_path']
                    })
                
                if img_list:
                    categories_dict[category['name']] = img_list
            
            return {
                "categories": categories_dict,
                "current_page": page,
                "total_pages": total_pages,
                "total_categories": total_categories,
                "items_per_page": HOME_PAGE_SIZE
            }
    except Exception as e:
        print(f"[ERROR] 从数据库获取分页分类失败: {str(e)}")
        # 发生错误时回退到原逻辑
        all_categories = get_image_categories()
        category_list = list(all_categories.items())

        total_categories = len(category_list)
        total_pages = (total_categories + HOME_PAGE_SIZE - 1) // HOME_PAGE_SIZE

        page = max(1, min(page, total_pages))

        start = (page - 1) * HOME_PAGE_SIZE
        end = start + HOME_PAGE_SIZE

        return {
            "categories": dict(category_list[start:end]),
            "current_page": page,
            "total_pages": total_pages,
            "total_categories": total_categories,
            "items_per_page": HOME_PAGE_SIZE
        }


def get_paginated_category_images(category_name: str, page: int = 1) -> dict:
    """
    分页获取分类下图片（从数据库读取）
    所有分类必须是数据库中存在的分类
    """
    try:
        from ..core.database import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 查询分类ID - 所有分类必须从数据库中查询
            cursor.execute('''
                SELECT id FROM categories 
                WHERE name = %s AND status = 'enabled'
            ''', (category_name,))
            category = cursor.fetchone()
            
            if not category:
                return {
                    "category_name": category_name,
                    "images": [],
                    "current_page": 1,
                    "total_pages": 0,
                    "total_images": 0,
                    "page_size": CATEGORY_PAGE_SIZE
                }
            
            # 查询该分类下的所有图片
            cursor.execute('''
                SELECT filename, file_path FROM images 
                WHERE category_id = %s AND status = 'enabled'
                ORDER BY created_at DESC
            ''', (category['id'],))
            all_images = cursor.fetchall()
            
            # 转换为所需格式
            formatted_images = []
            for img in all_images:
                formatted_images.append({
                    "name": img['filename'],
                    "url": f"/image?path={quote(img['file_path'])}",
                    "path": img['file_path']
                })
            
            # 计算分页信息
            total_images = len(formatted_images)
            total_pages = (total_images + CATEGORY_PAGE_SIZE - 1) // CATEGORY_PAGE_SIZE
            page = max(1, min(page, total_pages))
            
            # 计算分页范围
            start = (page - 1) * CATEGORY_PAGE_SIZE
            end = start + CATEGORY_PAGE_SIZE
            
            return {
                "category_name": category_name,
                "images": formatted_images[start:end],
                "current_page": page,
                "total_pages": total_pages,
                "total_images": total_images,
                "page_size": CATEGORY_PAGE_SIZE
            }
    except Exception as e:
        print(f"[ERROR] 从数据库获取分类图片失败: {str(e)}")
        # 发生错误时回退到文件系统扫描，但不支持根目录分类
        all_images = []
        
        dir_path = os.path.join(IMG_ROOT_DIR, category_name)
        if os.path.isdir(dir_path):
            dir_images = get_all_images_in_dir(dir_path)
            for img_path in dir_images:
                rel_path = os.path.relpath(img_path, IMG_ROOT_DIR)
                all_images.append({
                    "name": os.path.basename(img_path),
                    "url": f"/image?path={quote(rel_path)}",
                    "path": rel_path
                })
        
        total_images = len(all_images)
        total_pages = (total_images + CATEGORY_PAGE_SIZE - 1) // CATEGORY_PAGE_SIZE
        page = max(1, min(page, total_pages))
        
        start = (page - 1) * CATEGORY_PAGE_SIZE
        end = start + CATEGORY_PAGE_SIZE
        
        return {
            "category_name": category_name,
            "images": all_images[start:end],
            "current_page": page,
            "total_pages": total_pages,
            "total_images": total_images,
            "page_size": CATEGORY_PAGE_SIZE
        }


def get_random_image_in_category(category_name: str) -> Optional[dict]:
    """
    分类随机：从数据库读取指定分类的图片，随机返回一张
    所有分类必须是数据库中存在的分类
    """
    try:
        from ..core.database import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 查询分类ID - 所有分类必须从数据库中查询
            cursor.execute('''
                SELECT id FROM categories 
                WHERE name = %s AND status = 'enabled'
            ''', (category_name,))
            category = cursor.fetchone()
            
            if not category:
                return None
            
            # 从该分类中随机选择一张图片
            cursor.execute('''
                SELECT filename, file_path FROM images 
                WHERE category_id = %s AND status = 'enabled'
                ORDER BY RANDOM() LIMIT 1
            ''', (category['id'],))
            
            image = cursor.fetchone()
            
            if not image:
                return {"error": "empty"}
            
            # 返回与原格式相同的结果
            return {
                "name": image['filename'],
                "url": f"/image?path={quote(image['file_path'])}",
                "path": image['file_path']
            }
    except Exception as e:
        print(f"[ERROR] 从数据库获取随机图片失败: {str(e)}")
        # 发生错误时回退到文件系统扫描，但仍然要求分类目录存在
        dir_path = os.path.join(IMG_ROOT_DIR, category_name)
        if not os.path.isdir(dir_path):
            return None

        dir_images = get_all_images_in_dir(dir_path)
        if not dir_images:
            return {"error": "empty"}

        random_path = random.choice(dir_images)
        rel_path = os.path.relpath(random_path, IMG_ROOT_DIR)
        return {
            "name": os.path.basename(random_path),
            "url": f"/image?path={quote(rel_path)}",
            "path": rel_path
        }


def get_random_image_in_all_categories() -> Optional[dict]:
    """
    全局随机:从数据库读取所有图片，随机返回一张
    """
    try:
        from ..core.database import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 从所有启用状态的图片中随机选择一张
            cursor.execute('''
                SELECT filename, file_path FROM images 
                WHERE status = 'enabled'
                ORDER BY RANDOM() LIMIT 1
            ''')
            
            image = cursor.fetchone()
            
            if not image:
                return None
            
            # 返回与原格式相同的结果
            return {
                "name": image['filename'],
                "url": f"/image?path={quote(image['file_path'])}",
                "path": image['file_path']
            }
    except Exception as e:
        print(f"[ERROR] 从数据库获取全局随机图片失败: {str(e)}")
        # 发生错误时回退到文件系统扫描
        all_img_paths = []

        # 收集根目录图片
        if os.path.isdir(IMG_ROOT_DIR):
            for file_name in safe_listdir(IMG_ROOT_DIR):
                file_path = os.path.join(IMG_ROOT_DIR, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    all_img_paths.append(file_path)

        # 收集子分类图片
        if os.path.isdir(IMG_ROOT_DIR):
            for dir_name in safe_listdir(IMG_ROOT_DIR):
                dir_path = os.path.join(IMG_ROOT_DIR, dir_name)
                if os.path.isdir(dir_path):
                    all_img_paths.extend(get_all_images_in_dir(dir_path))

        if not all_img_paths:
            return None

        random_path = random.choice(all_img_paths)
        rel_path = os.path.relpath(random_path, IMG_ROOT_DIR)
        return {
            "name": os.path.basename(random_path),
            "url": f"/image?path={quote(rel_path)}",
            "path": rel_path
        }


def get_all_images(page: int = 1, category: str = '') -> dict:
    """
    获取所有图片列表(分页) - 从数据库读取
    支持分类过滤
    """
    all_images = []

    try:
        from ..core.database import get_db_connection
        from urllib.parse import quote

        with get_db_connection() as conn:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # 构建查询语句，支持分类过滤
            if category:
                cursor.execute('''
                    SELECT
                        i.id,
                        i.filename,
                        i.file_path,
                        i.file_size,
                        i.width,
                        i.height,
                        i.created_at,
                        c.name as category_name
                    FROM images i
                    LEFT JOIN categories c ON i.category_id = c.id
                    WHERE i.status = 'enabled' AND c.name = %s
                    ORDER BY i.created_at DESC
                ''', (category,))
            else:
                # 查询启用状态的图片，按创建时间倒序排序
                cursor.execute('''
                    SELECT
                        i.id,
                        i.filename,
                        i.file_path,
                        i.file_size,
                        i.width,
                        i.height,
                        i.created_at,
                        c.name as category_name
                    FROM images i
                    LEFT JOIN categories c ON i.category_id = c.id
                    WHERE i.status = 'enabled'
                    ORDER BY i.created_at DESC
                ''')

            images_data = cursor.fetchall()

            # 构建图片列表
            for img in images_data:
                file_path = os.path.join(IMG_ROOT_DIR, img['file_path'])
                file_size = img['file_size'] or 0

                # 计算文件大小显示
                if file_size < 1024:
                    size_str = f"{file_size}B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size // 1024}KB"
                else:
                    size_str = f"{file_size // (1024 * 1024)}MB"

                # 计算分辨率
                width = img['width'] or 0
                height = img['height'] or 0
                resolution = f"{width}×{height}"

                # 格式化创建时间
                modified_time = img['created_at'].strftime('%Y-%m-%d') if img['created_at'] else ""

                all_images.append({
                    "id": img['id'],
                    "name": img['filename'],
                    "category": img['category_name'] or "未分类",
                    "path": img['file_path'],
                    "url": f"/image?path={quote(img['file_path'])}",
                    "size_bytes": file_size,
                    "resolution": resolution,
                    "modified_time": modified_time
                })

    except Exception as e:
        print(f"[ERROR] 从数据库读取图片列表失败: {str(e)}")
        # 如果数据库读取失败，回退到文件系统扫描
        all_images = []
        categories_data = get_image_categories()

        for category_name, images in categories_data.items():
            for img in images:
                file_path = os.path.join(IMG_ROOT_DIR, img["path"])
                file_size = 0
                file_resolution = "0x0"
                modified_time = ""

                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d')

                    try:
                        from PIL import Image
                        with Image.open(file_path) as img_obj:
                            file_resolution = f"{img_obj.width}×{img_obj.height}"
                    except:
                        pass

                # 计算文件大小显示
                if file_size < 1024:
                    size_str = f"{file_size}B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size // 1024}KB"
                else:
                    size_str = f"{file_size // (1024 * 1024)}MB"

                all_images.append({
                    "id": len(all_images) + 1,
                    "name": img["name"],
                    "category": category_name,
                    "path": img["path"],
                    "url": img["url"],
                    "size_bytes": file_size,
                    "resolution": file_resolution,
                    "modified_time": modified_time
                })

    # 分页处理
    total_images = len(all_images)
    total_pages = (total_images + HOME_PAGE_SIZE - 1) // HOME_PAGE_SIZE if total_images > 0 else 1
    page = max(1, min(page, total_pages))

    start = (page - 1) * HOME_PAGE_SIZE
    end = start + HOME_PAGE_SIZE

    return {
        "images": all_images[start:end],
        "current_page": page,
        "total_pages": total_pages,
        "total_images": total_images,
        "page_size": HOME_PAGE_SIZE
    }
