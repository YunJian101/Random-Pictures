#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · system
=============

系统信息与版本更新：版本号、检查更新、执行更新、备份、回滚、时区、站点信息
"""

import time
from pathlib import Path

from fastapi import (
    Depends,
    Request,
)
from fastapi.responses import JSONResponse

from ...api.dependencies import get_current_admin
from ...services.audit_service import record as audit

async def api_system_backups(current_user: dict = Depends(get_current_admin)):
    """系统备份列表API"""
    try:
        from ...services.update_service import UpdateService
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


async def api_system_version():
    """系统版本信息API - 公开接口（仅返回版本号与日期，不含任何内部数据）"""
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

                # 1.x → 2.x 不支持软件内更新：2.0.0 是重构版，文件结构变了，
                # 旧版本的「替换文件」更新逻辑覆盖不了，只能手动更新
                try:
                    from backend import __version__ as current_version
                except Exception:
                    current_version = '0.0.0'
                from ...services.update_service import UpdateService
                manual_update_required = UpdateService.requires_manual_update(
                    current_version, latest_version
                )

                return JSONResponse(content={
                    'code': 200,
                    'msg': 'success',
                    'data': {
                        'latest_version': latest_version,
                        'latest_version_date': latest_version_date,
                        'manual_update_required': manual_update_required,
                        'manual_update_hint': (
                            f'当前 {current_version} 不能软件内更新到 {latest_version}：'
                            f'这是跨大版本重构，请手动更新（拉取代码 → 替换 backend/ 与 frontend/ → '
                            f'docker compose up -d --build）'
                            if manual_update_required else ''
                        ),
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


async def api_system_execute_update(request: Request, current_user: dict = Depends(get_current_admin)):
    """系统执行更新API"""
    try:
        from ...services.update_service import UpdateService
        update_service = UpdateService()
        update_result = await update_service.execute_update()

        await audit(request, 'system.update', current_user,
                    target_type='system', target_id=update_result.get('version'),
                    detail=('执行版本更新：' + str(update_result.get('message', '')))[:200])

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



async def api_system_rollback(request: Request, current_user: dict = Depends(get_current_admin)):
    """系统回滚API"""
    try:
        data = await request.json()
        backup_path = (data.get('backup_path') or '').strip()

        if not backup_path:
            return JSONResponse(content={
                'code': 400,
                'msg': '备份路径不能为空'
            }, status_code=400)

        from ...services.update_service import UpdateService
        update_service = UpdateService()

        # 前端「备份列表」只下发文件名（列表接口不下发完整路径），这里补成备份目录下的
        # 绝对路径；同时挡住 ../ 之类越权路径——只允许备份目录里的文件
        backup_dir = update_service.backup_dir.resolve()
        candidate = Path(backup_path)
        if not candidate.is_absolute():
            candidate = backup_dir / candidate
        candidate = candidate.resolve()
        if backup_dir not in candidate.parents:
            return JSONResponse(content={
                'code': 400,
                'msg': '备份文件必须位于备份目录内'
            }, status_code=400)
        if not candidate.is_file():
            return JSONResponse(content={
                'code': 400,
                'msg': f'备份文件不存在：{candidate.name}'
            }, status_code=400)

        rollback_result = await update_service.rollback(str(candidate))

        await audit(request, 'system.rollback', current_user,
                    target_type='system', target_id=candidate.name,
                    detail=f'回滚到备份 {candidate.name}（{rollback_result}）'[:200])

        return JSONResponse(content={
            'code': 200,
            'msg': rollback_result
        })
    except FileNotFoundError as e:
        return JSONResponse(content={
            'code': 400,
            'msg': str(e)
        }, status_code=400)
    except Exception as e:
        print(f"[ERROR] 执行回滚失败: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': f'回滚失败: {str(e)}'
        }, status_code=500)


# ==================== 站点信息缓存 ====================
# /api/system/info 与 /api/system/timezone 是公开接口，首页每次加载都会打，
# 这里做一层 5 分钟的进程内缓存；配置一改就由 invalidate_config_cache() 立刻失效。
CONFIG_CACHE_TTL = 300
_config_cache: dict = {}
_cache_expiry = 0.0


def invalidate_config_cache() -> None:
    """配置变更后调用：清空缓存，下次读库拿最新值"""
    global _cache_expiry
    _config_cache.clear()
    _cache_expiry = 0.0


def _cache_fresh(required=()) -> bool:
    return time.time() < _cache_expiry and all(k in _config_cache for k in required)


def _cache_store(values: dict) -> None:
    global _cache_expiry
    _config_cache.update(values)
    _cache_expiry = time.time() + CONFIG_CACHE_TTL


async def api_get_system_timezone():
    """获取系统时区配置API（公共接口）"""
    from ...core.database import get_async_db_connection

    try:
        # 检查缓存是否有效（5分钟过期）
        if _cache_fresh(('timezone',)):
            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统时区成功（缓存）',
                'data': {'timezone': _config_cache['timezone']},
            })

        async with get_async_db_connection() as conn:
            timezone = await conn.fetchval(
                'SELECT config_value FROM system_configs WHERE config_key = $1', 'timezone'
            ) or 'Asia/Shanghai'

            _cache_store({'timezone': timezone})

            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统时区成功',
                'data': {'timezone': timezone},
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
    from ...core.database import get_async_db_connection

    try:
        # 检查缓存是否有效（5分钟过期）
        if _cache_fresh(('site_name', 'favicon_url')):
            response_data = {
                'site_name': _config_cache['site_name'],
                'favicon_url': _config_cache.get('favicon_url', ''),
                # 首页「稳定交付 N 天」按这个日期算（公开信息，不含任何个人数据）
                'launch_date': _config_cache.get('site_launch_date', ''),
            }

            # 只有当显示备案信息开关开启时，才返回备案信息
            if _config_cache.get('show_beian_info') == 'true' and all(
                key in _config_cache for key in ['icp_beian', 'beian_link']
            ):
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
                WHERE config_key IN ($1, $2, $3, $4, $5, $6, $7)
            ''', 'site_name', 'timezone', 'icp_beian', 'beian_link', 'show_beian_info', 'favicon_url',
                'site_launch_date')
            
            # 构建配置字典
            configs = {row['config_key']: row['config_value'] for row in results}
            
            # 获取配置值，使用默认值
            site_name = configs.get('site_name', '随机图API')
            timezone = configs.get('timezone', 'Asia/Shanghai')
            icp_beian_code = configs.get('icp_beian', '')
            icp_beian_url = configs.get('beian_link', 'https://beian.miit.gov.cn')
            show_beian_info = configs.get('show_beian_info', 'false')
            favicon_url = configs.get('favicon_url', '')
            launch_date = configs.get('site_launch_date', '')
            
            # 更新缓存
            _cache_store({
                'site_name': site_name,
                'timezone': timezone,
                'icp_beian': icp_beian_code,
                'beian_link': icp_beian_url,
                'show_beian_info': show_beian_info,
                'favicon_url': favicon_url,
                'site_launch_date': launch_date
            })

            # 构建响应数据
            response_data = {
                'site_name': site_name,
                'favicon_url': favicon_url,
                'launch_date': launch_date
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
                'favicon_url': '',
                'launch_date': ''
            }
        })


