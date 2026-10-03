"""
资源管理器
"""

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path

import aiohttp

from ..config.manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.system import SystemManager
from .models import (
    ResourceCheckResult,
    ResourceFile,
    ResourceManifest,
    ResourceServer,
    ResourceUpdateResult,
)

logger = get_logger(__name__)


class ResourceManager:
    """资源管理器"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.system_manager = SystemManager()
        self.data_dir = Path.home() / '.dwrg' / 'data'
        self.cache_dir = Path.home() / '.dwrg' / 'cache'
        self.game_dir = Path.home() / '.dwrg' / 'game'

        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.game_dir.mkdir(parents=True, exist_ok=True)

        # 资源服务器
        self.resource_servers = self._init_resource_servers()

        # 并发控制
        self.semaphore = asyncio.Semaphore(
            self.config_manager.get_app_config().max_concurrent_downloads
        )

    def _init_resource_servers(self) -> list[ResourceServer]:
        """初始化资源服务器"""
        servers = [
            ResourceServer(
                name="official",
                endpoint="https://resources.identityv.com",
                base_url="https://resources.identityv.com/v1",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_available=True
            ),
            ResourceServer(
                name="backup",
                endpoint="https://backup.resources.identityv.com",
                base_url="https://backup.resources.identityv.com/v1",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_available=True
            )
        ]
        return servers

    async def check_resources(self, server: str | None = None) -> ResourceCheckResult:
        """检查游戏资源"""
        logger.info("开始检查游戏资源...")

        try:
            # 获取资源清单
            manifest = await self._get_manifest(server)
            if not manifest:
                return ResourceCheckResult(
                    total_files=0,
                    healthy_files=0,
                    corrupted_files=0,
                    missing_files=0,
                    scan_time=datetime.now()
                )

            # 扫描文件
            total_files = len(manifest.files)
            healthy_files = 0
            corrupted_files = 0
            missing_files = 0

            for file_info in manifest.files:
                file_path = self.game_dir / file_info.path

                if not file_path.exists():
                    missing_files += 1
                    continue

                # 检查文件大小
                actual_size = file_path.stat().st_size
                if actual_size != file_info.size:
                    corrupted_files += 1
                    continue

                # 检查MD5
                actual_md5 = await self._calculate_md5(file_path)
                if actual_md5 != file_info.md5:
                    corrupted_files += 1
                    continue

                healthy_files += 1

            result = ResourceCheckResult(
                total_files=total_files,
                healthy_files=healthy_files,
                corrupted_files=corrupted_files,
                missing_files=missing_files,
                scan_time=datetime.now()
            )

            logger.info(f"资源检查完成: {result}")
            return result

        except Exception as e:
            logger.error(f"检查资源失败: {e}")
            raise

    async def update_resources(self, server: str | None = None, force: bool = False) -> ResourceUpdateResult:
        """更新游戏资源"""
        logger.info("开始更新游戏资源...")

        try:
            start_time = datetime.now()

            # 获取资源清单
            manifest = await self._get_manifest(server)
            if not manifest:
                return ResourceUpdateResult(
                    success=False,
                    error="无法获取资源清单",
                    scan_time=datetime.now()
                )

            # 检查是否需要更新
            if not force and await self._is_up_to_date(manifest):
                logger.info("资源已是最新版本")
                return ResourceUpdateResult(
                    success=True,
                    downloaded_files=0,
                    updated_files=0,
                    scan_time=datetime.now()
                )

            # 下载资源
            downloaded_files = 0
            updated_files = 0
            failed_files = []
            total_size = 0

            # 创建下载任务
            tasks = []
            for file_info in manifest.files:
                task = self._download_file(file_info)
                tasks.append(task)

            # 并发下载
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_files.append(manifest.files[i].name)
                    logger.error(f"下载失败: {manifest.files[i].name} - {result}")
                else:
                    if result:
                        downloaded_files += 1
                        updated_files += 1
                    total_size += manifest.files[i].size

            elapsed_time = (datetime.now() - start_time).total_seconds()

            result = ResourceUpdateResult(
                success=len(failed_files) == 0,
                downloaded_files=downloaded_files,
                updated_files=updated_files,
                failed_files=failed_files,
                total_size=total_size,
                elapsed_time=elapsed_time,
                scan_time=datetime.now()
            )

            logger.info(f"资源更新完成: {result}")
            return result

        except Exception as e:
            logger.error(f"更新资源失败: {e}")
            return ResourceUpdateResult(
                success=False,
                error=str(e),
                scan_time=datetime.now()
            )

    async def _get_manifest(self, server: str | None = None) -> ResourceManifest | None:
        """获取资源清单"""
        try:
            # 选择服务器
            if server:
                srv = next((s for s in self.resource_servers if s.name == server), None)
                if not srv:
                    logger.error(f"服务器不存在: {server}")
                    return None
            else:
                srv = self.resource_servers[0]

            # 获取清单
            url = f"{srv.base_url}/manifest.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ResourceManifest(**data)
                    else:
                        logger.error(f"获取清单失败: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"获取资源清单失败: {e}")
            return None

    async def _is_up_to_date(self, manifest: ResourceManifest) -> bool:
        """检查资源是否已更新"""
        try:
            # 检查本地清单
            local_manifest_path = self.data_dir / 'manifest.json'
            if local_manifest_path.exists():
                with open(local_manifest_path, encoding='utf-8') as f:
                    local_data = json.load(f)
                    local_manifest = ResourceManifest(**local_data)
                    return local_manifest.version == manifest.version

            return False

        except Exception as e:
            logger.error(f"检查更新状态失败: {e}")
            return False

    async def _download_file(self, file_info: ResourceFile) -> bool:
        """下载单个文件"""
        async with self.semaphore:
            try:
                file_path = self.game_dir / file_info.path

                # 创建目录
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # 检查文件是否已存在且正确
                if file_path.exists():
                    actual_size = file_path.stat().st_size
                    if actual_size == file_info.size:
                        # 快速验证MD5
                        if await self._quick_md5_check(file_path, file_info.md5):
                            return False  # 文件已存在且正确

                # 下载文件
                url = f"{self.resource_servers[0].base_url}/files/{file_info.name}"

                # 使用临时文件
                temp_path = file_path.with_suffix(file_path.suffix + '.tmp')

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            # 下载到临时文件
                            with open(temp_path, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    f.write(chunk)

                            # 验证下载的文件
                            if await self._verify_downloaded_file(temp_path, file_info):
                                # 重命名为正式文件
                                temp_path.replace(file_path)
                                return True
                            else:
                                # 删除无效的临时文件
                                temp_path.unlink(missing_ok=True)
                                return False
                        else:
                            logger.error(f"下载失败: {file_info.name} - {response.status}")
                            return False

            except Exception as e:
                logger.error(f"下载文件失败: {file_info.name} - {e}")
                return False

    async def _calculate_md5(self, file_path: Path) -> str:
        """计算文件的MD5值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def _quick_md5_check(self, file_path: Path, expected_md5: str) -> bool:
        """快速MD5检查"""
        try:
            # 只检查文件开头和结尾的MD5
            hash_md5 = hashlib.md5()

            # 读取开头1KB
            with open(file_path, "rb") as f:
                hash_md5.update(f.read(1024))

            # 读取结尾1KB
            file_size = file_path.stat().st_size
            if file_size > 1024:
                with open(file_path, "rb") as f:
                    f.seek(file_size - 1024)
                    hash_md5.update(f.read(1024))

            return hash_md5.hexdigest() == expected_md5

        except:
            return False

    async def _verify_downloaded_file(self, temp_path: Path, file_info: ResourceFile) -> bool:
        """验证下载的文件"""
        try:
            # 检查文件大小
            actual_size = temp_path.stat().st_size
            if actual_size != file_info.size:
                return False

            # 检查MD5
            actual_md5 = await self._calculate_md5(temp_path)
            return actual_md5 == file_info.md5

        except Exception as e:
            logger.error(f"验证文件失败: {file_info.name} - {e}")
            return False

    def clean_cache(self, all: bool = False) -> bool:
        """清理缓存"""
        try:
            if all:
                # 删除整个缓存目录
                import shutil
                if self.cache_dir.exists():
                    shutil.rmtree(self.cache_dir)
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("清理所有缓存")
            else:
                # 删除临时文件
                for temp_file in self.game_dir.glob('*.tmp'):
                    temp_file.unlink(missing_ok=True)
                logger.info("清理临时文件")

            return True

        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            return False

    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        try:
            cache_size = 0
            file_count = 0

            if self.cache_dir.exists():
                for file_path in self.cache_dir.rglob('*'):
                    if file_path.is_file():
                        cache_size += file_path.stat().st_size
                        file_count += 1

            game_size = 0
            game_file_count = 0

            if self.game_dir.exists():
                for file_path in self.game_dir.rglob('*'):
                    if file_path.is_file():
                        game_size += file_path.stat().st_size
                        game_file_count += 1

            return {
                'cache_size': cache_size,
                'cache_files': file_count,
                'game_size': game_size,
                'game_files': game_file_count,
                'cache_dir': str(self.cache_dir),
                'game_dir': str(self.game_dir)
            }

        except Exception as e:
            logger.error(f"获取缓存信息失败: {e}")
            return {}
