"""
资源管理器

作为资源领域的唯一对外入口，``ResourceManager`` 只负责「装配」：
选择资源源、获取清单、调用 :class:`~dwrg_manager.resources.validator.Validator`
做文件体检、调用 :class:`~dwrg_manager.resources.patcher.Patcher` 做增量更新，
并对外暴露缓存统计与清理。真正的下载/校验/比对逻辑分别位于
``downloader`` / ``validator`` / ``patcher`` 三个子模块。

资源源不再内置任何编造域名，全部来自 ``AppConfig.resource_sources``
（默认预置两条已实测的国际服直链），因此用户可自行覆盖；国服 PC 端
公开直链已关闭，只能通过 ``--dir`` 指定本地已安装目录走
:class:`~dwrg_manager.resources.transports.LocalIndexTransport`。
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

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
from .transports import HttpIndexTransport, LocalIndexTransport
from .validator import Validator

logger = get_logger(__name__)

#: 清单来源模式：``auto``（本地清单优先，其次 HTTP 索引）、``local``、``http``。
SOURCE_MODES: tuple[str, ...] = ("auto", "local", "http")

#: 本地清单被视为「未过期」的最大时长（秒）；超过该时长后 ``auto`` 模式
#: 会重新走 HTTP 索引刷新。
DEFAULT_MANIFEST_TTL_SECONDS = 24 * 60 * 60


class ResourceManager:
    """资源管理器，编排校验 / 下载 / 补丁三个子模块。"""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        *,
        transport: ManifestTransport | None = None,
        source: str = "auto",
        game_dir: Path | str | None = None,
    ) -> None:
        """初始化资源管理器。

        Args:
            config_manager: 配置管理器；缺省使用默认配置。传入的配置决定
                ``data_dir`` / ``cache_dir`` / 并发数 / 超时等。
            transport: 清单提供者；缺省按 ``source`` 自动选择，测试可注入假实现。
                一旦显式传入，``source`` 与自动选择逻辑都不再生效。
            source: 清单来源模式，取值见 :data:`SOURCE_MODES`；``auto`` 表示
                「本地清单优先（存在且未过期），其次 HTTP 索引」。
            game_dir: 显式指定游戏目录；``None`` 时依次取 ``app.game_path``
                与 ``data_dir/game``。

        Example:
            >>> manager = ResourceManager(ConfigManager("/tmp/c.yaml"))
            >>> isinstance(manager.get_cache_info()["cache_size"], int)
            True
        """
        self.config_manager = config_manager or ConfigManager()
        app_config = self.config_manager.get_app_config()

        self.data_dir = Path(app_config.data_dir).expanduser()
        self.cache_dir = Path(app_config.cache_dir).expanduser()
        self.game_dir = self._resolve_game_dir(app_config, game_dir)
        for directory in (self.data_dir, self.cache_dir, self.game_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self.source = source if source in SOURCE_MODES else "auto"
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
        self._injected_transport = transport
        self.transport: ManifestTransport | None = None

    @staticmethod
    def _resolve_game_dir(app_config: Any, override: Path | str | None) -> Path:
        """解析实际使用的游戏目录。

        优先级：显式参数 ``override`` → ``app.game_path`` → ``data_dir/game``。

        Args:
            app_config: 应用级配置对象。
            override: 显式指定的游戏目录；``None`` 表示不覆盖。

        Returns:
            展开用户目录后的绝对路径。
        """
        if override:
            return Path(override).expanduser()
        configured = str(getattr(app_config, "game_path", "") or "").strip()
        if configured:
            return Path(configured).expanduser()
        return Path(app_config.data_dir).expanduser() / "game"

    def _init_resource_servers(self) -> list[ResourceServer]:
        """从配置构造资源服务器（即资源源）列表。

        不再内置任何编造域名；每个条目对应 ``AppConfig.resource_sources``
        中的一条配置，名称与渠道均可由用户覆盖。

        Returns:
            来自配置的 :class:`ResourceServer` 列表；配置为空时返回空列表。
        """
        app_config = self.config_manager.get_app_config()
        servers: list[ResourceServer] = []
        for source_config in app_config.resource_sources:
            servers.append(
                ResourceServer(
                    name=source_config.name,
                    endpoint=source_config.url,
                    base_url=source_config.url.rsplit("/", 1)[0],
                    current_version=source_config.description or source_config.name,
                    latest_version=source_config.description or source_config.name,
                    is_available=source_config.is_available,
                )
            )
        return servers

    def _select_server(self, server: str | None) -> ResourceServer | None:
        """按名称选择资源服务器（即资源源）。

        Args:
            server: 资源源名称；``None`` 表示使用第一个可用源。

        Returns:
            匹配的 :class:`ResourceServer`；未找到返回 ``None``。
        """
        if server is None:
            for candidate in self.resource_servers:
                if candidate.is_available:
                    return candidate
            return None
        for candidate in self.resource_servers:
            if candidate.name == server:
                return candidate
        logger.error("资源源不存在: %s", server)
        return None

    def _build_transport(self) -> ManifestTransport:
        """按来源模式构造默认传输层。

        Returns:
            ``local`` 模式返回 :class:`LocalIndexTransport`；
            其余返回 :class:`HttpIndexTransport`。
        """
        if self.source == "local":
            return LocalIndexTransport(directory=self.game_dir)
        return HttpIndexTransport(
            sources=self.config_manager.get_app_config().resource_sources,
            timeout=self.config_manager.get_app_config().download_timeout,
        )

    def _get_transport(self) -> ManifestTransport:
        """返回当前生效的传输层（懒构造并缓存）。

        Returns:
            测试注入的替身，或按 ``source`` 构造的默认实现。
        """
        if self._injected_transport is not None:
            return self._injected_transport
        if self.transport is None:
            self.transport = self._build_transport()
        return self.transport

    def _is_local_manifest_fresh(self) -> bool:
        """判断本地清单文件是否存在且未过期。

        Returns:
            清单存在且修改时间在 :data:`DEFAULT_MANIFEST_TTL_SECONDS` 之内时
            返回 ``True``。
        """
        manifest_path = self.patcher.manifest_path
        try:
            if not manifest_path.is_file():
                return False
            age = datetime.now().timestamp() - manifest_path.stat().st_mtime
        except OSError as exc:
            logger.warning("读取本地清单时间失败: %s (%s)", manifest_path, exc)
            return False
        return age < DEFAULT_MANIFEST_TTL_SECONDS

    def _load_local_manifest(self) -> ResourceManifest | None:
        """读取本地已记录的清单。

        Returns:
            解析成功返回 :class:`ResourceManifest`；不存在或损坏返回 ``None``。
        """
        return self.patcher.load_manifest()

    async def _get_manifest(self, server: str | None = None) -> ResourceManifest | None:
        """获取资源清单（含来源模式、服务器选择与异常降级）。

        ``auto`` 模式的优先级：

        1. 注入的 ``transport``（测试替身，行为与旧版完全一致）；
        2. 本地清单（``data_dir/manifest.json`` 存在且未过期）；
        3. HTTP 索引（对配置的资源源发 ``HEAD``）。

        Args:
            server: 资源源名称。

        Returns:
            清单；无法获取时返回 ``None``。
        """
        selected = self._select_server(server)
        if selected is None:
            return None

        if self._injected_transport is None:
            if self.source == "local":
                return await self._get_transport().fetch_manifest(selected)
            if self.source == "auto" and self._is_local_manifest_fresh():
                local_manifest = self._load_local_manifest()
                if local_manifest is not None:
                    logger.info("使用本地清单: %s", self.patcher.manifest_path)
                    return local_manifest
                logger.info("本地清单损坏，回落到 HTTP 索引")

        try:
            return await self._get_transport().fetch_manifest(selected)
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
            server: 资源源名称；``None`` 使用第一个可用源。

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
            server: 资源源名称；``None`` 使用第一个可用源。
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
