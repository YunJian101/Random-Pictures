#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片路由模块
处理所有图片相关的API请求
"""

import os
from typing import Optional
from fastapi import Query, Request, HTTPException, Body, Depends
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote
from ..api.dependencies import get_current_admin
from ..services.audit_service import record as audit
from ..handlers.error_handlers import create_error_response, get_base_url

from ..core.config import IMG_ROOT_DIR
from ..core.database import get_async_db_connection
from ..services.image_service import (
    get_paginated_category_images,
    get_random_image_in_category,
    get_random_image_in_all_categories,
)
from ..utils.utils import validate_safe_path, validate_image_file, get_mime_type
from ..utils.request import client_ip as resolve_client_ip


async def api_categories(page: int = Query(1, ge=1, le=1000, description="页码")):
    """分类列表API - 从数据库读取"""
    from ..core.database import get_async_db_connection
    from ..core.config import HOME_PAGE_SIZE

    async with get_async_db_connection() as conn:
        # 查询启用状态的分类，按创建时间排序
        all_categories = await conn.fetch('''
            SELECT id, name, description, status, created_at, updated_at
            FROM categories
            WHERE status = 'enabled'
            ORDER BY created_at DESC
        ''')

        # 计算分页信息
        total_categories = len(all_categories)
        total_pages = (total_categories + HOME_PAGE_SIZE - 1) // HOME_PAGE_SIZE
        page = max(1, min(page, total_pages))

        # 计算分页范围
        start = (page - 1) * HOME_PAGE_SIZE
        end = start + HOME_PAGE_SIZE
        paginated_categories = all_categories[start:end]

        # 公开接口：只暴露展示所需字段
        # id / status / 时间戳属于内部数据，仅管理端接口返回（/api/admin/categories）
        category_list = []
        for category in paginated_categories:
            # 从数据库查询该分类的图片数量
            result = await conn.fetchrow('''
                SELECT COUNT(*) as count FROM images
                WHERE category_id = $1 AND status = 'enabled'
            ''', category['id'])
            image_count = result['count'] if result else 0

            category_list.append({
                'name': category['name'],
                'description': category['description'],
                'image_count': image_count
            })

        return JSONResponse(content={
            "category_list": category_list,
            "current_page": page,
            "total_pages": total_pages,
            "total_categories": total_categories,
            "items_per_page": HOME_PAGE_SIZE
        })


async def api_category_images(
    name: str = Query(..., description="分类名称"),
    page: int = Query(1, ge=1, le=1000, description="页码")
):
    """分类图片API"""
    result = await get_paginated_category_images(unquote(name), page)
    return JSONResponse(content=result)


# ==================== 请求参数解析 ====================
ALLOWED_FORMATS = ('jpg', 'jpeg', 'png', 'gif', 'webp')


def _parse_exclude(raw: Optional[str]) -> list:
    """解析 exclude=1,2,3（排除指定图片 id），最多 100 个"""
    if not raw:
        return []
    ids = []
    for piece in str(raw).split(','):
        piece = piece.strip()
        if not piece:
            continue
        if not piece.isdigit():
            raise HTTPException(status_code=422, detail=f"exclude 参数包含非法值: {piece}")
        ids.append(int(piece))
        # 超限必须报错：静默截断会让调用方以为 100 个之后的 ID 也生效了
        if len(ids) > 100:
            raise HTTPException(status_code=422, detail="exclude 最多 100 个图片 ID")
    return ids


def _parse_formats(raw: Optional[str]) -> list:
    """解析 format=jpg,png（限定图片后缀）"""
    if not raw:
        return []
    formats = []
    for piece in str(raw).split(','):
        piece = piece.strip().lower().lstrip('.')
        if not piece:
            continue
        if piece == 'jpeg':
            piece = 'jpg'
        if piece not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=422,
                detail=f"不支持的格式: {piece}（可选 {', '.join(ALLOWED_FORMATS)}）",
            )
        if piece not in formats:
            formats.append(piece)
    return formats


async def _serve_image(
    full_path: str, rel_path: str, width: Optional[int], cache_control: str, accept: str = ''
):
    """按需返回原图或缩略图

    响应头带 Vary: Accept —— 同一个缩略图 URL 可能返回 webp 或 jpeg，
    不加这个 CDN/代理会把 webp 缓存下来发给不支持它的客户端。
    """
    from ..services.thumb_service import ensure_thumb, normalize_width, pick_format

    target_width = normalize_width(width)
    if target_width:
        fmt = pick_format(accept)
        thumb = await ensure_thumb(rel_path, target_width, fmt)
        if thumb:
            return FileResponse(
                thumb,
                media_type='image/webp' if fmt == 'webp' else 'image/jpeg',
                headers={
                    'Cache-Control': cache_control,
                    'X-Thumb-Width': str(target_width),
                    'X-Thumb-Format': fmt,
                    'Vary': 'Accept',
                },
            )
        # 缩略图失败（比如 Pillow 处理不了）就退回原图，不让请求失败
        print(f'[WARN] 缩略图生成失败，回退原图: {rel_path}')

    return FileResponse(
        full_path,
        media_type=get_mime_type(full_path),
        headers={'Cache-Control': cache_control},
    )


# ==================== 图片路由 ====================
async def handle_random_image(
    request: Request,
    type: Optional[str] = Query(None, description="分类类型"),
    exclude: Optional[str] = Query(None, description="排除的图片 ID，逗号分隔"),
    format: Optional[str] = Query(None, description="限定格式，逗号分隔：jpg/png/gif/webp"),
    w: Optional[int] = Query(None, ge=1, le=4000, description="返回宽度（自动生成缩略图）"),
):
    """处理随机图片请求 - 直接返回图片内容"""
    try:
        exclude_ids = _parse_exclude(exclude)
        formats = _parse_formats(format)

        if type:
            decoded_category = unquote(type)
            result = await get_random_image_in_category(decoded_category, exclude_ids, formats)
        else:
            result = await get_random_image_in_all_categories(exclude_ids, formats)

        if result is None:
            if type:
                base_url = get_base_url(request)
                response = await create_error_response(
                    request,
                    "404分类不存在",
                    404,
                    {"category": unquote(type), "BASE_URL": base_url},
                    "分类不存在"
                )
                return response
            raise HTTPException(status_code=404, detail="没有可用的图片")

        if isinstance(result, dict) and result.get('error') == 'empty':
            raise HTTPException(status_code=404, detail="该分类下没有符合条件可用的图片")

        image_path = result.get('path')
        if not image_path:
            raise HTTPException(status_code=404, detail="无法获取图片路径")

        full_path = os.path.join(IMG_ROOT_DIR, image_path)

        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="图片文件不存在")

        if not await validate_image_file(full_path):
            raise HTTPException(status_code=404, detail="不是有效的图片文件")

        # 更新访问统计信息
        try:
            rel_path = os.path.relpath(full_path, IMG_ROOT_DIR)
            async with get_async_db_connection() as conn:
                await conn.execute('''
                    UPDATE images
                    SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP
                    WHERE file_path = $1
                ''', rel_path)
        except Exception as db_error:
            print(f"[ERROR] 更新访问统计失败: {str(db_error)}")

        # 随机接口必须禁用缓存，否则拿到的永远是同一张
        return await _serve_image(
            full_path, image_path, w, 'no-cache, max-age=0',
            request.headers.get('accept', ''),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 处理随机图片请求时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail="处理随机图片请求时发生错误")


async def handle_image(
    request: Request,
    path: str = Query(..., description="图片路径"),
    w: Optional[int] = Query(None, ge=1, le=4000, description="返回宽度（自动生成缩略图）"),
):
    """处理图片直链请求"""
    if not validate_safe_path(IMG_ROOT_DIR, path):
        raise HTTPException(status_code=422, detail="非法图片路径")

    rel_path = unquote(path)
    full_path = os.path.join(IMG_ROOT_DIR, rel_path)

    if not os.path.exists(full_path):
        # 检查分类是否存在
        path_parts = path.split('/')
        if len(path_parts) > 1:
            category = path_parts[0]
            category_path = os.path.join(IMG_ROOT_DIR, category)
            if not os.path.isdir(category_path):
                base_url = get_base_url(request)
                response = await create_error_response(
                    request,
                    "404分类不存在",
                    404,
                    {"category": category, "BASE_URL": base_url},
                    "分类不存在"
                )
                return response

        image_name = os.path.basename(path)
        category = path_parts[0] if len(path_parts) > 1 else ""
        base_url = get_base_url(request)
        response = await create_error_response(
            request,
            "404图片不存在",
            404,
            {"image_name": image_name, "category": category, "image_path": path, "BASE_URL": base_url},
            "图片不存在"
        )
        return response

    if not await validate_image_file(full_path):
        image_name = os.path.basename(path)
        path_parts = path.split('/')
        category = path_parts[0] if len(path_parts) > 1 else ""
        base_url = get_base_url(request)
        response = await create_error_response(
            request,
            "404图片不存在",
            404,
            {"image_name": image_name, "category": category, "image_path": path, "BASE_URL": base_url},
            "图片不存在"
        )
        return response

    # 更新访问统计信息
    try:
        async with get_async_db_connection() as conn:
            await conn.execute('''
                UPDATE images
                SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP
                WHERE file_path = $1
            ''', rel_path)
    except Exception as db_error:
        print(f"[ERROR] 更新访问统计失败: {str(db_error)}")

    # 直链内容稳定，可以长缓存
    return await _serve_image(
        full_path, rel_path, w, 'public, max-age=604800',
        request.headers.get('accept', ''),
    )


async def handle_thumb(request: Request, path: str = Query(..., description="图片路径"),
                       w: int = Query(320, ge=1, le=4000, description="缩略图宽度")):
    """缩略图接口：列表/卡片用，避免直接拉原图"""
    if not validate_safe_path(IMG_ROOT_DIR, path):
        raise HTTPException(status_code=422, detail="非法图片路径")

    rel_path = unquote(path)
    full_path = os.path.join(IMG_ROOT_DIR, rel_path)

    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="图片不存在")

    return await _serve_image(
        full_path, rel_path, w, 'public, max-age=2592000',
        request.headers.get('accept', ''),
    )


async def api_all_images(
    page: int = Query(1, ge=1, le=1000, description="页码"),
    category: str = Query("", description="分类名称"),
    q: str = Query("", max_length=100, description="文件名关键字"),
    sort: str = Query("created_desc", description="排序：created_desc/created_asc/size_desc/size_asc/views_desc/name_asc"),
    current_user: dict = Depends(get_current_admin),
):
    """获取所有图片列表API - 仅管理员可使用"""
    from ..services.image_service import get_all_images
    result = await get_all_images(page, category, q, sort)
    return JSONResponse(content=result)


async def api_image_detail(image_id: int, current_user: dict = Depends(get_current_admin)):
    """获取单个图片详细信息API - 仅管理员（含 md5 / 上传 IP 等内部数据）"""
    try:
        async with get_async_db_connection() as conn:
            image = await conn.fetchrow('''
                SELECT 
                    i.id, 
                    i.filename, 
                    i.file_path, 
                    i.category_id, 
                    c.name as category_name,
                    i.file_size, 
                    i.width, 
                    i.height, 
                    i.format, 
                    i.md5, 
                    i.uploader, 
                    i.upload_ip, 
                    i.view_count, 
                    i.last_viewed_at, 
                    i.created_at as upload_time
                FROM images i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.id = $1
            ''', image_id)
            
            if not image:
                return JSONResponse(
                    content={"code": 404, "msg": "图片不存在"},
                    status_code=404
                )
            
            # 格式化文件大小
            def format_file_size(size_bytes):
                if size_bytes < 1024:
                    return f"{size_bytes}B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f}KB"
                else:
                    return f"{size_bytes / (1024 * 1024):.1f}MB"
            
            # 构建响应数据
            response_data = {
                "code": 200,
                "msg": "success",
                "data": {
                    "id": image['id'],
                    "filename": image['filename'],
                    "file_path": image['file_path'],
                    "category_id": image['category_id'],
                    "category_name": image['category_name'] or "未分类",
                    "file_size": image['file_size'],
                    "width": image['width'],
                    "height": image['height'],
                    "format": image['format'] or "未知",
                    "md5": image['md5'] or "未知",
                    "uploader": image['uploader'] or "未知",
                    "upload_ip": image['upload_ip'] or "未知",
                    "view_count": image['view_count'],
                    "last_viewed_at": image['last_viewed_at'].isoformat() if image['last_viewed_at'] else "未知",
                    "upload_time": image['upload_time'].isoformat() if image['upload_time'] else "未知"
                }
            }
            
            return JSONResponse(content=response_data)
            
    except Exception as e:
        print(f"[ERROR] 获取图片详情失败: {str(e)}")
        return JSONResponse(
            content={"code": 500, "msg": "获取图片详情失败"},
            status_code=500
        )


async def api_update_image(request: Request, image_id: int, filename: str = Body(...), category_id: int = Body(...), current_user: dict = Depends(get_current_admin)):
    """更新图片信息API"""
    try:
        # 获取用户信息和IP地址（与登录、审核日志同一套规则）
        username = current_user.get('username', 'unknown')
        client_ip = await resolve_client_ip(request)
        user_agent = request.headers.get('User-Agent', 'unknown')
        
        # 输出操作开始日志
        print(f"[INFO] 开始更新图片信息 - 操作: 更新图片 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
        print(f"[INFO] 用户代理: {user_agent}")
        print(f"[INFO] 更新内容: 文件名='{filename}', 分类ID={category_id}")
        
        async with get_async_db_connection() as conn:
            # 检查图片是否存在
            image = await conn.fetchrow('''
                SELECT i.id, i.filename, i.file_path, i.category_id, c.name as category_name
                FROM images i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.id = $1
            ''', image_id)
            if not image:
                print(f"[ERROR] 更新图片信息失败 - 图片不存在 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
                return JSONResponse(
                    content={"code": 404, "msg": "图片不存在"},
                    status_code=404
                )
            
            # 处理文件名更新
            original_filename = image['filename']
            original_file_path = image['file_path']
            original_category_id = image['category_id']
            original_category_name = image['category_name']
            
            # 校验文件名，避免路径攻击
            from ..utils.utils import validate_local_path
            
            # 检测路径穿透攻击
            is_valid, error_msg = validate_local_path(filename)
            has_path_traversal = not is_valid
            
            if has_path_traversal:
                print(f"[ERROR] 检测到路径穿透攻击尝试 | 用户: {username} | IP: {client_ip} | 文件名: {filename}")
                print(f"[ERROR] 攻击详情: {error_msg}")
                # 记录详细的错误日志
                import traceback
                print(f"[ERROR] 路径穿透攻击检测堆栈: {traceback.format_exc()}")
            
            # 移除文件名中的路径分隔符和其他危险字符
            # 只允许字母、数字、下划线、中文字符和常见标点
            import re
            safe_filename = re.sub(r'[\\/"*?<>|]', '_', filename)
            
            # 提取原始文件名的后缀
            last_dot_index = original_filename.rfind('.')
            if last_dot_index > 0:
                file_extension = original_filename[last_dot_index:]
                # 提取新文件名的前缀（不含后缀）
                new_filename_prefix = safe_filename.rsplit('.', 1)[0] if '.' in safe_filename else safe_filename
                # 构建新文件名（保持原始后缀）
                new_filename = new_filename_prefix + file_extension
            else:
                # 如果原始文件名没有后缀，直接使用安全的文件名
                new_filename = safe_filename
            
            # 确保文件名不为空
            if not new_filename or new_filename == '.':
                print(f"[ERROR] 更新图片信息失败 - 文件名不能为空 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
                return JSONResponse(
                    content={"code": 400, "msg": "文件名不能为空"},
                    status_code=400
                )
            
            # 检查分类是否有变化
            category_changed = original_category_id != category_id
            
            # 如果分类有变化，获取新分类的名称
            new_category_name = original_category_name
            if category_changed:
                new_category = await conn.fetchrow('SELECT name FROM categories WHERE id = $1', category_id)
                if not new_category:
                    print(f"[ERROR] 更新图片信息失败 - 指定的分类不存在 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id} | 分类ID: {category_id}")
                    return JSONResponse(
                        content={"code": 400, "msg": "指定的分类不存在"},
                        status_code=400
                    )
                new_category_name = new_category['name']
                print(f"[INFO] 分类变更 - 从 '{original_category_name}' 变更为 '{new_category_name}'")
            
            # 构建新的文件路径
            from ..core.config import IMG_ROOT_DIR
            from ..utils.async_io import (
                async_exists,
                async_makedirs,
                async_rename,
                async_unique_filename,
            )
            
            # 提取原始文件名（不含路径）
            original_basename = os.path.basename(original_file_path)
            
            # 构建新的文件路径
            if category_changed:
                # 如果分类有变化，使用新分类的文件夹
                new_file_path = os.path.join(new_category_name, new_filename)
            else:
                # 如果分类没有变化，只更新文件名
                new_file_path = os.path.join(os.path.dirname(original_file_path), new_filename)
            
            # 如果文件路径有变化，移动文件
            if original_file_path != new_file_path:
                target_dir_rel = os.path.dirname(new_file_path)
                target_dir_abs = os.path.join(IMG_ROOT_DIR, target_dir_rel)

                # 重名必须顺延：os.rename 会静默覆盖同名文件，把另一张图的内容冲掉，
                # 之后两条记录还都指向同一个文件（实测会丢图）
                new_filename = await async_unique_filename(
                    target_dir_abs,
                    new_filename,
                    is_taken=lambda name: conn.fetchval(
                        'SELECT id FROM images WHERE file_path = $1 AND id <> $2',
                        os.path.join(target_dir_rel, name),
                        image_id,
                    ),
                )
                new_file_path = os.path.join(target_dir_rel, new_filename)

                # 构建完整的文件路径
                original_full_path = os.path.join(IMG_ROOT_DIR, original_file_path)
                new_full_path = os.path.join(IMG_ROOT_DIR, new_file_path)
                
                print(f"[INFO] 准备移动文件 | 原路径: {original_full_path} | 新路径: {new_full_path}")
                
                # 确保目标文件夹存在
                await async_makedirs(os.path.dirname(new_full_path), exist_ok=True)
                print(f"[INFO] 目标文件夹已确保存在: {os.path.dirname(new_full_path)}")
                
                # 源文件必须真的在：不在就不能假装成功，否则数据库会指向一个不存在的文件
                if not await async_exists(original_full_path):
                    print(f"[ERROR] 原始文件不存在，拒绝改名/移动: {original_full_path}")
                    return JSONResponse(
                        content={"code": 400, "msg": "原文件不存在（可能已被删除或移动），请重新上传或删除该图片记录"},
                        status_code=400
                    )

                await async_rename(original_full_path, new_full_path)
                print(f"[INFO] 图片文件已移动: {original_full_path} -> {new_full_path}")
            
            # 更新图片信息
            print(f"[INFO] 开始更新数据库 | 新文件名: {new_filename} | 新分类ID: {category_id} | 新文件路径: {new_file_path}")
            await conn.execute('''
                UPDATE images
                SET filename = $1, category_id = $2, file_path = $3, updated_at = CURRENT_TIMESTAMP
                WHERE id = $4
            ''', new_filename, category_id, new_file_path, image_id)
            print(f"[INFO] 数据库更新成功")
            
            # 输出操作完成日志
            print(f"[INFO] 图片信息更新成功 - 操作: 更新图片 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
            print(f"[INFO] 更新结果: 文件名='{new_filename}', 分类ID={category_id}, 文件路径='{new_file_path}'")

            await audit(request, 'image.update', current_user,
                        target_type='image', target_id=image_id,
                        detail=f"修改图片 #{image_id} 为「{new_filename}」，分类 #{category_id}")
            
            return JSONResponse(
                content={"code": 200, "msg": "图片信息更新成功"}
            )
    except Exception as e:
        # 输出详细的错误日志
        print(f"[ERROR] 更新图片信息失败 - 操作: 更新图片 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
        print(f"[ERROR] 错误信息: {str(e)}")
        import traceback
        print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
        return JSONResponse(
            content={"code": 500, "msg": "更新图片信息失败"},
            status_code=500
        )


async def api_delete_image(image_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """删除图片API"""
    try:
        async with get_async_db_connection() as conn:
            # 检查图片是否存在
            result = await conn.fetchrow('SELECT file_path FROM images WHERE id = $1', image_id)
            if not result:
                return JSONResponse(
                    content={"code": 404, "msg": "图片不存在"},
                    status_code=404
                )
            
            # 获取文件路径
            file_path = result['file_path']
            full_path = os.path.join(IMG_ROOT_DIR, file_path)
            
            # 删除数据库记录
            await conn.execute('DELETE FROM images WHERE id = $1', image_id)
            
            # 删除物理文件
            from ..utils.async_io import async_exists, async_remove
            if await async_exists(full_path):
                await async_remove(full_path)
                print(f"[INFO] 物理文件已删除: {full_path}")

            await audit(request, 'image.delete', current_user,
                        target_type='image', target_id=image_id,
                        detail=f"删除图片 #{image_id}（{file_path}）")

            return JSONResponse(
                content={"code": 200, "msg": "图片删除成功"}
            )
            
    except Exception as e:
        print(f"[ERROR] 删除图片失败: {str(e)}")
        return JSONResponse(
            content={"code": 500, "msg": "删除图片失败"},
            status_code=500
        )
