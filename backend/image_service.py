#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片服务模块 - 核心业务逻辑
==========================
"""

import os
import random
from typing import List, Optional, Dict
from urllib.parse import quote

from .config import IMG_ROOT_DIR, HOME_PAGE_SIZE, CATEGORY_PAGE_SIZE
from .utils import safe_listdir, get_all_images_in_dir, get_directory_modify_time
from .cache import global_cache


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
    获取所有图片分类（实时检测根目录变化）
    """
    # 检查根目录是否发生变化
    root_mtime = get_directory_modify_time(IMG_ROOT_DIR)
    last_root_mtime = global_cache.get_dir_mtime("root")

    if root_mtime != last_root_mtime:
        global_cache.set_dir_mtime("root", root_mtime)
        global_cache.clear("image_cache")

    categories = {}

    # 处理根目录图片（作为"根目录"分类）
    root_images = []
    if os.path.isdir(IMG_ROOT_DIR):
        for file_name in safe_listdir(IMG_ROOT_DIR):
            file_path = os.path.join(IMG_ROOT_DIR, file_name)
            if os.path.isfile(file_path) and file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                rel_path = os.path.relpath(file_path, IMG_ROOT_DIR)
                root_images.append({
                    "name": file_name,
                    "url": f"/image?path={quote(rel_path)}",
                    "path": rel_path
                })

    if root_images:
        categories["根目录"] = root_images

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
    分页获取分类列表
    """
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
    分页获取分类下图片
    """
    all_images = []

    if category_name == "根目录":
        if os.path.isdir(IMG_ROOT_DIR):
            for file_name in safe_listdir(IMG_ROOT_DIR):
                file_path = os.path.join(IMG_ROOT_DIR, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    rel_path = os.path.relpath(file_path, IMG_ROOT_DIR)
                    all_images.append({
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
    分类随机：直接返回随机单张图片
    """
    if category_name == "根目录":
        img_paths = []
        if os.path.isdir(IMG_ROOT_DIR):
            for file_name in safe_listdir(IMG_ROOT_DIR):
                file_path = os.path.join(IMG_ROOT_DIR, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    img_paths.append(file_path)

        if not os.path.isdir(IMG_ROOT_DIR):
            return None

        if not img_paths:
            return {"error": "empty"}

        random_path = random.choice(img_paths)
        rel_path = os.path.relpath(random_path, IMG_ROOT_DIR)
        return {
            "name": os.path.basename(random_path),
            "url": f"/image?path={quote(rel_path)}",
            "path": rel_path
        }
    else:
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
    全局随机：直接返回随机单张图片
    """
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
