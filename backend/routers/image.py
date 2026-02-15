#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片路由模块
处理所有图片相关的API请求
"""

import os
from typing import Optional
from fastapi import Query, Request, HTTPException, Form, Body, Depends
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote
from psycopg2.extras import RealDictCursor
from ..api.dependencies import get_current_admin
from ..handlers.error_handlers import create_error_response, get_base_url

from ..core.config import IMG_ROOT_DIR, ICP_BEIAN_CODE, ICP_BEIAN_URL
from ..core.database import get_db_connection
from ..services.image_service import (
    get_paginated_categories,
    get_paginated_category_images,
    get_random_image_in_category,
    get_random_image_in_all_categories
)
from ..utils.utils import validate_safe_path, validate_image_file, get_mime_type, get_client_ip


async def api_categories(page: int = Query(1, ge=1, le=1000, description="页码")):
    """分类列表API - 从数据库读取"""
    from ..core.database import get_db_connection
    from ..core.config import HOME_PAGE_SIZE

    with get_db_connection() as conn:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 查询启用状态的分类，按创建时间排序
        cursor.execute('''
            SELECT id, name, description, status, created_at, updated_at
            FROM categories
            WHERE status = 'enabled'
            ORDER BY created_at DESC
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

        # 构建包含ID和图片数量的分类列表
        category_list = []
        for category in paginated_categories:
            # 从数据库查询该分类的图片数量
            cursor.execute('''
                SELECT COUNT(*) as count FROM images
                WHERE category_id = %s AND status = 'enabled'
            ''', (category['id'],))
            result = cursor.fetchone()
            image_count = result['count'] if result else 0

            category_list.append({
                'id': category['id'],
                'name': category['name'],
                'description': category['description'],
                'status': category['status'],
                'image_count': image_count,
                'created_at': category['created_at'].isoformat(),
                'updated_at': category['updated_at'].isoformat()
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
                # 使用通用函数生成错误响应
                base_url = get_base_url(request)
                response = create_error_response(
                    request, 
                    "404分类不存在", 
                    404, 
                    {"category": decoded_category, "BASE_URL": base_url}, 
                    "分类不存在"
                )
                return response
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

        # 更新访问统计信息
        try:
            rel_path = os.path.relpath(full_path, IMG_ROOT_DIR)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE images
                    SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP
                    WHERE file_path = %s
                ''', (rel_path,))
                print(f"[INFO] 图片访问统计已更新: {rel_path}")
        except Exception as db_error:
            print(f"[ERROR] 更新访问统计失败: {str(db_error)}")

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
                # 使用通用函数生成错误响应
                base_url = get_base_url(request)
                response = create_error_response(
                    request, 
                    "404分类不存在", 
                    404, 
                    {"category": category, "BASE_URL": base_url}, 
                    "分类不存在"
                )
                return response
        
        # 使用通用函数生成错误响应
        # 从路径中提取图片名称和分类
        image_name = os.path.basename(path)
        path_parts = path.split('/')
        category = path_parts[0] if len(path_parts) > 1 else ""
        base_url = get_base_url(request)
        response = create_error_response(
            request, 
            "404图片不存在", 
            404, 
            {"image_name": image_name, "category": category, "image_path": path, "BASE_URL": base_url}, 
            "图片不存在"
        )
        return response

    if not validate_image_file(full_path):
        # 使用通用函数生成错误响应
        # 从路径中提取图片名称和分类
        image_name = os.path.basename(path)
        path_parts = path.split('/')
        category = path_parts[0] if len(path_parts) > 1 else ""
        base_url = get_base_url(request)
        response = create_error_response(
            request, 
            "404图片不存在", 
            404, 
            {"image_name": image_name, "category": category, "image_path": path, "BASE_URL": base_url}, 
            "图片不存在"
        )
        return response

    # 更新访问统计信息
    try:
        rel_path = os.path.relpath(full_path, IMG_ROOT_DIR)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE images
                SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP
                WHERE file_path = %s
            ''', (rel_path,))
            print(f"[INFO] 图片访问统计已更新: {rel_path}")
    except Exception as db_error:
        print(f"[ERROR] 更新访问统计失败: {str(db_error)}")

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
    return JSONResponse(content={
        "icp_beian_code": ICP_BEIAN_CODE if ICP_BEIAN_CODE else "",
        "icp_beian_url": ICP_BEIAN_URL if ICP_BEIAN_URL else "https://beian.miit.gov.cn",
        "code": 200,
        "msg": "success"
    })


async def api_all_images(page: int = Query(1, ge=1, le=1000, description="页码"), category: str = Query("", description="分类名称"), current_user: dict = Depends(get_current_admin)):
    """获取所有图片列表API - 仅管理员可使用"""
    from ..services.image_service import get_all_images
    result = get_all_images(page, category)
    return JSONResponse(content=result)


async def api_image_detail(image_id: int):
    """获取单个图片详细信息API"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
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
                WHERE i.id = %s
            ''', (image_id,))
            image = cursor.fetchone()
            
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
        # 获取用户信息和IP地址
        username = current_user.get('username', 'unknown')
        x_forwarded_for = request.headers.get('X-Forwarded-For', '')
        remote_addr = request.client.host if request.client else ''
        client_ip = get_client_ip(x_forwarded_for, remote_addr)
        user_agent = request.headers.get('User-Agent', 'unknown')
        
        # 输出操作开始日志
        print(f"[INFO] 开始更新图片信息 - 操作: 更新图片 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
        print(f"[INFO] 用户代理: {user_agent}")
        print(f"[INFO] 更新内容: 文件名='{filename}', 分类ID={category_id}")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 检查图片是否存在
            cursor.execute('''
                SELECT i.id, i.filename, i.file_path, i.category_id, c.name as category_name
                FROM images i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.id = %s
            ''', (image_id,))
            image = cursor.fetchone()
            if not image:
                print(f"[ERROR] 更新图片信息失败 - 图片不存在 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
                return JSONResponse(
                    content={"code": 404, "msg": "图片不存在"},
                    status_code=404
                )
            
            # 处理文件名更新
            original_filename = image[1]
            original_file_path = image[2]
            original_category_id = image[3]
            original_category_name = image[4]
            
            # 校验文件名，避免路径攻击
            import re
            
            # 检测路径穿透攻击
            path_traversal_patterns = ["../", "..\\", "/", "\\"]
            has_path_traversal = any(pattern in filename for pattern in path_traversal_patterns)
            
            if has_path_traversal:
                print(f"[ERROR] 检测到路径穿透攻击尝试 | 用户: {username} | IP: {client_ip} | 文件名: {filename}")
                print(f"[ERROR] 攻击详情: 文件名包含路径穿透模式")
                # 记录详细的错误日志
                import traceback
                print(f"[ERROR] 路径穿透攻击检测堆栈: {traceback.format_exc()}")
            
            # 移除文件名中的路径分隔符和其他危险字符
            # 只允许字母、数字、下划线、中文字符和常见标点
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
                cursor.execute('SELECT name FROM categories WHERE id = %s', (category_id,))
                new_category = cursor.fetchone()
                if not new_category:
                    print(f"[ERROR] 更新图片信息失败 - 指定的分类不存在 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id} | 分类ID: {category_id}")
                    return JSONResponse(
                        content={"code": 400, "msg": "指定的分类不存在"},
                        status_code=400
                    )
                new_category_name = new_category[0]
                print(f"[INFO] 分类变更 - 从 '{original_category_name}' 变更为 '{new_category_name}'")
            
            # 构建新的文件路径
            from ..core.config import IMG_ROOT_DIR
            
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
                # 构建完整的文件路径
                original_full_path = os.path.join(IMG_ROOT_DIR, original_file_path)
                new_full_path = os.path.join(IMG_ROOT_DIR, new_file_path)
                
                print(f"[INFO] 准备移动文件 | 原路径: {original_full_path} | 新路径: {new_full_path}")
                
                # 确保目标文件夹存在
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                print(f"[INFO] 目标文件夹已确保存在: {os.path.dirname(new_full_path)}")
                
                # 移动文件
                if os.path.exists(original_full_path):
                    os.rename(original_full_path, new_full_path)
                    print(f"[INFO] 图片文件已移动: {original_full_path} -> {new_full_path}")
                else:
                    print(f"[WARNING] 原始文件不存在: {original_full_path}")
            
            # 更新图片信息
            print(f"[INFO] 开始更新数据库 | 新文件名: {new_filename} | 新分类ID: {category_id} | 新文件路径: {new_file_path}")
            cursor.execute('''
                UPDATE images
                SET filename = %s, category_id = %s, file_path = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (new_filename, category_id, new_file_path, image_id))
            conn.commit()
            print(f"[INFO] 数据库更新成功")
            
            # 输出操作完成日志
            print(f"[INFO] 图片信息更新成功 - 操作: 更新图片 | 用户: {username} | IP: {client_ip} | 图片ID: {image_id}")
            print(f"[INFO] 更新结果: 文件名='{new_filename}', 分类ID={category_id}, 文件路径='{new_file_path}'")
            
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


async def api_delete_image(image_id: int, current_user: dict = Depends(get_current_admin)):
    """删除图片API"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 检查图片是否存在
            cursor.execute('SELECT file_path FROM images WHERE id = %s', (image_id,))
            result = cursor.fetchone()
            if not result:
                return JSONResponse(
                    content={"code": 404, "msg": "图片不存在"},
                    status_code=404
                )
            
            # 获取文件路径
            file_path = result[0]
            full_path = os.path.join(IMG_ROOT_DIR, file_path)
            
            # 删除数据库记录
            cursor.execute('DELETE FROM images WHERE id = %s', (image_id,))
            conn.commit()
            
            # 删除物理文件
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[INFO] 物理文件已删除: {full_path}")
            
            return JSONResponse(
                content={"code": 200, "msg": "图片删除成功"}
            )
            
    except Exception as e:
        print(f"[ERROR] 删除图片失败: {str(e)}")
        return JSONResponse(
            content={"code": 500, "msg": "删除图片失败"},
            status_code=500
        )
