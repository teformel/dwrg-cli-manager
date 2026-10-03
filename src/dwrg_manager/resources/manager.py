"""
资源管理器

作为资源领域的唯一对外入口，``ResourceManager`` 只负责「装配」：
选择服务器、获取清单、调用 :class:`~dwrg_manager.resources.validator.Validator`
做文件体检、调用 :class:`~dwrg_manager.resources.patcher.Patcher` 做增量更新，
并对外暴露缓存统计与清理。真正的下载/校验/比对逻辑分别位于
``downloader`` / ``validator`` / ``patcher`` 三个子模块。
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

from ..config.manager import ConfigManager
from ..utils.logger import get_logger
from .downloader import Downloader
from .models import (
    ManifestTransport,
    PatchPlan,
    ResourceCheckResult,
    ResourceFile,
    ResourceManifest,
    ResourceServer,
    ResourceUpdateResult,
)
from .patcher import Patcher
from .validator import Validator

logger = get_logger(__name__)


class AiohttpManifestTransport:
    """基于 aiohttp 的默认清单提供者。"""

    def __init__(self, timeout: int = 30) -> None:
        """初始化传输层。

        Args:
            timeout: 获取清单的请求总超时（秒）。
        """
        self._timeout = timeout

    async def fetch_manifest(self, server: ResourceServer) -> ResourceManifest | None:
        """从服务器的 ``manifest.json`` 拉取并解析清单。

        Args:
            server: 目标资源服务器。

        Returns:
            解析成功返回 :class:`ResourceManifest`，失败返回 ``None``。
        """
        url = f"{server.base_url.rstrip('/')}/manifest.json"
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error("获取清单失败: HTTP %s (%s)", response.status, url)
                        return None
                    data = await response.json()
        except Exception as exc:  # noqa: BLE001 - 网络边界，统一降级为 None
            logger.error("获取清单异常: %s (%s)", exc, url)
            return None
        try:
            return ResourceManifest(**data)
        except ValueError as exc:
            logger.error("解析清单失败: %s", exc)
            return None


class ResourceManager:
    """资源管理器，编排校验 / 下载 / 补丁三个子模块。"""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        *,
        transport: ManifestTransport | None = None,
    ) -> None:
        """初始化资源管理器。

        Args:
            config_manager: 配置管理器；缺省使用默认配置。传入的配置决定
                ``data_dir`` / ``cache_dir`` / 并发数 / 超时等。
            transport: 清单提供者；缺省走 aiohttp，测试可注入假实现。

        Example:
            >>> manager = ResourceManager(ConfigManager("/tmp/c.yaml"))
            >>> isinstance(manager.get_cache_info()["cache_size"], int)
            True
        """
        self.config_manager = config_manager or ConfigManager()
        app_config = self.config_manager.get_app_config()

        self.data_dir = Path(app_config.data_dir).expanduser()
        self.cache_dir = Path(app_config.cache_dir).expanduser()
        self.game_dir = self.data_dir / "game"
        for directory in (self.data_dir, self.cache_dir, self.game_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self.resource_servers = self._init_resource_servers()
        self.validator = Validator()
        self.downloader = Downloader(
            concurrency=app_config.max_concurrent_downloads,
            timeout=app_config.download_timeout,
        )
        self.patcher = Patcher(
            manifest_path=self.data_dir / "manifest.json",
            game_dir=self.game_dir,
            validator=self.validator,
        )
        self.transport = transport or AiohttpManifestTransport()

    def _init_resource_servers(self) -> list[ResourceServer]:
        """初始化内置资源服务器列表。

        Returns:
            主用与备用两个 :class:`ResourceServer`。
        """
        return [
            ResourceServer(
                name="official",
                endpoint="https://resources.identityv.com",
                base_url="https://resources.identityv.com/v1",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_available=True,
            ),
            ResourceServer(
                name="backup",
                endpoint="https://backup.resources.identityv.com",
                base_url="https://backup.resources.identityv.com/v1",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_available=True,
            ),
        ]

    def _select_server(self, server: str | None) -> ResourceServer | None:
        """按名称选择资源服务器。

        Args:
            server: 服务器名称；``None`` 表示使用第一个（主用）服务器。

        Returns:
            匹配的 :class:`ResourceServer`；未找到返回 ``None``。
        """
        if server is None:
            return self.resource_servers[0] if self.resource_servers else None
        for candidate in self.resource_servers:
            if candidate.name == server:
                return candidate
        logger.error("服务器不存在: %s", server)
        return None

    async def _get_manifest(self, server: str | None = None) -> ResourceManifest | None:
        """获取资源清单（含服务器选择与异常降级）。

        Args:
            server: 服务器名称。

        Returns:
            清单；无法获取时返回 ``None``。
        """
        selected = self._select_server(server)
        if selected is None:
            return None
        try:
            return await self.transport.fetch_manifest(selected)
        except Exception as exc:  # noqa: BLE001 - 传输层异常统一降级为 None
            logger.error("获取资源清单异常: %s", exc)
            return None

    def _verify_file(self, file_info: ResourceFile, path: Path) -> bool:
        """校验单个已在磁盘上的文件。

        仅当清单提供了 ``partial_hash`` 时才先做抽样快检；抽样未通过或无抽样
        哈希字段时，回退到全量校验。

        Args:
            file_info: 清单中的文件信息。
            path: 实际文件路径。

        Returns:
            文件完整有效返回 ``True``。
        """
        if not path.exists():
            return False
        if file_info.partial_hash and self.validator.quick_check(
            path, file_info.size, file_info.partial_hash
        ):
            return True
        return self.validator.verify(
            path, size=file_info.size, md5=file_info.md5, sha256=file_info.sha256
        )

    async def check_resources(self, server: str | None = None) -> ResourceCheckResult:
        """检查游戏资源完整性。

        Args:
            server: 服务器名称；``None`` 使用主用服务器。

        Returns:
            :class:`ResourceCheckResult`。清单拉取失败时返回全 0 结果并记录错误日志。
        """
        logger.info("开始检查游戏资源...")
        manifest = await self._get_manifest(server)
        if manifest is None:
            logger.error("资源检查失败：无法获取资源清单")
            return ResourceCheckResult(
                total_files=0,
                healthy_files=0,
                corrupted_files=0,
                missing_files=0,
                outdated_files=0,
                scan_time=datetime.now(),
            )

        healthy = corrupted = missing = 0
        for file_info in manifest.files:
            path = self.game_dir / file_info.path
            if not path.exists():
                missing += 1
            elif self._verify_file(file_info, path):
                healthy += 1
            else:
                corrupted += 1

        result = ResourceCheckResult(
            total_files=len(manifest.files),
            healthy_files=healthy,
            corrupted_files=corrupted,
            missing_files=missing,
            outdated_files=0,
            scan_time=datetime.now(),
        )
        logger.info("资源检查完成: %s", result)
        return result

    async def update_resources(
        self, server: str | None = None, force: bool = False
    ) -> ResourceUpdateResult:
        """更新游戏资源。

        Args:
            server: 服务器名称；``None`` 使用主用服务器。
            force: 为 ``True`` 时忽略「版本未变」短路，改为按磁盘现状做修复式更新
                （重新下载缺失/损坏文件）。

        Returns:
            :class:`ResourceUpdateResult`。清单拉取失败时 ``success=False`` 且
            ``error`` 明确指明失败原因，调用方据此可与「无更新」区分。
        """
        logger.info("开始更新游戏资源...")
        start_time = datetime.now()

        manifest = await self._get_manifest(server)
        if manifest is None:
            message = "无法获取资源清单"
            if server:
                message = f"{message}（服务器: {server}）"
            logger.error(message)
            return ResourceUpdateResult(
                success=False,
                downloaded_files=0,
                updated_files=0,
                failed_files=[],
                error=message,
                total_size=0,
                elapsed_time=0.0,
                scan_time=datetime.now(),
            )

        local_manifest = self.patcher.load_manifest()
        if (
            not force
            and local_manifest is not None
            and local_manifest.version == manifest.version
        ):
            logger.info("资源已是最新版本: %s", manifest.version)
            return ResourceUpdateResult(
                success=True,
                downloaded_files=0,
                updated_files=0,
                failed_files=[],
                error=None,
                total_size=0,
                elapsed_time=0.0,
                scan_time=datetime.now(),
            )

        if force:
            plan = self._build_repair_plan(manifest, local_manifest)
        else:
            plan = self.patcher.plan(local_manifest, manifest)

        patch_result = await self.patcher.apply(plan, self.downloader)

        download_files = plan.files_to_download()
        total_size = sum(
            file_info.size
            for file_info, result in zip(
                download_files, patch_result.results, strict=True
            )
            if result.success
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        result = ResourceUpdateResult(
            success=patch_result.success,
            downloaded_files=patch_result.added + patch_result.updated,
            updated_files=patch_result.updated,
            failed_files=patch_result.failed_files,
            error=patch_result.error,
            total_size=total_size,
            elapsed_time=elapsed,
            scan_time=datetime.now(),
        )
        logger.info("资源更新完成: %s", result)
        return result

    def _build_repair_plan(
        self, remote_manifest: ResourceManifest, local_manifest: ResourceManifest | None
    ) -> PatchPlan:
        """按磁盘现状构建修复计划（``force=True`` 时使用）。

        与基于清单的增量不同，这里直接以文件系统为准：缺失或校验不通过的文件
        进入 ``added`` / ``updated``（都会触发下载），其余为 ``unchanged``。

        Args:
            remote_manifest: 远端目标清单。
            local_manifest: 本地清单，用于识别需要删除的多余文件。

        Returns:
            修复用的 :class:`PatchPlan`。
        """
        remote_paths = {file_info.path for file_info in remote_manifest.files}
        added: list[ResourceFile] = []
        updated: list[ResourceFile] = []
        unchanged: list[ResourceFile] = []
        for file_info in remote_manifest.files:
            path = self.game_dir / file_info.path
            if not path.exists():
                added.append(file_info)
            elif self._verify_file(file_info, path):
                unchanged.append(file_info)
            else:
                updated.append(file_info)
        removed = [
            file_info
            for file_info in (local_manifest.files if local_manifest else [])
            if file_info.path not in remote_paths
        ]
        return PatchPlan(
            download_url=remote_manifest.download_url,
            remote_manifest=remote_manifest,
            added=added,
            updated=updated,
            removed=removed,
            unchanged=unchanged,
        )

    def clean_cache(self, all_files: bool = False) -> bool:
        """清理缓存。

        Args:
            all_files: 为 ``True`` 时清空整个缓存目录；否则只删除 ``.tmp`` /
                ``.part`` 临时文件。

        Returns:
            清理成功返回 ``True``，失败返回 ``False``。
        """
        try:
            if all_files:
                if self.cache_dir.exists():
                    shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("已清理全部缓存: %s", self.cache_dir)
            else:
                removed = 0
                for directory in (self.cache_dir, self.game_dir):
                    if not directory.exists():
                        continue
                    for pattern in ("*.tmp", "*.part"):
                        for temp_file in directory.rglob(pattern):
                            temp_file.unlink(missing_ok=True)
                            removed += 1
                logger.info("已清理临时文件: %d 个", removed)
            return True
        except OSError as exc:
            logger.error("清理缓存失败: %s", exc)
            return False

    def get_cache_info(self) -> dict[str, Any]:
        """获取缓存与游戏资源目录统计。

        Returns:
            包含 ``cache_size`` / ``game_size``（原始字节）、``cache_size_human``
            / ``game_size_human``（人类可读）、``cache_files`` / ``game_files``
            / ``cache_dir`` / ``game_dir`` 的字典；读取异常时返回 ``{}``。
        """
        try:
            cache_size, cache_files = self._dir_stats(self.cache_dir)
            game_size, game_files = self._dir_stats(self.game_dir)
            return {
                "cache_size": cache_size,
                "cache_files": cache_files,
                "game_size": game_size,
                "game_files": game_files,
                "cache_dir": str(self.cache_dir),
                "game_dir": str(self.game_dir),
                "cache_size_human": self.validator.human_size(cache_size),
                "game_size_human": self.validator.human_size(game_size),
            }
        except OSError as exc:
            logger.error("获取缓存信息失败: %s", exc)
            return {}

    @staticmethod
    def _dir_stats(directory: Path) -> tuple[int, int]:
        """递归统计目录内文件的总大小与数量。

        Args:
            directory: 目标目录。

        Returns:
            ``(总字节数, 文件数)``；目录不存在时返回 ``(0, 0)``。
        """
        if not directory.exists():
            return 0, 0
        total = 0
        count = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
                count += 1
        return total, count
