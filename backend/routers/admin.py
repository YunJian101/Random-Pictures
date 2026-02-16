#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员路由模块
处理管理员相关的API请求
"""

from fastapi import Depends, Request, HTTPException, Body
from fastapi.responses import JSONResponse

from ..core.security.auth import (
    get_all_users,
    get_user_by_id,
    update_user_info,
    ban_user,
    unban_user,
    delete_user,
    update_user_role,
    register_user
)
from ..api.dependencies import get_current_admin
from ..schemas.schemas import UserCreateRequest, UserUpdateRequest, CreateAdminRequest


async def api_admin_users(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户列表API"""
    users = await get_all_users()

    formatted_users = []
    for user in users:
        formatted_users.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': 'admin' if user['type'] == '管理员' else 'vip' if user['type'] == 'VIP用户' else 'user',
            'created_at': user['registerDate'],
            'last_login': user['lastLogin'],
            'is_banned': user['status'] == '封禁',
            'avatar_url': user['avatar']
        })

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'users': formatted_users}
    })


async def api_admin_user_detail(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户详情API"""
    user = await get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    formatted_user = {
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'role': 'admin' if user['type'] == '管理员' else 'vip' if user['type'] == 'VIP用户' else 'user',
        'created_at': user['registerDate'],
        'last_login': user['lastLogin'],
        'is_banned': user['status'] == '封禁',
        'avatar_url': user['avatar']
    }

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'user': formatted_user}
    })


async def api_admin_users_create(data: UserCreateRequest, current_user: dict = Depends(get_current_admin)):
    """管理员创建用户API"""
    result = await register_user(data.username, data.email or '', data.password)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_update(user_id: int, data: UserUpdateRequest, current_user: dict = Depends(get_current_admin)):
    """管理员更新用户信息API"""
    result = await update_user_info(user_id, data.username, data.email)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_ban(user_id: int, request: Request = None, current_user: dict = Depends(get_current_admin)):
    """管理员封禁用户API"""
    reason = None
    if request:
        try:
            body = await request.json()
            reason = body.get('reason')
        except:
            pass
    result = await ban_user(user_id, reason=reason)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_unban(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员解封用户API"""
    result = await unban_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_admin_user_delete(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员删除用户API"""
    result = await delete_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


async def api_create_admin(data: CreateAdminRequest):
    """创建管理员用户API（仅用于初始化）"""
    # 检查是否已存在管理员
    from backend.core.database import get_async_db_connection
    
    try:
        async with get_async_db_connection() as conn:
            admin_count = await conn.fetchval('SELECT COUNT(*) FROM users WHERE role = $1', 'admin')
            
            if admin_count > 0:
                return JSONResponse(content={
                    'code': 403,
                    'msg': '管理员账户已存在，此接口已禁用'
                }, status_code=403)
    except Exception as e:
        print(f"检查管理员账户时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '检查管理员账户时发生错误'
        }, status_code=500)

    # 继续原有逻辑
    result = await register_user(data.username, data.email or '', data.password)

    if result['code'] == 200:
        user_id = result['data']['id']
        update_result = await update_user_role(user_id, 'admin')
        if update_result['code'] == 200:
            result['msg'] = '管理员用户创建成功'
            result['data']['role'] = 'admin'
        else:
            result = update_result

    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


# 分类管理API
async def api_admin_create_category(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员创建分类API"""
    from ..core.database import get_async_db_connection
    
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
    from ..core.database import get_async_db_connection
    
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


async def api_admin_delete_category(category_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员删除分类API"""
    from ..core.database import get_async_db_connection

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





async def api_system_backups(current_user: dict = Depends(get_current_admin)):
    """系统备份列表API"""
    try:
        from ..services.update_service import UpdateService
        update_service = UpdateService()
        backups = await update_service.get_backups()

        # 格式化备份列表
        formatted_backups = []
        for i, backup in enumerate(backups, 1):
            # 计算文件大小
            size_bytes = backup['size']
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.2f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            
            formatted_backups.append({
                'id': i,
                'time': backup['timestamp'],
                'version': backup['version'],
                'size': size_str,
                'filename': backup['filename']
            })

        return JSONResponse(content={
            'code': 200,
            'msg': 'success',
            'data': {
                'backups': formatted_backups
            }
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取备份列表失败: {str(e)}")
        print(f"[ERROR] 获取备份列表失败: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '获取备份列表失败'
        }, status_code=500)


async def api_system_version(current_user: dict = Depends(get_current_admin)):
    """系统版本信息API - 获取本地版本信息"""
    try:
        # 获取当前版本和版本日期
        try:
            from backend import __version__, __version_date__
            current_version = __version__
            current_version_date = __version_date__
        except ImportError as e:
            if "__version_date__" in str(e):
                from backend import __version__
                current_version = __version__
                current_version_date = '未知日期'
            else:
                current_version = '未知版本'
                current_version_date = '未知日期'

        return JSONResponse(content={
            'code': 200,
            'msg': 'success',
            'data': {
                'version': current_version,
                'version_date': current_version_date
            }
        })
    except Exception as e:
        print(f"[ERROR] 获取版本信息失败: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '获取版本信息失败'
        }, status_code=500)

async def api_system_check_update(current_user: dict = Depends(get_current_admin)):
    """系统更新检查API - 仅获取GitHub版本信息"""
    try:
        import json
        import aiohttp

        # 从GitHub API获取最新版本信息
        github_api_url = "https://api.github.com/repos/YunJian101/Random-Pictures/releases"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(github_api_url, timeout=10, ssl=False) as response:
                # 检查是否是GitHub API速率限制错误
                if response.status == 403:
                    try:
                        error_data = await response.json()
                        if error_data.get('message', '').lower().startswith('api rate limit exceeded'):
                            return JSONResponse(content={
                                'code': 429,
                                'msg': 'GitHub API速率限制，请稍后再试'
                            }, status_code=429)
                    except:
                        pass
                
                response.raise_for_status()
                releases = await response.json()
                
                changelog = []

                # 处理前5个版本的更新日志
                for release in releases[:5]:
                    version = release.get('tag_name', '未知版本')
                    date = release.get('published_at', '').split('T')[0] if release.get('published_at') else '未知日期'
                    changes = []

                    # 解析更新内容
                    body = release.get('body', '')
                    if body:
                        # 简单解析Markdown格式的更新内容
                        lines = body.strip().split('\n')
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                changes.append(line)

                    changelog.append({
                        'version': version,
                        'date': date,
                        'changes': changes if changes else ['无更新说明']
                    })

                # 获取最新版本信息
                latest_version = changelog[0]['version'] if changelog else '未知'
                latest_version_date = changelog[0]['date'] if changelog else '未知'

                return JSONResponse(content={
                    'code': 200,
                    'msg': 'success',
                    'data': {
                        'latest_version': latest_version,
                        'latest_version_date': latest_version_date,
                        'changelog': changelog
                    }
                })
    except aiohttp.ClientResponseError as e:
        # 处理HTTP错误
        if e.status == 403:
            return JSONResponse(content={
                'code': 429,
                'msg': 'GitHub API速率限制，请稍后再试'
            }, status_code=429)
        print(f"[ERROR] 检查更新失败: {str(e)}")
        return JSONResponse(content={
            'code': 503,
            'msg': '获取版本信息失败'
        }, status_code=503)
    except Exception as e:
        print(f"[ERROR] 检查更新失败: {str(e)}")
        return JSONResponse(content={
            'code': 503,
            'msg': '获取版本信息失败'
        }, status_code=503)


async def api_system_execute_update(current_user: dict = Depends(get_current_admin)):
    """系统执行更新API"""
    try:
        from ..services.update_service import UpdateService
        update_service = UpdateService()
        update_result = await update_service.execute_update()

        return JSONResponse(content={
            'code': 200 if update_result['success'] else 500,
            'msg': update_result['message'],
            'data': update_result
        })
    except Exception as e:
        print(f"[ERROR] 执行更新失败: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': f'执行更新失败: {str(e)}'
        }, status_code=500)


async def api_admin_get_system_config(current_user: dict = Depends(get_current_admin)):
    """管理员获取系统配置API"""
    from ..core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            # 查询所有系统配置
            configs = await conn.fetch('SELECT config_key, config_value, description FROM system_configs')

            # 构建配置字典
            config_dict = {}
            for config in configs:
                config_dict[config['config_key']] = {
                    'value': config['config_value'],
                    'description': config['description']
                }

            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统配置成功',
                'data': config_dict
            })
    except Exception as e:
        print(f"[ERROR] 获取系统配置时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '获取系统配置时发生错误'
        }, status_code=500)


def validate_config_value(config_key: str, config_value: str) -> tuple[bool, str]:
    """
    验证配置值的有效性
    
    Args:
        config_key: 配置键
        config_value: 配置值
        
    Returns:
        (is_valid, error_message): 验证结果和错误信息
    """
    # 通用验证：配置值不能为空
    if config_value is None:
        return False, "配置值不能为空"
    
    # 转换为字符串
    config_value = str(config_value)
    
    # 导入工具函数
    from ..utils.utils import validate_local_path, is_remote_url
    
    # 根据配置键进行特定验证
    if config_key == 'site_name':
        if len(config_value) == 0:
            return False, "站点名称不能为空"
        if len(config_value) > 50:
            return False, "站点名称长度不能超过50个字符"
    elif config_key == 'site_domain':
        if config_value:
            if not is_remote_url(config_value):
                return False, "站点域名必须是有效的URL格式"
    elif config_key == 'favicon_url':
        if config_value:
            # 检查是否为URL
            if not is_remote_url(config_value):
                # 本地路径验证
                is_valid, error_msg = validate_local_path(config_value)
                if not is_valid:
                    return False, error_msg
                # 确保路径是相对路径，不包含绝对路径标志
                if config_value.startswith('/'):
                    # 允许以/开头的路径，但会在处理时转换为相对路径
                    pass
    elif config_key == 'icp_beian':
        if len(config_value) > 50:
            return False, "ICP备案号长度不能超过50个字符"
    elif config_key == 'beian_link':
        if config_value:
            if not is_remote_url(config_value):
                return False, "备案信息链接必须是有效的URL格式"
    elif config_key == 'timezone':
        if not config_value:
            return False, "时区设置不能为空"
        # 简化时区验证，避免依赖pytz模块
        # 只验证基本格式，不进行完整的时区名称验证
        import re
        timezone_pattern = r'^[A-Za-z_]+/[A-Za-z_]+$'
        if not re.match(timezone_pattern, config_value):
            return False, "请输入有效的时区名称格式，如 Asia/Shanghai"
    elif config_key in ['enable_access_log', 'show_beian_info', 'enable_path_traversal_protection', 'enable_hotlink_protection', 'enable_ip_blacklist']:
        if config_value not in ['true', 'false']:
            return False, "该配置必须设置为 'true' 或 'false'"
    
    return True, ""

async def api_admin_update_system_config(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员更新系统配置API"""
    from ..core.database import get_async_db_connection

    try:
        data = await request.json()
        config_key = data.get('key')
        config_value = data.get('value')

        if not config_key:
            return JSONResponse(content={
                'code': 400,
                'msg': '配置键不能为空'
            }, status_code=400)

        # 验证配置值
        is_valid, error_msg = validate_config_value(config_key, config_value)
        if not is_valid:
            return JSONResponse(content={
                'code': 400,
                'msg': error_msg
            }, status_code=400)

        async with get_async_db_connection() as conn:
            # 检查配置是否存在
            existing = await conn.fetchrow('SELECT id FROM system_configs WHERE config_key = $1', config_key)
            if not existing:
                return JSONResponse(content={
                    'code': 404,
                    'msg': '配置不存在'
                }, status_code=404)

            # 更新配置
            await conn.execute('''
                UPDATE system_configs 
                SET config_value = $1, updated_at = CURRENT_TIMESTAMP 
                WHERE config_key = $2
            ''', config_value, config_key)

            # 清除缓存，确保下次获取系统信息时从数据库读取最新值
            global _config_cache, _cache_expiry
            _config_cache = {}
            _cache_expiry = 0

            return JSONResponse(content={
                'code': 200,
                'msg': '配置更新成功'
            })
    except Exception as e:
        print(f"[ERROR] 更新系统配置时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '更新系统配置时发生错误'
        }, status_code=500)


async def api_admin_reset_system_config(current_user: dict = Depends(get_current_admin)):
    """管理员重置系统配置为默认值API"""
    from ..core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            # 重置所有配置为默认值（将 default_value 复制到 config_value）
            await conn.execute('''
                UPDATE system_configs 
                SET config_value = default_value, updated_at = CURRENT_TIMESTAMP
            ''')

            # 清除缓存，确保下次获取系统信息时从数据库读取最新值
            global _config_cache, _cache_expiry
            _config_cache = {}
            _cache_expiry = 0

            return JSONResponse(content={
                'code': 200,
                'msg': '系统配置已重置为默认值'
            })
    except Exception as e:
        print(f"[ERROR] 重置系统配置时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '重置系统配置时发生错误'
        }, status_code=500)


async def api_system_rollback(request: Request, current_user: dict = Depends(get_current_admin)):
    """系统回滚API"""
    try:
        data = await request.json()
        backup_path = data.get('backup_path')
        
        if not backup_path:
            return JSONResponse(content={
                'code': 400,
                'msg': '备份路径不能为空'
            }, status_code=400)

        from ..services.update_service import UpdateService
        update_service = UpdateService()
        rollback_result = await update_service.rollback(backup_path)

        return JSONResponse(content={
            'code': 200,
            'msg': rollback_result
        })
    except Exception as e:
        print(f"[ERROR] 执行回滚失败: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': f'执行回滚失败: {str(e)}'
        }, status_code=500)


# 配置缓存
_config_cache = {}
_cache_expiry = 0

async def api_get_system_timezone():
    """获取系统时区配置API（公共接口）"""
    from ..core.database import get_async_db_connection

    try:
        # 尝试从缓存获取
        global _config_cache, _cache_expiry
        import time
        
        # 检查缓存是否有效（5分钟过期）
        if time.time() < _cache_expiry and 'timezone' in _config_cache:
            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统时区成功（缓存）',
                'data': {
                    'timezone': _config_cache['timezone']
                }
            })

        async with get_async_db_connection() as conn:
            # 查询时区配置
            result = await conn.fetchval('SELECT config_value FROM system_configs WHERE config_key = $1', 'timezone')

            if result:
                timezone = result
            else:
                # 如果没有配置，使用默认值
                timezone = 'Asia/Shanghai'

            # 更新缓存
            _config_cache['timezone'] = timezone
            _cache_expiry = time.time() + 300  # 5分钟过期

            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统时区成功',
                'data': {
                    'timezone': timezone
                }
            })
    except Exception as e:
        print(f"[ERROR] 获取系统时区时发生错误: {str(e)}")
        # 发生错误时返回默认时区
        return JSONResponse(content={
            'code': 200,
            'msg': '获取系统时区失败，使用默认时区',
            'data': {
                'timezone': 'Asia/Shanghai'
            }
        })


async def api_get_system_info():
    """获取系统基本信息API（公共接口）"""
    from ..core.database import get_async_db_connection

    try:
        # 尝试从缓存获取
        global _config_cache, _cache_expiry
        import time
        
        # 检查缓存是否有效（5分钟过期）
        if time.time() < _cache_expiry and all(key in _config_cache for key in ['site_name', 'favicon_url']):
            # 构建响应数据
            response_data = {
                'site_name': _config_cache['site_name'],
                'favicon_url': _config_cache.get('favicon_url', '')
            }
            
            # 只有当显示备案信息开关开启时，才返回备案信息
            if _config_cache.get('show_beian_info') == 'true' and all(key in _config_cache for key in ['icp_beian', 'beian_link']):
                response_data['icp_beian_code'] = _config_cache['icp_beian']
                response_data['icp_beian_url'] = _config_cache['beian_link']
                response_data['show_beian_info'] = _config_cache['show_beian_info']
            
            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统基本信息成功（缓存）',
                'data': response_data
            })

        async with get_async_db_connection() as conn:
            # 一次查询获取所有需要的配置
            results = await conn.fetch('''
                SELECT config_key, config_value 
                FROM system_configs 
                WHERE config_key IN ($1, $2, $3, $4, $5, $6)
            ''', 'site_name', 'timezone', 'icp_beian', 'beian_link', 'show_beian_info', 'favicon_url')
            
            # 构建配置字典
            configs = {row['config_key']: row['config_value'] for row in results}
            
            # 获取配置值，使用默认值
            site_name = configs.get('site_name', '随机图API')
            timezone = configs.get('timezone', 'Asia/Shanghai')
            icp_beian_code = configs.get('icp_beian', '')
            icp_beian_url = configs.get('beian_link', 'https://beian.miit.gov.cn')
            show_beian_info = configs.get('show_beian_info', 'false')
            favicon_url = configs.get('favicon_url', '')
            
            # 更新缓存
            _config_cache.update({
                'site_name': site_name,
                'timezone': timezone,
                'icp_beian': icp_beian_code,
                'beian_link': icp_beian_url,
                'show_beian_info': show_beian_info,
                'favicon_url': favicon_url
            })
            _cache_expiry = time.time() + 300  # 5分钟过期

            # 构建响应数据
            response_data = {
                'site_name': site_name,
                'favicon_url': favicon_url
            }
            
            # 只有当显示备案信息开关开启时，才返回备案信息
            if show_beian_info == 'true':
                response_data['icp_beian_code'] = icp_beian_code
                response_data['icp_beian_url'] = icp_beian_url
                response_data['show_beian_info'] = show_beian_info
            
            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统基本信息成功',
                'data': response_data
            })
    except Exception as e:
        print(f"[ERROR] 获取系统基本信息时发生错误: {str(e)}")
        # 返回默认值
        return JSONResponse(content={
            'code': 200,
            'msg': '获取系统基本信息失败，使用默认值',
            'data': {
                'site_name': '随机图API',
                'favicon_url': ''
            }
        })


async def api_admin_batch_action(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员批量操作API
    支持下载、移动、删除选中的图片
    """
    from ..core.config import IMG_ROOT_DIR
    from ..utils.async_io import async_exists, async_getsize, async_remove, async_joinpath, async_makedirs
    from ..core.database import get_async_db_connection
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
            except Exception as e:
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
                                # 构建新的文件路径
                                new_file_path = os.path.join(category_name, filename)
                                new_full_path = os.path.join(IMG_ROOT_DIR, new_file_path)

                                # 物理移动文件
                                await asyncio.to_thread(shutil.move, old_full_path, new_full_path)

                                # 更新数据库
                                await conn.execute('UPDATE images SET category_id = $1, file_path = $2 WHERE id = $3', 
                                                 category_id_int, new_file_path, img_id)

                                return True, None
                            else:
                                return False, '文件不存在'
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
