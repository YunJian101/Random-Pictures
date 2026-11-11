#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · images
=============

图片批量操作：批量移动分类 / 批量删除
"""

from fastapi import (
    Depends,
    Request,
)
from fastapi.responses import JSONResponse
from ...api.dependencies import get_current_admin
from ...services.audit_service import record as audit

async def api_admin_batch_action(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员批量操作API
    支持下载、移动、删除选中的图片
    """
    from ...core.config import IMG_ROOT_DIR
    from ...utils.async_io import (
        async_exists,
        async_getsize,
        async_remove,
        async_makedirs,
        async_unique_filename,
    )
    from ...core.database import get_async_db_connection
    import os
    import zipfile
    import tempfile
    import shutil
    import asyncio

    try:
        # 解析请求体
        data = await request.json()
        action = data.get('action')
        image_ids = data.get('image_ids', [])
        category_id = data.get('category_id') or data.get('target_category')

        # 验证输入参数
        if not action:
            return JSONResponse(content={
                'code': 400,
                'msg': '操作类型不能为空'
            }, status_code=400)

        if action not in ['download', 'move', 'delete']:
            return JSONResponse(content={
                'code': 400,
                'msg': '无效的操作类型'
            }, status_code=400)

        if not image_ids or not isinstance(image_ids, list):
            return JSONResponse(content={
                'code': 400,
                'msg': '图片ID列表不能为空'
            }, status_code=400)

        # 先记一条「发起了什么批量操作」，失败明细由下面的返回值体现
        action_label = {'download': '批量下载', 'move': '批量移动分类', 'delete': '批量删除'}[action]
        await audit(
            request, 'image.batch', current_user,
            target_type='image',
            target_id=','.join(str(i) for i in image_ids[:20]) + ('…' if len(image_ids) > 20 else ''),
            detail=f"{action_label} {len(image_ids)} 张图片"
                   + (f"，目标分类 #{category_id}" if action == 'move' and category_id else ''),
            metadata={'action': action, 'count': len(image_ids), 'category_id': category_id},
        )

        # 验证图片ID是否有效
        valid_image_ids = []
        failed_items = []

        async with get_async_db_connection() as conn:
            for img_id in image_ids:
                try:
                    # 将图片ID转换为整数
                    img_id_int = int(img_id)
                    exists = await conn.fetchrow('SELECT id FROM images WHERE id = $1', img_id_int)
                    if exists:
                        valid_image_ids.append(img_id_int)
                    else:
                        failed_items.append({
                            'id': img_id,
                            'error': '图片不存在'
                        })
                except ValueError:
                    failed_items.append({
                        'id': img_id,
                        'error': '无效的图片ID格式'
                    })
                except Exception as e:
                    failed_items.append({
                        'id': img_id,
                        'error': str(e)
                    })

        if not valid_image_ids:
            return JSONResponse(content={
                'code': 400,
                'msg': '没有有效的图片ID',
                'data': {
                    'action': action,
                    'processed_count': 0,
                    'failed_count': len(failed_items),
                    'failed_items': failed_items
                }
            }, status_code=400)

        # 根据操作类型执行不同的逻辑
        if action == 'download':
            # 打包选中的图片为ZIP文件
            # 创建临时ZIP文件
            zip_filename = f"selected_images_{tempfile.mktemp()[-8:]}.zip"
            zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
            
            try:
                # 异步获取图片信息
                async with get_async_db_connection() as conn:
                    # 构建查询语句，使用asyncpg的参数占位符格式
                    placeholders = ','.join([f'${i+1}' for i in range(len(valid_image_ids))])
                    query = f'SELECT id, file_path, filename FROM images WHERE id IN ({placeholders})'
                    
                    # 执行查询
                    image_results = await conn.fetch(query, *valid_image_ids)
                
                # 将图片信息转换为字典，便于后续处理
                image_map = {img['id']: {'file_path': img['file_path'], 'filename': img['filename']} for img in image_results}
                
                # 使用线程池执行zipfile操作，避免阻塞事件循环
                async def create_zip():
                    """在后台线程中创建ZIP文件"""
                    def _create_zip():
                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for img_id in valid_image_ids:
                                if img_id in image_map:
                                    img_info = image_map[img_id]
                                    file_path = img_info['file_path']
                                    filename = img_info['filename']
                                    # 构建完整的文件路径
                                    full_path = os.path.join(IMG_ROOT_DIR, file_path)
                                    if os.path.exists(full_path):
                                        # 将文件添加到ZIP文件中
                                        zipf.write(full_path, arcname=filename)
                    
                    await asyncio.to_thread(_create_zip)
                
                # 执行异步ZIP创建
                await create_zip()
                
                # 检查ZIP文件是否为空
                zip_size = await async_getsize(zip_path)
                if zip_size == 0:
                    await async_remove(zip_path)
                    return JSONResponse(content={
                        'code': 500,
                        'msg': '打包失败，ZIP文件为空',
                        'data': {
                            'action': action,
                            'processed_count': 0,
                            'failed_count': len(valid_image_ids),
                            'failed_items': [{'id': img_id, 'error': '打包失败'} for img_id in valid_image_ids]
                        }
                    }, status_code=500)

                # 直接返回ZIP文件
                from fastapi.responses import FileResponse
                from fastapi import BackgroundTasks
                
                # 设置响应头，让浏览器下载文件
                headers = {
                    'Content-Disposition': f'attachment; filename="{zip_filename}"'
                }
                
                # 定义后台任务，在文件下载后删除临时文件
                def cleanup_temp_file(file_path: str):
                    """删除临时文件的后台任务"""
                    import time
                    # 设置下载超时时间为15分钟
                    time.sleep(900)  # 15分钟后删除临时文件
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"临时文件已删除: {file_path}")
                    except Exception as e:
                        print(f"删除临时文件时出错: {str(e)}")
                
                # 创建后台任务
                background_tasks = BackgroundTasks()
                background_tasks.add_task(cleanup_temp_file, zip_path)
                
                return FileResponse(
                    path=zip_path,
                    filename=zip_filename,
                    headers=headers,
                    media_type='application/zip',
                    background=background_tasks
                )
            except Exception:
                # 清理临时文件
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                raise

        elif action == 'move':
            # 验证目标分类ID是否有效
            if not category_id:
                return JSONResponse(content={
                    'code': 400,
                    'msg': '目标分类ID不能为空',
                    'data': {
                        'action': action,
                        'processed_count': 0,
                        'failed_count': len(valid_image_ids),
                        'failed_items': [{'id': img_id, 'error': '目标分类ID不能为空'} for img_id in valid_image_ids]
                    }
                }, status_code=400)

            # 将分类ID转换为整数
            try:
                category_id_int = int(category_id)
            except ValueError:
                return JSONResponse(content={
                    'code': 400,
                    'msg': '无效的分类ID格式',
                    'data': {
                        'action': action,
                        'processed_count': 0,
                        'failed_count': len(valid_image_ids),
                        'failed_items': [{'id': img_id, 'error': '无效的分类ID格式'} for img_id in valid_image_ids]
                    }
                }, status_code=400)

            # 检查分类是否存在
            category_name = None
            async with get_async_db_connection() as conn:
                result = await conn.fetchrow('SELECT name FROM categories WHERE id = $1', category_id_int)
                if not result:
                    return JSONResponse(content={
                        'code': 400,
                        'msg': '目标分类不存在',
                        'data': {
                            'action': action,
                            'processed_count': 0,
                            'failed_count': len(valid_image_ids),
                            'failed_items': [{'id': img_id, 'error': '目标分类不存在'} for img_id in valid_image_ids]
                        }
                    }, status_code=400)
                category_name = result['name']

            # 创建目标分类目录
            target_dir = os.path.join(IMG_ROOT_DIR, category_name)
            await async_makedirs(target_dir, exist_ok=True)

            # 移动图片
            moved_count = 0
            move_failed_items = []
            move_success_items = []

            # 异步移动单个图片的函数
            async def move_single_image(img_id):
                try:
                    async with get_async_db_connection() as conn:
                        # 获取图片信息
                        result = await conn.fetchrow('SELECT file_path, filename FROM images WHERE id = $1', img_id)
                        if result:
                            old_file_path = result['file_path']
                            filename = result['filename']
                            # 构建完整的文件路径
                            old_full_path = os.path.join(IMG_ROOT_DIR, old_file_path)
                            if await async_exists(old_full_path):
                                # 目标目录里已有同名文件就顺延（名字_1.jpg…）：
                                # shutil.move 在目标已存在时会静默覆盖，把另一张图的内容冲掉，
                                # 之后两条记录还都指向同一个文件（实测会丢图）
                                unique_name = await async_unique_filename(
                                    target_dir,
                                    filename,
                                    is_taken=lambda name: conn.fetchval(
                                        'SELECT id FROM images WHERE file_path = $1 AND id <> $2',
                                        os.path.join(category_name, name),
                                        img_id,
                                    ),
                                )
                                # 构建新的文件路径
                                new_file_path = os.path.join(category_name, unique_name)
                                new_full_path = os.path.join(IMG_ROOT_DIR, new_file_path)

                                # 物理移动文件
                                await asyncio.to_thread(shutil.move, old_full_path, new_full_path)

                                # 更新数据库（重名顺延过的话，filename 也要一起改）
                                await conn.execute(
                                    'UPDATE images SET category_id = $1, file_path = $2, filename = $3 WHERE id = $4',
                                    category_id_int, new_file_path, unique_name, img_id,
                                )

                                return True, None
                            else:
                                return False, '原文件不存在（可能已被删除）'
                        else:
                            return False, '图片不存在'
                except Exception as e:
                    return False, str(e)

            # 并发执行移动操作
            tasks = [move_single_image(img_id) for img_id in valid_image_ids]
            results = await asyncio.gather(*tasks)

            # 处理结果
            for i, (success, error) in enumerate(results):
                img_id = valid_image_ids[i]
                if success:
                    moved_count += 1
                    move_success_items.append({'id': img_id, 'message': '移动成功'})
                else:
                    move_failed_items.append({'id': img_id, 'error': error})

            # 构建响应消息
            if move_success_items and move_failed_items:
                msg = f'部分移动成功，共处理 {moved_count} 张图片，失败 {len(move_failed_items)} 张'
            elif move_success_items:
                msg = f'移动成功，共处理 {moved_count} 张图片'
            else:
                msg = f'移动失败，共 {len(move_failed_items)} 张图片'

            return JSONResponse(content={
                'code': 200 if move_success_items else 400,
                'msg': msg,
                'data': {
                    'action': action,
                    'processed_count': moved_count,
                    'failed_count': len(move_failed_items),
                    'success_items': move_success_items,
                    'failed_items': move_failed_items
                }
            })

        elif action == 'delete':
            # 删除图片
            deleted_count = 0
            delete_failed_items = []
            delete_success_items = []

            # 异步删除单个图片的函数
            async def delete_single_image(img_id):
                try:
                    async with get_async_db_connection() as conn:
                        # 获取图片信息
                        result = await conn.fetchrow('SELECT file_path FROM images WHERE id = $1', img_id)
                        if result:
                            file_path = result['file_path']
                            # 构建完整的文件路径
                            full_path = os.path.join(IMG_ROOT_DIR, file_path)
                            if await async_exists(full_path):
                                # 物理删除文件
                                await async_remove(full_path)

                            # 从数据库中删除
                            await conn.execute('DELETE FROM images WHERE id = $1', img_id)

                            return True, None
                        else:
                            return False, '图片不存在'
                except Exception as e:
                    return False, str(e)

            # 并发执行删除操作
            tasks = [delete_single_image(img_id) for img_id in valid_image_ids]
            results = await asyncio.gather(*tasks)

            # 处理结果
            for i, (success, error) in enumerate(results):
                img_id = valid_image_ids[i]
                if success:
                    deleted_count += 1
                    delete_success_items.append({'id': img_id, 'message': '删除成功'})
                else:
                    delete_failed_items.append({'id': img_id, 'error': error})

            # 构建响应消息
            if delete_success_items and delete_failed_items:
                msg = f'部分删除成功，共处理 {deleted_count} 张图片，失败 {len(delete_failed_items)} 张'
            elif delete_success_items:
                msg = f'删除成功，共处理 {deleted_count} 张图片'
            else:
                msg = f'删除失败，共 {len(delete_failed_items)} 张图片'

            return JSONResponse(content={
                'code': 200 if delete_success_items else 400,
                'msg': msg,
                'data': {
                    'action': action,
                    'processed_count': deleted_count,
                    'failed_count': len(delete_failed_items),
                    'success_items': delete_success_items,
                    'failed_items': delete_failed_items
                }
            })

    except Exception as e:
        print(f"[ERROR] 批量操作时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': f'批量操作时发生错误: {str(e)}'
        }, status_code=500)


# ==================== 管理端：分类全量列表 ====================
