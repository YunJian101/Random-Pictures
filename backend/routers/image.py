#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片路由模块
处理所有图片相关的API请求
"""

import os
from typing import Optional
from fastapi import Query, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote

from ..config import IMG_ROOT_DIR, ICP_BEIAN_CODE, ICP_BEIAN_URL
from ..image_service import (
    get_paginated_categories,
    get_paginated_category_images,
    get_random_image_in_category,
    get_random_image_in_all_categories
)
from ..utils import validate_safe_path, validate_image_file, get_mime_type


async def api_categories(page: int = Query(1, ge=1, le=1000, description="页码")):
    """分类列表API"""
    result = get_paginated_categories(page)
    return JSONResponse(content=result)


async def api_category_images(
    name: str = Query(..., description="分类名称"),
    page: int = Query(1, ge=1, le=1000, description="页码")
):
    """分类图片API"""
    result = get_paginated_category_images(unquote(name), page)
    return JSONResponse(content=result)


async def handle_random_image(
    request: Request,
    type: Optional[str] = Query(None, description="分类类型")
):
    """处理随机图片请求 - 直接返回图片内容"""
    try:
        if type:
            decoded_category = unquote(type)
            result = get_random_image_in_category(decoded_category)
        else:
            result = get_random_image_in_all_categories()

        if result is None:
            if type:
                raise HTTPException(status_code=404, detail="分类不存在")
            raise HTTPException(status_code=404, detail="没有可用的图片")

        if isinstance(result, dict) and result.get('error') == 'empty':
            raise HTTPException(status_code=404, detail="该分类下没有图片")

        image_path = result.get('path')
        if not image_path:
            raise HTTPException(status_code=404, detail="无法获取图片路径")

        full_path = os.path.join(IMG_ROOT_DIR, image_path)

        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="图片文件不存在")

        if not validate_image_file(full_path):
            raise HTTPException(status_code=404, detail="不是有效的图片文件")

        content_type = get_mime_type(full_path)

        return FileResponse(
            full_path,
            media_type=content_type,
            headers={
                'Cache-Control': 'no-cache, max-age=0'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 处理随机图片请求时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail="处理随机图片请求时发生错误")


async def handle_image(
    request: Request,
    path: str = Query(..., description="图片路径")
):
    """处理图片直链请求"""
    if not validate_safe_path(IMG_ROOT_DIR, path):
        raise HTTPException(status_code=422, detail="非法图片路径")

    full_path = os.path.join(IMG_ROOT_DIR, unquote(path))

    if not os.path.exists(full_path):
        # 检查分类是否存在
        path_parts = path.split('/')
        if len(path_parts) > 1:
            category = path_parts[0]
            category_path = os.path.join(IMG_ROOT_DIR, category)
            if not os.path.isdir(category_path):
                raise HTTPException(status_code=404, detail="分类不存在")

        raise HTTPException(status_code=404, detail="图片不存在")

    if not validate_image_file(full_path):
        raise HTTPException(status_code=404, detail="图片不存在")

    content_type = get_mime_type(full_path)

    return FileResponse(
        full_path,
        media_type=content_type,
        headers={
            'Cache-Control': 'public, max-age=604800'
        }
    )


async def api_config():
    """配置信息API"""
    from .. import __version__
    return JSONResponse(content={
        "version": __version__,
        "icp_beian_code": ICP_BEIAN_CODE if ICP_BEIAN_CODE else "",
        "icp_beian_url": ICP_BEIAN_URL if ICP_BEIAN_URL else "https://beian.miit.gov.cn",
        "code": 200,
        "msg": "success"
    })
