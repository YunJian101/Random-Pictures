#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新服务
=============

实现应用的在线更新功能，包括版本检查、备份、下载、验证、更新和回滚
"""

import os
import shutil
import requests
import tarfile
import zipfile
import hashlib
import time
import asyncio
import multiprocessing
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException
import logging
import signal
import sys
import threading

# 为回滚功能创建独立的日志记录器
rollback_logger = logging.getLogger('rollback_service')
rollback_logger.setLevel(logging.INFO)
if not rollback_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    rollback_logger.addHandler(handler)

logger = logging.getLogger(__name__)


class UpdateService:
    """
    更新服务类
    处理应用的在线更新流程
    """

    def __init__(self):
        """
        初始化更新服务
        """
        self.github_owner = "YunJian101"
        self.github_repo = "Random-Pictures"
        self.github_api = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}"
        self.backup_dir = Path("/app/backups")
        self.app_dir = Path("/app")
        self.temp_dir = Path("/app/temp_update")
        self._cached_latest_version = None
        self._cache_time = None
        self._cache_duration = 300  # 缓存5分钟
        
        # GitHub Personal Access Token (可选，用于私有仓库)
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        
        # 增强的请求配置
        self.request_timeout = 30
        self.max_retries = 5  # 增加重试次数
        self.retry_delay = 2
        self.ssl_verify = False  # 禁用SSL验证避免连接问题
        
        # 确保必要的目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 必需的文件列表用于验证
        self.required_files = [
            "backend/main.py",
            "backend/core/version.py",
            "frontend/index.html",
            "Dockerfile",
            "requirements.txt"
        ]

    async def get_current_version(self) -> str:
        """
        获取当前版本
        
        Returns:
            str: 当前版本号
        """
        try:
            from backend.core.version import __version__
            return __version__
        except ImportError:
            logger.warning("无法导入版本信息，使用默认版本")
            return "3.0.0"

    async def get_latest_version(self, force_refresh: bool = False) -> dict:
        """
        获取 GitHub 最新版本信息（带缓存和重试机制）

        Args:
            force_refresh: 是否强制刷新，忽略缓存
            
        Returns:
            dict: 最新版本信息
        """
        # 检查缓存
        if (not force_refresh and self._cached_latest_version and self._cache_time and
            time.time() - self._cache_time < self._cache_duration):
            logger.info("使用缓存的版本信息")
            return self._cached_latest_version

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RandomPictures-Updater/1.0"
        }
        
        # 如果有GitHub Token，添加认证头
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        # 实现增强的重试机制
        for attempt in range(self.max_retries):
            try:
                logger.info(f"请求 GitHub API (尝试 {attempt + 1}/{self.max_retries}): {self.github_api}/releases/latest")
                
                # 配置请求参数
                request_kwargs = {
                    "timeout": self.request_timeout,
                    "headers": headers,
                    "verify": self.ssl_verify
                }
                
                response = requests.get(
                    f"{self.github_api}/releases/latest",
                    **request_kwargs
                )
                
                logger.info(f"GitHub API 响应状态: {response.status_code}")
                
                if response.status_code == 401:
                    logger.error("GitHub token 认证失败")
                    raise HTTPException(status_code=401, detail="GitHub token 认证失败")
                elif response.status_code == 403:
                    logger.error("GitHub API 速率限制")
                    raise HTTPException(status_code=429, detail="GitHub API 速率限制，请稍后再试")
                elif response.status_code == 404:
                    logger.error("仓库或版本不存在")
                    raise HTTPException(status_code=404, detail="仓库或版本不存在")
                
                response.raise_for_status()
                data = response.json()
                
                result = {
                    "tag_name": data.get("tag_name", "").replace("v", ""),
                    "name": data.get("name", ""),
                    "body": data.get("body", ""),
                    "html_url": data.get("html_url", ""),
                    "published_at": data.get("published_at", ""),
                    "assets": data.get("assets", [])
                }
                
                # 更新缓存
                self._cached_latest_version = result
                self._cache_time = time.time()
                logger.info(f"获取最新版本成功: {result['tag_name']}")
                return result
                
            except requests.exceptions.SSLError as e:
                logger.warning(f"SSL错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    # SSL错误时短暂等待后重试
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                logger.error("SSL连接持续失败，请检查网络环境")
                raise HTTPException(status_code=503, detail="SSL连接失败，请检查网络环境或稍后重试")
                
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数退避
                    continue
                raise HTTPException(status_code=504, detail="请求超时，请检查网络连接")
                
            except requests.exceptions.ConnectionError:
                logger.warning(f"连接错误 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise HTTPException(status_code=503, detail="无法连接到GitHub，请检查网络连接")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常: {e}")
                raise HTTPException(status_code=500, detail=f"网络请求失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"获取最新版本失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取最新版本失败: {str(e)}")

        raise HTTPException(status_code=500, detail="达到最大重试次数，更新检查失败")

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        比较版本号，返回 1(v1>v2), -1(v1<v2), 0(相等)
        
        Args:
            v1: 版本号1
            v2: 版本号2
            
        Returns:
            int: 比较结果
        """
        def normalize(v):
            # 处理版本号中的字母和特殊字符
            import re
            parts = re.split(r'[.-]', v.lower())
            normalized = []
            for part in parts:
                if part.isdigit():
                    normalized.append(int(part))
                else:
                    # 将字母转换为数字进行比较
                    normalized.append(sum(ord(c) for c in part))
            return normalized

        n1, n2 = normalize(v1), normalize(v2)
        
        # 补齐长度
        max_len = max(len(n1), len(n2))
        n1.extend([0] * (max_len - len(n1)))
        n2.extend([0] * (max_len - len(n2)))

        for a, b in zip(n1, n2):
            if a > b:
                return 1
            elif a < b:
                return -1

        return 0

    async def check_update(self) -> dict:
        """
        检查更新
        
        Returns:
            dict: 更新检查结果
        """
        try:
            current_version = await self.get_current_version()
            latest_info = await self.get_latest_version()
            latest_version = latest_info["tag_name"].replace("v", "")

            comparison = self._compare_versions(current_version, latest_version)

            return {
                "current_version": current_version,
                "latest_version": latest_version,
                "has_update": comparison == -1,
                "update_available": comparison == -1,
                "release_info": latest_info
            }
        except Exception as e:
            logger.error(f"检查更新过程中发生错误: {e}")
            raise

    async def backup_current_version(self) -> str:
        """
        备份当前版本为压缩文件
        
        Returns:
            str: 备份文件路径
        """
        try:
            current_version = await self.get_current_version()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_{current_version}_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_filename

            logger.info(f"开始创建压缩备份，版本 {current_version}...")

            # 创建临时工作目录
            temp_dir = self.temp_dir / f"backup_{timestamp}"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # 要备份的文件和目录（只备份实际存在的）
            items_to_backup = [
                "backend",
                "frontend",
                "Dockerfile",
                "docker-compose.yml",
                "requirements.txt"
            ]

            backed_up_items = []

            for item in items_to_backup:
                source = self.app_dir / item
                if source.exists():
                    # 复制到临时目录
                    target = temp_dir / item
                    try:
                        if source.is_file():
                            shutil.copy2(source, target)
                        else:
                            shutil.copytree(source, target, dirs_exist_ok=True)
                        backed_up_items.append(item)
                        logger.debug(f"已准备: {item}")
                    except Exception as e:
                        logger.warning(f"准备 {item} 失败: {e}")

            # 创建元数据
            metadata = {
                "version": current_version,
                "timestamp": timestamp,
                "created_at": datetime.now().isoformat(),
                "items": backed_up_items,
                "backup_filename": backup_filename
            }

            # 保存元数据到临时目录
            metadata_file = temp_dir / "backup_metadata.json"
            try:
                import json
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                logger.debug("备份元数据已创建")
            except Exception as e:
                logger.warning(f"创建备份元数据失败: {e}")

            # 创建压缩文件
            logger.info(f"正在创建压缩文件: {backup_path}")
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in temp_dir.iterdir():
                    tar.add(item, arcname=item.name)

            # 清理临时目录
            shutil.rmtree(temp_dir)

            # 计算压缩文件大小
            backup_size = backup_path.stat().st_size
            logger.info(f"压缩备份创建完成: {backup_path}")
            logger.info(f"备份项目: {len(backed_up_items)}, 大小: {backup_size/1024/1024:.2f} MB")

            return str(backup_path)

        except Exception as e:
            logger.error(f"备份失败: {e}")
            # 清理临时目录
            if 'temp_dir' in locals() and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件SHA256哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: SHA256哈希值
        """
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    async def _download_with_auth(self, url: str, target_path: Path) -> bool:
        """
        使用认证头下载文件
        
        Args:
            url: 下载URL
            target_path: 目标文件路径
            
        Returns:
            bool: 下载是否成功
        """
        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RandomPictures-Updater/1.0"
            }
            
            # 如果有GitHub Token，添加认证头
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            for attempt in range(self.max_retries):
                try:
                    logger.info(f"下载文件 (尝试 {attempt + 1}/{self.max_retries})")
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=self.request_timeout,
                        stream=True,
                        verify=self.ssl_verify
                    )
                    response.raise_for_status()

                    # 下载文件
                    total_size = None
                    if 'content-length' in response.headers:
                        total_size = int(response.headers['content-length'])
                        logger.info(f"文件大小: {total_size} bytes")

                    downloaded_size = 0
                    with open(target_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                if total_size and downloaded_size % (total_size // 5 or 1024*1024) == 0:
                                    progress = (downloaded_size / total_size) * 100
                                    logger.info(f"下载进度: {progress:.1f}%")

                    logger.info(f"下载成功: {target_path} ({downloaded_size} bytes)")
                    return True

                except requests.exceptions.SSLError as e:
                    logger.warning(f"SSL错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                except requests.exceptions.Timeout:
                    logger.warning(f"下载超时 (尝试 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                except requests.exceptions.ConnectionError:
                    logger.warning(f"连接错误 (尝试 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                except Exception as e:
                    logger.warning(f"下载异常 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue

            return False

        except Exception as e:
            logger.error(f"下载过程发生错误: {e}")
            return False

    async def _download_with_fallback(self, url: str, target_path: Path, headers: dict) -> bool:
        """
        使用备用方法下载文件（通用方法，带重试）
        
        Args:
            url: 下载URL
            target_path: 目标文件路径
            headers: 请求头
            
        Returns:
            bool: 下载是否成功
        """
        try:
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"备用下载 (尝试 {attempt + 1}/{self.max_retries})")
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=self.request_timeout,
                        stream=True,
                        verify=self.ssl_verify
                    )
                    response.raise_for_status()

                    with open(target_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    logger.info("备用下载成功")
                    return True

                except requests.exceptions.SSLError as e:
                    logger.warning(f"SSL错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                except requests.exceptions.Timeout:
                    logger.warning(f"超时 (尝试 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                except Exception as e:
                    logger.warning(f"异常 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue

            return False

        except Exception as e:
            logger.error(f"备用下载异常: {e}")
            return False

    async def download_update(self, tag_name: str) -> Path:
        """
        下载更新包（增强版，包含备用下载方法）
        
        Args:
            tag_name: 版本标签
            
        Returns:
            Path: 下载的更新包路径
        """
        try:
            # 清理临时目录
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"开始获取 Release 信息: v{tag_name}")
            
            # 获取 Release 信息（带认证和增强错误处理）
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RandomPictures-Updater/1.0"
            }
            
            # 如果有GitHub Token，添加认证头
            if self.github_token:
                headers["Authorization"] = f"Bearer {self.github_token}"
            
            # 增强的请求配置
            request_kwargs = {
                "timeout": self.request_timeout,
                "headers": headers,
                "verify": self.ssl_verify
            }
            
            # 实现重试机制
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(
                        f"{self.github_api}/releases/tags/v{tag_name}",
                        **request_kwargs
                    )
                    response.raise_for_status()
                    release_data = response.json()
                    break  # 成功则跳出重试循环
                    
                except requests.exceptions.SSLError as e:
                    logger.warning(f"获取Release信息SSL错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    raise HTTPException(status_code=503, detail=f"SSL连接失败: {str(e)}")
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"获取Release信息超时 (尝试 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    raise HTTPException(status_code=504, detail="获取Release信息超时")
                    
                except requests.exceptions.ConnectionError:
                    logger.warning(f"获取Release信息连接错误 (尝试 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    raise HTTPException(status_code=503, detail="无法连接到GitHub获取Release信息")
                    
                except Exception as e:
                    logger.error(f"获取Release信息失败: {e}")
                    raise HTTPException(status_code=500, detail=f"获取Release信息失败: {str(e)}")
            
            else:
                raise HTTPException(status_code=500, detail="达到最大重试次数，无法获取Release信息")

            # 查找源码压缩包
            assets = release_data.get("assets", [])
            download_url = None
            archive_name = None
            expected_hash = None
            tag_name_from_release = release_data.get("tag_name", "")

            logger.info(f"Release tag_name: {tag_name_from_release}")

            # 优先查找带哈希校验的资产
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith((".tar.gz", ".zip")):
                    download_url = asset["browser_download_url"]
                    archive_name = asset["name"]
                    logger.info(f"找到资产文件: {archive_name}")
                    # 查找对应的哈希文件
                    hash_asset_name = f"{asset['name']}.sha256"
                    for hash_asset in assets:
                        if hash_asset.get("name") == hash_asset_name:
                            expected_hash = hash_asset.get("browser_download_url")
                            break
                    break

            # 如果没有找到合适的资产，使用 GitHub API tarball endpoint
            if not download_url:
                # 使用GitHub API的tarball endpoint
                download_url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/tarball/{tag_name_from_release}"
                clean_tag = tag_name_from_release.lstrip('v')
                archive_name = f"{clean_tag}.tar.gz"
                logger.info(f"未找到资产，使用GitHub API tarball: {download_url}")

            # 下载文件
            archive_path = self.temp_dir / archive_name
            logger.info(f"开始下载更新包: {download_url}")

            # 使用统一的下载方法
            download_success = await self._download_with_auth(download_url, archive_path)

            # 如果认证下载失败，尝试备用下载方法（不带认证）
            if not download_success:
                logger.info("认证下载失败，尝试备用下载方法...")
                if await self._download_with_fallback(download_url, archive_path, headers):
                    download_success = True
                else:
                    raise HTTPException(status_code=503, detail="下载失败，请检查网络连接和仓库访问权限")

            # 验证文件完整性
            if expected_hash and download_success:
                try:
                    logger.info("正在验证文件完整性...")
                    hash_response = requests.get(expected_hash, timeout=10, headers=headers)
                    if hash_response.status_code == 200:
                        expected_sha256 = hash_response.text.strip().split()[0]
                        actual_sha256 = await self._calculate_file_hash(archive_path)
                        if expected_sha256.lower() == actual_sha256.lower():
                            logger.info("文件完整性验证通过")
                        else:
                            logger.warning("文件哈希不匹配，可能存在损坏")
                except Exception as e:
                    logger.warning(f"文件完整性验证失败: {e}")

            return archive_path
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"下载更新包失败: {e}")
            raise HTTPException(status_code=500, detail=f"下载更新包失败: {str(e)}")

    async def extract_update(self, archive_path: Path) -> Path:
        """
        解压更新包（增强版）
        
        Args:
            archive_path: 更新包路径
            
        Returns:
            Path: 解压后的项目根目录
        """
        try:
            extract_dir = self.temp_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"开始解压: {archive_path}")
            logger.info(f"解压目标目录: {extract_dir}")

            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
                    logger.info(f"ZIP文件解压完成，包含 {len(zip_ref.namelist())} 个文件")
            elif archive_path.name.endswith(".tar.gz") or archive_path.suffix == ".tgz":
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    members = tar_ref.getmembers()
                    tar_ref.extractall(extract_dir)
                    logger.info(f"TAR.GZ文件解压完成，包含 {len(members)} 个文件")
            else:
                raise HTTPException(status_code=500, detail=f"不支持的压缩包格式: {archive_path.name}")

            logger.info(f"解压完成: {extract_dir}")

            # 查找解压后的项目根目录
            extracted_items = list(extract_dir.iterdir())
            if not extracted_items:
                raise HTTPException(status_code=500, detail="解压后目录为空")

            # 如果只有一个目录，返回该目录作为项目根目录
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                project_root = extracted_items[0]
                logger.info(f"识别项目根目录: {project_root}")
                return project_root
            else:
                # 多个项目或文件，返回extract_dir
                logger.info("使用解压根目录作为项目根目录")
                return extract_dir
                
        except zipfile.BadZipFile:
            logger.error("ZIP文件损坏")
            raise HTTPException(status_code=500, detail="ZIP文件损坏")
        except tarfile.TarError:
            logger.error("TAR文件损坏")
            raise HTTPException(status_code=500, detail="TAR文件损坏")
        except Exception as e:
            logger.error(f"解压失败: {e}")
            raise HTTPException(status_code=500, detail=f"解压失败: {str(e)}")

    async def validate_update_files(self, source_dir: Path) -> bool:
        """
        验证更新文件完整性（只验证核心文件）
        
        Args:
            source_dir: 源目录
            
        Returns:
            bool: 验证是否通过
        """
        try:
            logger.info("开始验证更新文件完整性...")

            # 检查核心必须文件
            core_required_files = [
                "backend/main.py",
                "backend/core/version.py"
            ]

            missing_core_files = []
            for file_path in core_required_files:
                full_path = source_dir / file_path
                if not full_path.exists():
                    missing_core_files.append(file_path)
                    logger.error(f"缺少核心文件: {file_path}")

            if missing_core_files:
                logger.error(f"文件验证失败，缺少核心文件: {missing_core_files}")
                return False

            # 验证版本文件格式
            version_file = source_dir / "backend/core/version.py"
            if version_file.exists():
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if "__version__" not in content:
                            logger.error("版本文件格式不正确")
                            return False
                        # 验证版本号格式
                        import re
                        version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                        if version_match:
                            version = version_match.group(1)
                            logger.info(f"检测到新版本号: {version}")
                except Exception as e:
                    logger.error(f"读取版本文件失败: {e}")
                    return False

            # 检查关键目录结构
            critical_dirs = ["backend", "frontend"]
            for dir_name in critical_dirs:
                dir_path = source_dir / dir_name
                if not dir_path.exists() or not dir_path.is_dir():
                    logger.error(f"关键目录缺失或不是目录: {dir_name}")
                    return False

            logger.info("更新文件验证通过")
            return True

        except Exception as e:
            logger.error(f"文件验证过程中发生错误: {e}")
            return False

    async def apply_update_safely(self, source_dir: Path) -> str:
        """
        安全地应用更新（原子性操作）
        
        Args:
            source_dir: 源目录
            
        Returns:
            str: 更新结果
        """
        try:
            # 首先验证更新文件
            if not await self.validate_update_files(source_dir):
                raise HTTPException(status_code=500, detail="更新文件验证失败")

            # 要更新的文件和目录
            items_to_update = [
                "backend",
                "frontend",
                "Dockerfile",
                "docker-compose.yml",
                "requirements.txt"
            ]

            # 创建临时备份目录用于本次更新的快速回滚
            temp_backup_dir = self.temp_dir / "temp_backup"
            temp_backup_dir.mkdir(parents=True, exist_ok=True)

            logger.info("开始准备原子性更新...")
            
            # 第一步：备份当前文件到临时目录（安全操作）
            logger.info("第一步：备份当前文件到临时目录...")
            for item in items_to_update:
                source = self.app_dir / item
                backup_target = temp_backup_dir / item
                
                if source.exists():
                    try:
                        if source.is_file():
                            shutil.copy2(source, backup_target)
                        else:
                            shutil.copytree(source, backup_target, dirs_exist_ok=True)
                        logger.debug(f"已备份: {item}")
                    except Exception as e:
                        logger.error(f"备份 {item} 失败: {e}")
                        raise HTTPException(status_code=500, detail=f"备份 {item} 失败: {str(e)}")

            # 第二步：验证临时备份是否成功
            logger.info("第二步：验证临时备份完整性...")
            for item in items_to_update:
                backup_source = temp_backup_dir / item
                original_source = self.app_dir / item
                if original_source.exists() and not backup_source.exists():
                    error_msg = f"临时备份验证失败: {item}"
                    logger.error(error_msg)
                    # 清理不完整的临时备份
                    await self._cleanup_temp_backup(temp_backup_dir)
                    raise HTTPException(status_code=500, detail=error_msg)

            # 第三步：应用新文件（逐个文件覆盖）
            logger.info("第三步：应用新文件...")
            failed_items = []
            for item in items_to_update:
                new_source = source_dir / item
                target = self.app_dir / item

                if new_source.exists():
                    try:
                        logger.info(f"正在更新: {item}")

                        if new_source.is_file():
                            # 文件：直接覆盖
                            if target.exists():
                                target.unlink()
                            shutil.copy2(new_source, target)
                            logger.info(f"更新完成文件: {item}")
                        else:
                            # 目录：逐个文件覆盖
                            logger.info(f"开始更新目录: {item}")
                            dir_updated = 0

                            for src_file in new_source.rglob('*'):
                                if not src_file.is_file():
                                    continue

                                # 跳过 Python 缓存文件
                                if src_file.name.endswith('.pyc') or '__pycache__' in str(src_file):
                                    continue

                                # 计算相对路径
                                rel_path = src_file.relative_to(new_source)
                                dst_file = target / rel_path

                                # 创建目标目录
                                dst_file.parent.mkdir(parents=True, exist_ok=True)

                                # 覆盖文件
                                shutil.copy2(src_file, dst_file)
                                dir_updated += 1

                            logger.info(f"更新完成目录 {item}: {dir_updated} 个文件")

                    except Exception as e:
                        logger.error(f"更新 {item} 失败: {e}")
                        failed_items.append((item, str(e)))

            # 如果有任何项目更新失败，尝试回滚
            if failed_items:
                logger.error(f"部分文件更新失败，开始回滚: {[item[0] for item in failed_items]}")
                await self._rollback_from_temp_backup(temp_backup_dir)
                error_details = "; ".join([f"{item}: {error}" for item, error in failed_items])
                raise HTTPException(status_code=500, detail=f"更新失败，已回滚: {error_details}")

            # 第四步：清理临时备份
            logger.info("第四步：清理临时备份...")
            await self._cleanup_temp_backup(temp_backup_dir)
            
            logger.info("原子性更新完成")
            return "更新应用成功"
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"安全更新过程中发生错误: {e}")
            raise HTTPException(status_code=500, detail=f"安全更新失败: {str(e)}")

    async def _cleanup_temp_backup(self, temp_backup_dir: Path):
        """
        清理临时备份目录
        
        Args:
            temp_backup_dir: 临时备份目录
        """
        try:
            if temp_backup_dir.exists():
                shutil.rmtree(temp_backup_dir)
                logger.debug("临时备份目录已清理")
        except Exception as e:
            logger.warning(f"清理临时备份失败: {e}")

    async def _rollback_from_temp_backup(self, temp_backup_dir: Path):
        """
        从临时备份回滚
        
        Args:
            temp_backup_dir: 临时备份目录
        """
        try:
            if temp_backup_dir.exists():
                items_to_restore = ["backend", "frontend", "Dockerfile", "docker-compose.yml", "requirements.txt"]
                
                logger.info("开始从临时备份回滚...")
                for item in items_to_restore:
                    backup_source = temp_backup_dir / item
                    target = self.app_dir / item
                    
                    if backup_source.exists():
                        # 删除当前文件
                        if target.exists():
                            if target.is_file():
                                target.unlink()
                            else:
                                shutil.rmtree(target)
                        
                        # 恢复临时备份
                        if backup_source.is_file():
                            shutil.copy2(backup_source, target)
                        else:
                            shutil.copytree(backup_source, target, dirs_exist_ok=True)
                        logger.debug(f"已回滚: {item}")
                
                logger.info("回滚完成")
        except Exception as rollback_error:
            logger.error(f"回滚过程中发生错误: {rollback_error}")
            raise HTTPException(status_code=500, detail=f"回滚失败: {str(rollback_error)}")

    async def apply_update(self, source_dir: Path) -> str:
        """
        应用更新（兼容旧接口）
        
        Args:
            source_dir: 源目录
            
        Returns:
            str: 更新结果
        """
        return await self.apply_update_safely(source_dir)

    async def rollback(self, backup_path: str) -> str:
        """
        从压缩备份文件回滚（独立进程）
        
        Args:
            backup_path: 备份路径
            
        Returns:
            str: 回滚结果
        """
        # 启动独立进程
        process = multiprocessing.Process(
            target=_rollback_process,
            args=(backup_path, str(self.app_dir), str(self.temp_dir), str(self.backup_dir), None)
        )
        process.daemon = False
        process.start()

        # 短暂等待
        await asyncio.sleep(1)

        # 进程已快速完成，等待并返回结果
        if not process.is_alive():
            # 等待进程结束
            process.join(timeout=5)
            return "回滚已完成，正在刷新..."

        return "回滚已启动，正在后台独立执行..."

    async def cleanup_temp_files(self):
        """
        清理临时文件
        """
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info("临时文件清理完成")
            else:
                logger.debug("临时目录不存在，无需清理")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

    async def execute_update(self) -> dict:
        """
        执行完整更新流程（增强版）
        
        Returns:
            dict: 更新结果
        """
        update_start_time = datetime.now()
        temp_backup_path = None
        
        try:
            logger.info("=" * 60)
            logger.info("开始执行系统更新流程")
            logger.info("=" * 60)
            
            # 1. 检查更新
            logger.info("[步骤1/7] 检查更新...")
            check_result = await self.check_update()
            if not check_result["has_update"]:
                logger.info("系统已是最新版本")
                return {
                    "success": True,
                    "message": "已是最新版本",
                    "current_version": check_result["current_version"],
                    "duration": 0
                }

            latest_version = check_result["latest_version"]
            logger.info(f"发现新版本: {check_result['current_version']} -> {latest_version}")

            # 2. 备份当前版本
            logger.info("[步骤2/7] 创建备份...")
            backup_path = await self.backup_current_version()
            temp_backup_path = backup_path
            logger.info(f"备份完成: {backup_path}")

            # 3. 下载更新包
            logger.info("[步骤3/7] 下载更新包...")
            archive_path = await self.download_update(latest_version)
            logger.info(f"下载完成: {archive_path}")

            # 4. 解压更新包
            logger.info("[步骤4/7] 解压更新包...")
            source_dir = await self.extract_update(archive_path)
            logger.info(f"解压完成: {source_dir}")

            # 5. 验证更新文件
            logger.info("[步骤5/7] 验证更新文件...")
            if not await self.validate_update_files(source_dir):
                raise HTTPException(status_code=500, detail="更新文件验证失败")

            # 6. 应用更新
            logger.info("[步骤6/7] 应用更新...")
            await self.apply_update_safely(source_dir)
            logger.info("更新应用完成")

            # 7. 清理临时文件
            logger.info("[步骤7/7] 清理临时文件...")
            await self.cleanup_temp_files()
            logger.info("临时文件清理完成")

            update_duration = (datetime.now() - update_start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info("系统更新成功完成!")
            logger.info(f"从 v{check_result['current_version']} 更新到 v{latest_version}")
            logger.info(f"耗时: {update_duration:.2f} 秒")
            logger.info("=" * 60)

            return {
                "success": True,
                "message": f"更新成功，从 v{check_result['current_version']} 更新到 v{latest_version}",
                "current_version": latest_version,
                "duration": update_duration,
                "backup_path": temp_backup_path
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新过程中发生错误: {e}")
            # 清理临时文件
            try:
                await self.cleanup_temp_files()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")

    async def get_backups(self) -> list:
        """
        获取备份列表
        
        Returns:
            list: 备份列表
        """
        try:
            backups = []
            if self.backup_dir.exists():
                for backup_file in self.backup_dir.iterdir():
                    if backup_file.is_file() and backup_file.name.endswith('.tar.gz'):
                        # 解析备份文件名获取版本和时间
                        import re
                        match = re.search(r'backup_(.*?)_(\d{8}_\d{6})\.tar\.gz', backup_file.name)
                        if match:
                            version = match.group(1)
                            timestamp_str = match.group(2)
                            try:
                                timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                                backup_info = {
                                    "filename": backup_file.name,
                                    "path": str(backup_file),
                                    "version": version,
                                    "timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                    "size": backup_file.stat().st_size
                                }
                                backups.append(backup_info)
                            except Exception as e:
                                logger.warning(f"解析备份文件 {backup_file.name} 失败: {e}")
            
            # 按时间倒序排序
            backups.sort(key=lambda x: x['timestamp'], reverse=True)
            return backups
        except Exception as e:
            logger.error(f"获取备份列表失败: {e}")
            return []


def _rollback_process(backup_path, app_dir, temp_dir, backup_dir, logger):
    """
    回滚进程
    
    Args:
        backup_path: 备份路径
        app_dir: 应用目录
        temp_dir: 临时目录
        backup_dir: 备份目录
        logger: 日志记录器
    """
    try:
        rollback_logger.info(f"开始回滚进程，备份文件: {backup_path}")
        
        # 验证备份文件存在
        backup_path = Path(backup_path)
        if not backup_path.exists():
            rollback_logger.error(f"备份文件不存在: {backup_path}")
            return
        
        app_dir = Path(app_dir)
        temp_dir = Path(temp_dir)
        
        # 创建临时解压目录
        extract_dir = temp_dir / "rollback_extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        # 解压备份文件
        rollback_logger.info(f"解压备份文件: {backup_path}")
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(extract_dir)
        
        # 查找解压后的项目根目录
        extracted_items = list(extract_dir.iterdir())
        if not extracted_items:
            rollback_logger.error("解压后目录为空")
            return
        
        source_dir = extracted_items[0] if len(extracted_items) == 1 else extract_dir
        
        # 要回滚的文件和目录
        items_to_restore = ["backend", "frontend", "Dockerfile", "docker-compose.yml", "requirements.txt"]
        
        # 开始回滚
        rollback_logger.info("开始回滚文件...")
        for item in items_to_restore:
            source_item = source_dir / item
            target_item = app_dir / item
            
            if source_item.exists():
                try:
                    # 删除当前文件
                    if target_item.exists():
                        if target_item.is_file():
                            target_item.unlink()
                        else:
                            shutil.rmtree(target_item)
                    
                    # 恢复备份
                    if source_item.is_file():
                        shutil.copy2(source_item, target_item)
                    else:
                        shutil.copytree(source_item, target_item, dirs_exist_ok=True)
                    rollback_logger.info(f"已回滚: {item}")
                except Exception as e:
                    rollback_logger.error(f"回滚 {item} 失败: {e}")
        
        # 清理临时目录
        shutil.rmtree(extract_dir)
        rollback_logger.info("回滚完成")
        
    except Exception as e:
        rollback_logger.error(f"回滚过程中发生错误: {e}")
