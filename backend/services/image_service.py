#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片服务模块 - 核心业务逻辑
==========================

所有列表/随机逻辑都在 SQL 层完成分页与抽样：
- 列表：COUNT + LIMIT/OFFSET，不再把全表读进内存再切片
- 随机：按 offset 随机定位，避免 ORDER BY RANDOM() 的全表排序
"""

from typing import Optional
from urllib.parse import quote

from ..core.config import ADMIN_PAGE_SIZE, CATEGORY_PAGE_SIZE
from ..core.database import get_async_db_connection


def _format_size(size_bytes: int) -> str:
    """人类可读的文件大小"""
    size = int(size_bytes or 0)
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.1f}MB"


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


# ==================== 分类内图片（分页） ====================
async def get_paginated_category_images(category_name: str, page: int = 1) -> dict:
    """分页获取指定分类下的图片"""
    empty = {
        "category_name": category_name,
        "images": [],
        "current_page": 1,
        "total_pages": 0,
        "total_images": 0,
        "page_size": CATEGORY_PAGE_SIZE,
    }

    try:
        async with get_async_db_connection() as conn:
            category = await conn.fetchrow(
                "SELECT id FROM categories WHERE name = $1 AND status = 'enabled'",
                category_name,
            )
            if not category:
                return empty

            total_images = await conn.fetchval(
                "SELECT COUNT(*) FROM images WHERE category_id = $1 AND status = 'enabled'",
                category['id'],
            )
            total_images = int(total_images or 0)
            if total_images == 0:
                return empty

            total_pages = max(1, (total_images + CATEGORY_PAGE_SIZE - 1) // CATEGORY_PAGE_SIZE)
            page = max(1, min(page, total_pages))

            rows = await conn.fetch('''
                SELECT filename, file_path
                FROM images
                WHERE category_id = $1 AND status = 'enabled'
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            ''', category['id'], CATEGORY_PAGE_SIZE, (page - 1) * CATEGORY_PAGE_SIZE)

            images = [{
                "name": row['filename'],
                "url": f"/image?path={quote(row['file_path'])}",
                "path": row['file_path'],
            } for row in rows]

            return {
                "category_name": category_name,
                "images": images,
                "current_page": page,
                "total_pages": total_pages,
                "total_images": total_images,
                "page_size": CATEGORY_PAGE_SIZE,
            }
    except Exception as e:
        print(f"[ERROR] 获取分类图片失败: {str(e)}")
        return empty


# ==================== 随机取图 ====================
def _random_pool_sql(conditions, params) -> str:
    """拼一条"先组池子再随机定位"的 SQL

    比 ORDER BY RANDOM() 快得多：只在池子里随机抽一个偏移量，
    不需要全表排序。conditions 用 $N 占位，params 是已排好序的参数。
    """
    where = ' AND '.join(conditions)
    return f"""
        WITH pool AS (
            SELECT filename, file_path
            FROM images
            WHERE {where}
        )
        SELECT filename, file_path FROM pool
        OFFSET floor(random() * (SELECT COUNT(*) FROM pool))::int
        LIMIT 1
    """


def _filter_conditions(base: list, params: list, exclude_ids=None, formats=None) -> list:
    """在基础条件上追加 exclude（排除图片 id）与 format（限定后缀）过滤"""
    conditions = list(base)

    if exclude_ids:
        params.append(list(exclude_ids))
        conditions.append(f'id <> ALL(${len(params)}::int[])')

    if formats:
        params.append(list(formats))
        conditions.append(f'LOWER(format) = ANY(${len(params)}::text[])')

    return conditions


async def get_random_image_in_category(
    category_name: str,
    exclude_ids=None,
    formats=None,
) -> Optional[dict]:
    """分类随机：找不到分类返回 None，分类为空返回 {'error': 'empty'}"""
    try:
        async with get_async_db_connection() as conn:
            category = await conn.fetchrow(
                "SELECT id FROM categories WHERE name = $1 AND status = 'enabled'",
                category_name,
            )
            if not category:
                return None

            params: list = [category['id']]
            conditions = _filter_conditions(
                ["category_id = $1", "status = 'enabled'"], params, exclude_ids, formats
            )

            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM images WHERE {' AND '.join(conditions)}", *params
            )
            if not count:
                return {"error": "empty"}

            row = await conn.fetchrow(_random_pool_sql(conditions, params), *params)
            if not row:
                return {"error": "empty"}

            return {
                "name": row['filename'],
                "url": f"/image?path={quote(row['file_path'])}",
                "path": row['file_path'],
            }
    except Exception as e:
        print(f"[ERROR] 分类随机取图失败: {str(e)}")
        return None


async def get_random_image_in_all_categories(exclude_ids=None, formats=None) -> Optional[dict]:
    """全局随机：任意启用图片"""
    try:
        async with get_async_db_connection() as conn:
            params: list = []
            conditions = _filter_conditions(["status = 'enabled'"], params, exclude_ids, formats)

            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM images WHERE {' AND '.join(conditions)}", *params
            )
            if not total:
                return {"error": "empty"}

            link = await conn.fetchrow(_random_pool_sql(conditions, params), *params)
            if not link:
                return {"error": "empty"}

            return {
                "name": link['filename'],
                "url": f"/image?path={quote(link['file_path'])}",
                "path": link['file_path'],
            }
    except Exception as e:
        print(f"[ERROR] 全局随机取图失败: {str(e)}")
        return None


# ==================== 管理端图片列表（分页） ====================
# 排序白名单：只允许这些固定片段拼进 SQL，避免注入
_SORT_SQL = {
    'created_desc': 'i.created_at DESC',
    'created_asc': 'i.created_at ASC',
    'size_desc': 'i.file_size DESC NULLS LAST',
    'size_asc': 'i.file_size ASC NULLS LAST',
    'views_desc': 'i.view_count DESC NULLS LAST',
    'name_asc': 'i.filename ASC',
}

DEFAULT_SORT = 'created_desc'


def resolve_sort(sort: str) -> str:
    """把请求的排序键解析成 SQL 片段（不认识的一律回落到默认）"""
    return _SORT_SQL.get(sort or '', _SORT_SQL[DEFAULT_SORT])


async def get_all_images(
    page: int = 1,
    category: str = '',
    keyword: str = '',
    sort: str = DEFAULT_SORT,
) -> dict:
    """管理端：分页获取图片列表，可按分类名 + 文件名关键字过滤，并指定排序"""
    keyword = (keyword or '').strip()
    order_by = resolve_sort(sort)
    try:
        async with get_async_db_connection() as conn:
            # 过滤条件统一拼装，避免 4 份几乎相同的 SQL
            where = ["i.status = 'enabled'"]
            params = []
            if category:
                params.append(category)
                where.append(f'c.name = ${len(params)}')
            if keyword:
                params.append(f'%{keyword}%')
                where.append(f'i.filename ILIKE ${len(params)}')
            where_sql = ' AND '.join(where)

            total = await conn.fetchval(
                f'''SELECT COUNT(*)
                    FROM images i
                    LEFT JOIN categories c ON i.category_id = c.id
                    WHERE {where_sql}''',
                *params,
            )

            total = int(total or 0)
            total_pages = max(1, (total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE) if total else 1
            page = max(1, min(page, total_pages))
            offset = (page - 1) * ADMIN_PAGE_SIZE

            rows = await conn.fetch(
                f'''SELECT i.id, i.filename, i.file_path, i.file_size, i.width, i.height,
                           i.view_count, i.created_at, c.name AS category_name
                    FROM images i
                    LEFT JOIN categories c ON i.category_id = c.id
                    WHERE {where_sql}
                    ORDER BY {order_by}
                    LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}''',
                *params, ADMIN_PAGE_SIZE, offset,
            )

        images = []
        for row in rows:
            size_bytes = int(row['file_size'] or 0)
            images.append({
                "id": row['id'],
                "name": row['filename'],
                "category": row['category_name'] or "未分类",
                "path": row['file_path'],
                "url": f"/image?path={quote(row['file_path'])}",
                "size_bytes": size_bytes,
                "size": _format_size(size_bytes),
                "resolution": f"{row['width'] or 0}×{row['height'] or 0}",
                "views": int(row['view_count'] or 0),
                "modified_time": _iso(row['created_at']),
            })

        return {
            "images": images,
            "current_page": page,
            "total_pages": total_pages,
            "total_images": total,
            "page_size": ADMIN_PAGE_SIZE,
            "sort": sort if sort in _SORT_SQL else DEFAULT_SORT,
        }
    except Exception as e:
        print(f"[ERROR] 获取图片列表失败: {str(e)}")
        return {
            "images": [],
            "current_page": 1,
            "total_pages": 1,
            "total_images": 0,
            "page_size": ADMIN_PAGE_SIZE,
            "sort": DEFAULT_SORT,
        }
