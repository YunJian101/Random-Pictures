#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · categories
=================

分类管理：增删改与全量列表（含图片计数）
"""

from fastapi import (
    Depends,
    Request,
)
from fastapi.responses import JSONResponse
from ...api.dependencies import get_current_admin
from ...services.audit_service import record as audit

async def api_admin_create_category(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员创建分类API"""
    from ...core.database import get_async_db_connection
    
    try:
        data = await request.json()
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return JSONResponse(content={
                'code': 400,
                'msg': '分类名称不能为空'
            }, status_code=400)
        
        async with get_async_db_connection() as conn:
            # 检查分类名称是否已存在
            existing = await conn.fetchrow('SELECT id FROM categories WHERE name = $1', name)
            if existing:
                return JSONResponse(content={
                    'code': 400,
                    'msg': '分类名称已存在'
                }, status_code=400)
            
            # 创建分类
            category = await conn.fetchrow('''
                INSERT INTO categories (name, description) 
                VALUES ($1, $2) 
                RETURNING id, name, description, status, created_at, updated_at
            ''', name, description)

            await audit(request, 'category.create', current_user,
                        target_type='category', target_id=category['id'],
                        detail=f"新建分类「{name}」")
            
            return JSONResponse(content={
                'code': 200,
                'msg': '分类创建成功',
                'data': {
                    'id': category['id'],
                    'name': category['name'],
                    'description': category['description'],
                    'status': category['status'],
                    'created_at': category['created_at'].isoformat(),
                    'updated_at': category['updated_at'].isoformat()
                }
            })
    except Exception as e:
        print(f"[ERROR] 创建分类时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '创建分类时发生错误'
        }, status_code=500)


async def api_admin_update_category(category_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员更新分类API"""
    from ...core.database import get_async_db_connection
    
    try:
        data = await request.json()
        name = data.get('name')
        description = data.get('description')
        status = data.get('status')
        
        async with get_async_db_connection() as conn:
            # 检查分类是否存在
            existing = await conn.fetchrow('SELECT id FROM categories WHERE id = $1', category_id)
            if not existing:
                return JSONResponse(content={
                    'code': 404,
                    'msg': '分类不存在'
                }, status_code=404)
            
            # 检查分类名称是否已被其他分类使用
            if name:
                existing_name = await conn.fetchrow('SELECT id FROM categories WHERE name = $1 AND id != $2', name, category_id)
                if existing_name:
                    return JSONResponse(content={
                        'code': 400,
                        'msg': '分类名称已存在'
                    }, status_code=400)
            
            # 构建更新语句
            update_fields = []
            update_values = []
            param_index = 1
            
            if name is not None:
                update_fields.append(f'name = ${param_index}')
                update_values.append(name)
                param_index += 1
            if description is not None:
                update_fields.append(f'description = ${param_index}')
                update_values.append(description)
                param_index += 1
            if status is not None:
                update_fields.append(f'status = ${param_index}')
                update_values.append(status)
                param_index += 1
            
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(category_id)
            
            # 执行更新
            category = await conn.fetchrow(f'''
                UPDATE categories 
                SET {', '.join(update_fields)} 
                WHERE id = ${param_index} 
                RETURNING id, name, description, status, created_at, updated_at
            ''', *update_values)

            await audit(request, 'category.update', current_user,
                        target_type='category', target_id=category['id'],
                        detail=f"修改分类「{category['name']}」")
            
            return JSONResponse(content={
                'code': 200,
                'msg': '分类更新成功',
                'data': {
                    'id': category['id'],
                    'name': category['name'],
                    'description': category['description'],
                    'status': category['status'],
                    'created_at': category['created_at'].isoformat(),
                    'updated_at': category['updated_at'].isoformat()
                }
            })
    except Exception as e:
        print(f"[ERROR] 更新分类时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '更新分类时发生错误'
        }, status_code=500)


async def api_admin_delete_category(category_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员删除分类API"""
    from ...core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            # 检查分类是否存在
            existing = await conn.fetchrow('SELECT id FROM categories WHERE id = $1', category_id)
            if not existing:
                return JSONResponse(content={
                    'code': 404,
                    'msg': '分类不存在'
                }, status_code=404)

            # 查询该分类下的图片数量
            image_count = await conn.fetchval('SELECT COUNT(*) FROM images WHERE category_id = $1', category_id)

            # 更新该分类下的图片，将 category_id 设为 NULL
            if image_count > 0:
                await conn.execute('UPDATE images SET category_id = NULL WHERE category_id = $1', category_id)
                print(f"[INFO] 已将分类 {category_id} 下的 {image_count} 张图片移至未分类状态")

            # 删除分类
            await conn.execute('DELETE FROM categories WHERE id = $1', category_id)

            # 记录到审核日志（此时删除已提交）
            await audit(request, 'category.delete', current_user,
                        target_type='category', target_id=category_id,
                        detail=f"删除分类 #{category_id}，{image_count} 张图片转为未分类")

            return JSONResponse(content={
                'code': 200,
                'msg': f'分类删除成功，已处理 {image_count} 张图片'
            })
    except Exception as e:
        print(f"[ERROR] 删除分类时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '删除分类时发生错误'
        }, status_code=500)






async def api_admin_categories(current_user: dict = Depends(get_current_admin)):
    """获取分类完整列表（仅管理员）

    公开的 /api/categories 只返回展示字段；管理端需要 id / status 等内部字段，
    因此单独提供本接口，避免把内部数据暴露给匿名访客。
    """
    from ...core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            rows = await conn.fetch('''
                SELECT c.id, c.name, c.description, c.status, c.created_at, c.updated_at,
                       COALESCE(cnt.total, 0) AS image_count
                FROM categories c
                LEFT JOIN (
                    SELECT category_id, COUNT(*) AS total
                    FROM images
                    WHERE status = 'enabled'
                    GROUP BY category_id
                ) cnt ON cnt.category_id = c.id
                ORDER BY c.created_at DESC
            ''')

        categories = []
        for row in rows:
            categories.append({
                'id': row['id'],
                'name': row['name'],
                'description': row['description'] or '',
                'status': row['status'],
                'image_count': int(row['image_count'] or 0),
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
            })

        return JSONResponse(content={
            'code': 200,
            'msg': 'success',
            'data': {'categories': categories, 'total': len(categories)},
        })
    except Exception as e:
        print(f"[ERROR] 获取分类列表失败: {str(e)}")
        return JSONResponse(content={'code': 500, 'msg': '获取分类列表失败'}, status_code=500)


# ==================== 管理端：总览统计 ====================
