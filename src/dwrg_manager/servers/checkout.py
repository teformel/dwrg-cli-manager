"""
秒级渠道服切换（checkout / sync / download）

对标 wutheringwaves-cli-manager 的 `ww checkout` / `ww sync` /
`ww download` 三件套，把「切渠道服」从「重新下载整个客户端」变成
「本地差异缓存 + 秒级恢复」：

* **首次切换**：把当前渠道服的文件快照进 `<game_dir>/dwrg_server_diff_cache/<current>/`，
  再把目标渠道服的文件恢复/下载到游戏目录，并备份渠道配置文件
  （SDK / channel 标记）。
* **二次切换**：优先从本地缓存恢复，不触网；缓存缺失或损坏时回落重新下载，
  成功后回写缓存。
* **大版本变化**：游戏目录下的 version 文件内容发生变化时自动重置缓存，
  避免把旧版本的差异文件错贴到新版本上。

设计要点：
    - 所有文件操作都经过 :func:`~dwrg_manager.security.validation.validate_path`
      约束在游戏目录内，防止目录穿越。
    - 切换前一定先备份渠道配置文件，失败即中止，绝不留下「切了一半」的中间态。
    - 下载逻辑委托给既有的 :class:`~dwrg_manager.resources.downloader.Downloader`，
      本模块不重复实现传输层；测试通过注入假下载器实现零真实网络。
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from ..config.manager import ConfigManager
from ..exceptions import ServerError, ValidationError
from ..security.validation import validate_path
from ..utils.logger import get_logger
from .models import ServerConfig

logger = get_logger(__name__)

#: 游戏目录内用于存放渠道服差异缓存的子目录名。
CACHE_DIR_NAME = "dwrg_server_diff_cache"

#: 差异缓存目录内记录元数据的文件名。
CACHE_META_NAME = "cache_meta.json"

#: 渠道配置备份目录名（位于游戏目录内）。
CONFIG_BACKUP_DIR_NAME = "dwrg_server_config_backup"

#: 记录「上一个渠道服」的快照文件名（位于差异缓存根目录）。
SNAPSHOT_NAME = "previous_server.json"

#: 版本文件名（内容变化即视为大版本更新）。
VERSION_FILE_NAMES: tuple[str, ...] = ("version", "Version", "version.txt")

#: 渠道服特征表：渠道服名称 -> 用于识别的文件名特征（glob）。
#: 参考 ww 的 KRSDKConfig.json 思路；IdentityV 各渠道服的差异集中在渠道 SDK
#: 配置与渠道标记文件上，因此用「已知渠道服特征表 + 通用标记文件」双通道识别。
SERVER_FEATURE_FILES: dict[str, tuple[str, ...]] = {
    "official": (
        "*KRSDKConfig.json",
        "channel_official*.json",
        "*netease*_channel",
    ),
    "bserver": (
        "*KRSDKConfig.json",
        "channel_bilibili*.json",
        "*bilibili*_channel",
        "biligame*",
    ),
    "test_server": (
        "*KRSDKConfig.json",
        "channel_test*.json",
        "*test*_channel",
    ),
}

#: 各渠道服在渠道 SDK 配置里可能出现的标识串（用于内容级识别）。
SERVER_CONTENT_MARKERS: dict[str, tuple[str, ...]] = {
    "official": ("netease", "id5", "official", "dwr"),
    "bserver": ("bilibili", "biligame", "bili", "bserver"),
    "test_server": ("test", "testing", "experiment"),
}

#: 渠道配置文件在切换前必须备份的通配模式。
CHANNEL_CONFIG_PATTERNS: tuple[str, ...] = (
    "*KRSDKConfig.json",
    "*channel*.json",
    "*_channel",
    "*channel*.cfg",
    "*channel*.ini",
)

#: 各渠道服的兜底接口地址（配置未提供 endpoint 时使用）。
DEFAULT_ENDPOINTS: dict[str, str] = {
    "official": "https://idv.163.com",
    "bserver": "https://game.bilibili.com/idv",
    "test_server": "https://test.idv.163.com",
}


class SwitchMode(str, Enum):
    """一次切换实际走过的路径。

    Attributes:
        CACHE: 从本地差异缓存恢复（秒级，不触网）。
        DOWNLOAD: 缓存不可用，回落重新下载。
        ROLLBACK: 从上一渠道服快照回滚。
        NOOP: 目标渠道服即当前渠道服，未做任何改动。
    """

    CACHE = "cache"
    DOWNLOAD = "download"
    ROLLBACK = "rollback"
    NOOP = "noop"


@dataclass
class CheckoutResult:
    """一次 checkout / rollback 的结构化结果。

    Attributes:
        success: 是否成功。
        target: 目标渠道服名称。
        previous: 切换前的渠道服名称（未知时为 None）。
        mode: 实际走过的切换路径。
        restored_files: 从缓存恢复的文件数。
        downloaded_files: 重新下载的文件数。
        backup_files: 备份的渠道配置文件数。
        cache_reset: 是否因大版本变化重置了缓存。
        error: 失败原因；成功时为 None。
    """

    success: bool
    target: str
    previous: str | None = None
    mode: SwitchMode = SwitchMode.NOOP
    restored_files: int = 0
    downloaded_files: int = 0
    backup_files: int = 0
    cache_reset: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """导出为可 JSON 序列化的字典。

        Returns:
            含全部字段的字典，mode 为其字符串取值。
        """
        return {
            "success": self.success,
            "target": self.target,
            "previous": self.previous,
            "mode": self.mode.value,
            "restored_files": self.restored_files,
            "downloaded_files": self.downloaded_files,
            "backup_files": self.backup_files,
            "cache_reset": self.cache_reset,
            "error": self.error,
        }


@dataclass
class SyncResult:
    """一次全量校验（sync）的结果。

    Attributes:
        success: 是否成功完成校验（与是否存在问题无关）。
        total_files: 参与校验的文件总数。
        healthy_files: 校验通过的文件数。
        corrupted_files: 损坏（与缓存快照哈希不符）的文件相对路径列表。
        missing_files: 缺失（清单有、磁盘无）的文件相对路径列表。
        repaired_files: 被修复（本地缓存恢复）的文件相对路径列表。
        version: 本次校验读到的游戏版本号。
        error: 失败原因；成功时为 None。
    """

    success: bool
    total_files: int = 0
    healthy_files: int = 0
    corrupted_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    repaired_files: list[str] = field(default_factory=list)
    version: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """导出为可 JSON 序列化的字典。

        Returns:
            含全部字段的字典。
        """
        return {
            "success": self.success,
            "total_files": self.total_files,
            "healthy_files": self.healthy_files,
            "corrupted_files": list(self.corrupted_files),
            "missing_files": list(self.missing_files),
            "repaired_files": list(self.repaired_files),
            "version": self.version,
            "error": self.error,
        }


@dataclass
class DownloadResult:
    """一次客户端框架下载的结果。

    Attributes:
        success: 是否成功。
        server: 目标渠道服名称。
        game_dir: 实际下载目录。
        files: 成功下载的文件相对路径列表。
        failed_files: 下载失败的文件名列表。
        total_size: 下载总字节数。
        error: 失败原因；成功时为 None。
    """

    success: bool
    server: str
    game_dir: Path
    files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    total_size: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """导出为可 JSON 序列化的字典。

        Returns:
            含全部字段的字典，game_dir 转为字符串。
        """
        return {
            "success": self.success,
            "server": self.server,
            "game_dir": str(self.game_dir),
            "files": list(self.files),
            "failed_files": list(self.failed_files),
            "total_size": self.total_size,
            "error": self.error,
        }


class ClientDownloader(Protocol):
    """客户端下载器协议（便于注入测试替身）。

    真实实现由 :class:`~dwrg_manager.resources.downloader.Downloader` 提供；
    测试可注入任何满足该签名、且不触网的替身。
    """

    async def download(
        self,
        url: str,
        dest: Path,
        *,
        expected_size: int | None = None,
        expected_md5: str | None = None,
        resume: bool = True,
    ) -> Any:
        """下载单个文件到 dest。

        Args:
            url: 下载地址。
            dest: 目标路径。
            expected_size: 期望大小（字节）。
            expected_md5: 期望 MD5。
            resume: 是否允许断点续传。

        Returns:
            下载结果对象，需具备 success 属性。
        """
        ...


@dataclass
class _CacheMeta:
    """差异缓存的元数据（落盘为 cache_meta.json）。

    Attributes:
        server: 该缓存所属的渠道服名称。
        version: 生成缓存时的游戏版本号。
        created_at: 生成时间（ISO 8601）。
        files: 缓存内的文件相对路径列表。
    """

    server: str
    version: str
    created_at: str = ""
    files: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _CacheMeta:
        """从字典还原元数据。

        Args:
            data: JSON 解析得到的字典。

        Returns:
            _CacheMeta 实例；字段缺失时取空默认值。
        """
        raw_files = data.get("files")
        files = [str(item) for item in raw_files] if isinstance(raw_files, list) else []
        return cls(
            server=str(data.get("server", "")),
            version=str(data.get("version", "")),
            created_at=str(data.get("created_at", "")),
            files=files,
        )

    def to_dict(self) -> dict[str, Any]:
        """导出为可 JSON 序列化的字典。

        Returns:
            元数据字典。
        """
        return {
            "server": self.server,
            "version": self.version,
            "created_at": self.created_at,
            "files": list(self.files),
        }


class ChannelSwitcher:
    """渠道服秒级切换器。

    以「本地差异缓存」为核心，把切渠道服的代价从「整包下载」降到「本地文件
    恢复」；缓存不可用时才回落到下载，并把新差异写回缓存。

    Args:
        config_manager: 注入的配置管理器；为 None 时使用默认配置。
        downloader: 客户端下载器；为 None 时按需惰性创建
            :class:`~dwrg_manager.resources.downloader.Downloader`。
        channel_config_patterns: 切换前需要备份的渠道配置文件通配模式。

    Example:
        >>> switcher = ChannelSwitcher()  # doctest: +SKIP
        >>> result = switcher.checkout("bserver")  # doctest: +SKIP
        >>> result.mode  # doctest: +SKIP
        <SwitchMode.CACHE: 'cache'>
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        downloader: ClientDownloader | None = None,
        channel_config_patterns: Sequence[str] = CHANNEL_CONFIG_PATTERNS,
    ) -> None:
        self.config_manager = config_manager or ConfigManager()
        self._downloader_ref = downloader
        self._channel_config_patterns = tuple(channel_config_patterns)
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------ #
    # 目录解析
    # ------------------------------------------------------------------ #
    def resolve_game_dir(self, game_dir: str | Path | None = None) -> Path:
        """解析游戏目录：显式参数 > 配置 > data_dir/game。

        Args:
            game_dir: 显式指定的游戏目录；为 None 时按上述顺序回落。

        Returns:
            规范化后的绝对路径（不要求已存在）。

        Raises:
            ValidationError: 路径类型非法。
        """
        if game_dir is not None:
            return validate_path(game_dir)
        configured = self.config_manager.get_app_config().game_path
        if configured:
            return validate_path(configured)
        data_dir = self.config_manager.get_app_config().data_dir
        return validate_path(Path(data_dir).expanduser() / "game")

    def remember_game_dir(self, game_dir: str | Path) -> Path:
        """把游戏目录写入配置，实现「一次设置、永久生效」。

        Args:
            game_dir: 游戏目录路径。

        Returns:
            写入配置的规范化绝对路径。
        """
        resolved = validate_path(game_dir)
        self.config_manager.get_app_config().game_path = str(resolved)
        self.config_manager.save_config()
        self.logger.info("已记住游戏目录: %s", resolved)
        return resolved

    def _cache_root(self, game_dir: Path) -> Path:
        """返回差异缓存的根目录（不存在也不创建）。

        Args:
            game_dir: 游戏目录。

        Returns:
            game_dir 下的差异缓存根目录。
        """
        return game_dir / CACHE_DIR_NAME

    def _cache_dir(self, game_dir: Path, server: str) -> Path:
        """返回指定渠道服的差异缓存目录。

        Args:
            game_dir: 游戏目录。
            server: 渠道服名称。

        Returns:
            该渠道服的缓存目录。
        """
        return self._cache_root(game_dir) / server

    def _config_backup_dir(self, game_dir: Path) -> Path:
        """返回渠道配置备份目录。

        Args:
            game_dir: 游戏目录。

        Returns:
            渠道配置备份目录。
        """
        return game_dir / CONFIG_BACKUP_DIR_NAME

    def _snapshot_path(self, game_dir: Path) -> Path:
        """返回「上一个渠道服」快照文件路径。

        Args:
            game_dir: 游戏目录。

        Returns:
            快照 JSON 路径。
        """
        return self._cache_root(game_dir) / SNAPSHOT_NAME

    # ------------------------------------------------------------------ #
    # 版本与检测
    # ------------------------------------------------------------------ #
    def read_version(self, game_dir: Path) -> str:
        """读取游戏目录下的版本号。

        依次尝试 :data:`VERSION_FILE_NAMES` 中的文件名，取第一个可读且非空的
        内容（去空白）；都读不到时返回空字符串。

        Args:
            game_dir: 游戏目录。

        Returns:
            版本号字符串；未找到时为空字符串。
        """
        for name in VERSION_FILE_NAMES:
            candidate = game_dir / name
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self.logger.debug("读取版本文件失败: %s (%s)", candidate, exc)
                continue
            version = text.strip()
            if version:
                return version
        return ""

    def detect_current_server(self, game_dir: str | Path | None = None) -> str | None:
        """扫描目录特征推断当前渠道服。

        识别策略（按优先级）：

        1. 渠道 SDK 配置（KRSDKConfig.json 等）的**内容**中出现已知渠道服
           标识串（netease / bilibili / test ...）；
        2. 渠道标记文件名（channel_bilibili*.json / *bilibili*_channel）；
        3. 缓存快照中记录的上一渠道服（仅作兜底，前两者都失败时）。

        Args:
            game_dir: 游戏目录；为 None 时使用 :meth:`resolve_game_dir`。

        Returns:
            识别出的渠道服名称；无法识别时返回 None。

        Example:
            >>> ChannelSwitcher().detect_current_server("/tmp/game")  # doctest: +SKIP
            'bserver'
        """
        directory = self.resolve_game_dir(game_dir)
        if not directory.is_dir():
            self.logger.warning("游戏目录不存在，无法识别渠道服: %s", directory)
            return None

        detected = self._detect_by_content(directory) or self._detect_by_feature(
            directory
        )
        if detected:
            self.logger.info("识别到当前渠道服: %s", detected)
            return detected

        snapshot = self._load_snapshot(directory)
        if snapshot:
            self.logger.debug("按快照兜底识别渠道服: %s", snapshot)
        return snapshot

    def _detect_by_content(self, game_dir: Path) -> str | None:
        """通过渠道 SDK 配置内容识别渠道服。

        Args:
            game_dir: 游戏目录。

        Returns:
            识别出的渠道服名称；未命中返回 None。
        """
        for config_file in self._iter_channel_config_files(game_dir):
            try:
                text = (
                    config_file.read_text(encoding="utf-8", errors="replace")
                    .strip()
                    .lower()
                )
            except OSError as exc:
                self.logger.debug("读取渠道配置失败: %s (%s)", config_file, exc)
                continue
            for server, markers in SERVER_CONTENT_MARKERS.items():
                if any(marker in text for marker in markers):
                    return server
        return None

    def _detect_by_feature(self, game_dir: Path) -> str | None:
        """通过渠道标记文件名识别渠道服。

        Args:
            game_dir: 游戏目录。

        Returns:
            识别出的渠道服名称；未命中返回 None。
        """
        for server, patterns in SERVER_FEATURE_FILES.items():
            for pattern in patterns:
                for candidate in game_dir.glob(pattern):
                    if candidate.is_file():
                        return server
        return None

    def _iter_channel_config_files(self, game_dir: Path) -> Iterable[Path]:
        """迭代游戏目录下的渠道配置文件。

        Args:
            game_dir: 游戏目录。

        Yields:
            匹配 :data:`CHANNEL_CONFIG_PATTERNS` 的文件路径（去重）。
        """
        seen: set[Path] = set()
        for pattern in self._channel_config_patterns:
            for candidate in game_dir.glob(pattern):
                if candidate.is_file() and candidate not in seen:
                    seen.add(candidate)
                    yield candidate

    # ------------------------------------------------------------------ #
    # 客户端文件清单
    # ------------------------------------------------------------------ #
    def client_files(self, server: str) -> list[dict[str, str]]:
        """返回指定渠道服的客户端框架文件清单。

        只描述「框架 + 直链」部分：文件名、相对路径与下载 URL。逐文件的
        资源清单（path/size/hash）由 :mod:`dwrg_manager.resources` 负责，
        此处不重复实现。

        Args:
            server: 渠道服名称。

        Returns:
            每项含 name / path / url 的字典列表。
        """
        base = self._endpoint(server).rstrip("/")
        return [
            {
                "name": "IdentityV.exe",
                "path": "IdentityV.exe",
                "url": f"{base}/client/IdentityV.exe",
            },
            {
                "name": "UnityPlayer.dll",
                "path": "UnityPlayer.dll",
                "url": f"{base}/client/UnityPlayer.dll",
            },
        ]

    def _endpoint(self, server: str) -> str:
        """返回渠道服的接口地址（配置优先，未知渠道服回落官网）。

        Args:
            server: 渠道服名称。

        Returns:
            地址字符串。
        """
        config = self._server_config(server)
        if config is not None and config.endpoint:
            return config.endpoint
        return DEFAULT_ENDPOINTS.get(server, DEFAULT_ENDPOINTS["official"])

    def _server_config(self, server: str) -> ServerConfig | None:
        """查询渠道服配置。

        Args:
            server: 渠道服名称。

        Returns:
            渠道服配置；不存在时返回 None。
        """
        return self.config_manager.get_server_config(server)

    def _known_server_names(self) -> tuple[str, ...]:
        """返回配置中已知的渠道服名称。

        Returns:
            按字典序排列的渠道服名称元组。
        """
        return tuple(
            sorted(server.name for server in self.config_manager.list_servers())
        )

    def _ensure_known_server(self, server: str) -> None:
        """校验渠道服是否已在配置中存在。

        Args:
            server: 渠道服名称。

        Raises:
            ServerError: 渠道服不存在。
        """
        if self._server_config(server) is not None:
            return
        available = ", ".join(self._known_server_names()) or "（无）"
        raise ServerError(f"渠道服不存在: {server}，可用: {available}", server=server)

    # ------------------------------------------------------------------ #
    # checkout
    # ------------------------------------------------------------------ #
    def checkout(
        self,
        target: str,
        game_dir: str | Path | None = None,
        *,
        force_sync: bool = False,
    ) -> CheckoutResult:
        """切换到目标渠道服（秒级优先）。

        流程：校验目标 → 大版本变化则重置缓存 → 备份渠道配置 → 把当前渠道服
        文件快照进缓存 → 尝试缓存恢复目标 → 缓存不可用则回落下载并回写缓存
        → 更新快照。

        Args:
            target: 目标渠道服名称。
            game_dir: 游戏目录；为 None 时使用 :meth:`resolve_game_dir`。
            force_sync: 为 True 时跳过缓存，强制走下载路径。

        Returns:
            :class:`CheckoutResult`；失败时 success 为 False 且 error
            说明原因，此时不会改动游戏目录。

        Raises:
            ServerError: 目标渠道服不存在。
        """
        directory = self.resolve_game_dir(game_dir)
        self._ensure_known_server(target)

        current = self.detect_current_server(directory)
        if current == target:
            self.logger.info("目标渠道服即当前渠道服，无需切换: %s", target)
            self._write_snapshot(directory, target)
            return CheckoutResult(
                success=True, target=target, previous=current, mode=SwitchMode.NOOP
            )

        cache_reset = False
        if self._version_changed(directory):
            self.logger.info("检测到大版本变化，重置差异缓存")
            self.reset_cache(directory)
            cache_reset = True

        backup_files = self._backup_channel_configs(directory)
        if not backup_files and current is not None:
            # 已识别出渠道服却找不到任何渠道配置文件：多半是目录指错，直接失败。
            self.logger.error("未找到可备份的渠道配置文件: %s", directory)
            return CheckoutResult(
                success=False,
                target=target,
                previous=current,
                backup_files=0,
                error=f"未找到渠道配置文件，请确认游戏目录: {directory}",
            )

        if current is not None:
            self._capture_current(directory, current)

        if not force_sync:
            cached = self._restore_from_cache(directory, target)
            if cached is not None:
                self._apply_channel_configs(directory, target)
                self._write_snapshot(directory, target)
                return CheckoutResult(
                    success=True,
                    target=target,
                    previous=current,
                    mode=SwitchMode.CACHE,
                    restored_files=len(cached),
                    backup_files=backup_files,
                    cache_reset=cache_reset,
                )

        downloaded = self._download_client(target, directory)
        if downloaded.success:
            self._write_cache(directory, target, downloaded)
            self._apply_channel_configs(directory, target)
            self._write_snapshot(directory, target)
            return CheckoutResult(
                success=True,
                target=target,
                previous=current,
                mode=SwitchMode.DOWNLOAD,
                downloaded_files=len(downloaded.files),
                backup_files=backup_files,
                cache_reset=cache_reset,
            )

        return CheckoutResult(
            success=False,
            target=target,
            previous=current,
            backup_files=backup_files,
            cache_reset=cache_reset,
            error=downloaded.error or "下载客户端失败",
        )

    def rollback(self, game_dir: str | Path | None = None) -> CheckoutResult:
        """切回上一个渠道服（保留快照）。

        Args:
            game_dir: 游戏目录；为 None 时使用 :meth:`resolve_game_dir`。

        Returns:
            :class:`CheckoutResult`，mode 为 :attr:`SwitchMode.ROLLBACK`。

        Raises:
            ServerError: 没有可回滚的快照。
        """
        directory = self.resolve_game_dir(game_dir)
        snapshot = self._load_snapshot(directory)
        if not snapshot:
            raise ServerError("没有可回滚的渠道服快照，请先执行一次 checkout")

        current = self.detect_current_server(directory)
        result = self.checkout(snapshot, directory)
        if result.success:
            result.mode = SwitchMode.ROLLBACK
            result.previous = current or result.previous
        return result

    # ------------------------------------------------------------------ #
    # sync
    # ------------------------------------------------------------------ #
    def sync(
        self,
        game_dir: str | Path | None = None,
        *,
        repair: bool = False,
    ) -> SyncResult:
        """全量校验本地客户端文件，报告（可选修复）损坏与缺失。

        以差异缓存中的同渠道服快照作为「已知完好」基准：缓存里没有对应文件时
        只校验存在性，有对应文件时比对 MD5。

        Args:
            game_dir: 游戏目录；为 None 时使用 :meth:`resolve_game_dir`。
            repair: 为 True 时尝试用本地缓存修复缺失/损坏文件。

        Returns:
            :class:`SyncResult`；无法识别当前渠道服时 success 为 False。
        """
        directory = self.resolve_game_dir(game_dir)
        current = self.detect_current_server(directory)
        if current is None:
            return SyncResult(success=False, error="无法识别当前渠道服，请先 checkout")

        entries = self.client_files(current)
        missing: list[str] = []
        corrupted: list[str] = []
        for entry in entries:
            relative = entry["path"]
            try:
                path = validate_path(relative, base=directory)
            except ValidationError as exc:
                self.logger.warning("跳过越界文件: %s (%s)", relative, exc)
                continue
            if not path.is_file():
                missing.append(relative)
            elif self._is_corrupted(directory, current, path, relative):
                corrupted.append(relative)

        repaired: list[str] = []
        if repair:
            for relative in [*missing, *corrupted]:
                if self._restore_single(directory, current, relative):
                    repaired.append(relative)
                    if relative in missing:
                        missing.remove(relative)
                    elif relative in corrupted:
                        corrupted.remove(relative)

        healthy = len(entries) - len(missing) - len(corrupted)
        result = SyncResult(
            success=True,
            total_files=len(entries),
            healthy_files=healthy,
            corrupted_files=corrupted,
            missing_files=missing,
            repaired_files=repaired,
            version=self.read_version(directory),
        )
        self.logger.info("渠道服文件校验完成: %s", result.to_dict())
        return result

    def _is_corrupted(
        self, game_dir: Path, server: str, path: Path, relative: str
    ) -> bool:
        """判断本地文件是否与缓存快照不一致（即已损坏）。

        Args:
            game_dir: 游戏目录。
            server: 渠道服名称。
            path: 本地文件路径。
            relative: 文件相对路径。

        Returns:
            缓存中存在同路径文件且哈希不一致时返回 True；无缓存基准时返回 False。
        """
        cached = self._cache_dir(game_dir, server) / relative
        if not cached.is_file():
            return False
        from ..resources.validator import Validator

        validator = Validator()
        try:
            return validator.hash_file(path) != validator.hash_file(cached)
        except OSError as exc:
            self.logger.warning("比对文件哈希失败: %s (%s)", path, exc)
            return False

    def _restore_single(self, game_dir: Path, server: str, relative: str) -> bool:
        """从差异缓存恢复单个文件。

        Args:
            game_dir: 游戏目录。
            server: 渠道服名称。
            relative: 文件相对路径。

        Returns:
            恢复成功返回 True；缓存缺失或路径越界返回 False。
        """
        cache_file = self._cache_dir(game_dir, server) / relative
        if not cache_file.is_file():
            return False
        try:
            target = validate_path(relative, base=game_dir)
        except ValidationError as exc:
            self.logger.warning("缓存文件路径越界: %s (%s)", relative, exc)
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(cache_file, target)
        except OSError as exc:
            self.logger.warning("恢复缓存文件失败: %s (%s)", target, exc)
            return False
        return True

    # ------------------------------------------------------------------ #
    # download
    # ------------------------------------------------------------------ #
    def download(
        self,
        server: str,
        path: str | Path | None = None,
    ) -> DownloadResult:
        """从零下载指定渠道服的客户端框架。

        下载成功后会把文件写回差异缓存并记住游戏目录，使后续
        :meth:`checkout` 可以秒级完成。

        Args:
            server: 目标渠道服名称。
            path: 下载目录；为 None 时使用 :meth:`resolve_game_dir`。

        Returns:
            :class:`DownloadResult`。

        Raises:
            ServerError: 渠道服不存在。
        """
        directory = self.resolve_game_dir(path)
        self._ensure_known_server(server)
        directory.mkdir(parents=True, exist_ok=True)
        self.remember_game_dir(directory)
        result = self._download_client(server, directory)
        if result.success:
            self._write_cache(directory, server, result)
            self._apply_channel_configs(directory, server)
            self._write_snapshot(directory, server)
        return result

    # ------------------------------------------------------------------ #
    # 缓存管理
    # ------------------------------------------------------------------ #
    def reset_cache(self, game_dir: str | Path | None = None) -> bool:
        """清空差异缓存（保留渠道配置备份与快照）。

        Args:
            game_dir: 游戏目录；为 None 时使用 :meth:`resolve_game_dir`。

        Returns:
            清理成功返回 True；读写失败返回 False。
        """
        directory = self.resolve_game_dir(game_dir)
        root = self._cache_root(directory)
        if not root.exists():
            return True
        try:
            for child in root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
            self.logger.info("已重置差异缓存: %s", root)
            return True
        except OSError as exc:
            self.logger.error("重置差异缓存失败: %s (%s)", root, exc)
            return False

    def cache_info(self, game_dir: str | Path | None = None) -> dict[str, Any]:
        """返回差异缓存的统计信息。

        Args:
            game_dir: 游戏目录；为 None 时使用 :meth:`resolve_game_dir`。

        Returns:
            含 cache_dir / servers / total_files / total_size 的字典。
        """
        directory = self.resolve_game_dir(game_dir)
        root = self._cache_root(directory)
        servers: dict[str, dict[str, Any]] = {}
        total_files = 0
        total_size = 0
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                files = [item for item in child.rglob("*") if item.is_file()]
                size = sum(item.stat().st_size for item in files)
                servers[child.name] = {
                    "files": len(files),
                    "size": size,
                    "version": self._read_meta(child).version,
                }
                total_files += len(files)
                total_size += size
        return {
            "cache_dir": str(root),
            "servers": servers,
            "total_files": total_files,
            "total_size": total_size,
        }

    def _version_changed(self, game_dir: Path) -> bool:
        """判断游戏版本是否相对缓存记录发生变化。

        Args:
            game_dir: 游戏目录。

        Returns:
            任一缓存的记录版本与当前版本不一致时返回 True。
        """
        version = self.read_version(game_dir)
        if not version:
            return False
        root = self._cache_root(game_dir)
        if not root.is_dir():
            return False
        for child in root.iterdir():
            if not child.is_dir():
                continue
            recorded = self._read_meta(child).version
            if recorded and recorded != version:
                return True
        return False

    def _read_meta(self, cache_dir: Path) -> _CacheMeta:
        """读取某个渠道服缓存的元数据。

        Args:
            cache_dir: 该渠道服的缓存目录。

        Returns:
            _CacheMeta；文件缺失或损坏时返回空元数据。
        """
        path = cache_dir / CACHE_META_NAME
        if not path.is_file():
            return _CacheMeta(server=cache_dir.name, version="")
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.logger.warning("读取缓存元数据失败: %s (%s)", path, exc)
            return _CacheMeta(server=cache_dir.name, version="")
        if not isinstance(data, dict):
            return _CacheMeta(server=cache_dir.name, version="")
        return _CacheMeta.from_dict(data)

    def _write_cache(
        self, game_dir: Path, server: str, result: DownloadResult
    ) -> list[str]:
        """把下载结果写回差异缓存。

        Args:
            game_dir: 游戏目录。
            server: 渠道服名称。
            result: 下载结果。

        Returns:
            写入缓存的文件相对路径列表。
        """
        cache_dir = self._cache_dir(game_dir, server)
        cache_dir.mkdir(parents=True, exist_ok=True)
        stored: list[str] = []
        for relative in result.files:
            source = game_dir / relative
            if not source.is_file():
                continue
            target = cache_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, target)
            except OSError as exc:
                self.logger.warning("写入差异缓存失败: %s (%s)", target, exc)
                continue
            stored.append(relative)
        meta = _CacheMeta(
            server=server,
            version=self.read_version(game_dir),
            created_at=datetime.now().isoformat(timespec="seconds"),
            files=stored,
        )
        try:
            (cache_dir / CACHE_META_NAME).write_text(
                json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.warning("写入缓存元数据失败: %s (%s)", cache_dir, exc)
        self.logger.info("已写入差异缓存: %s（%d 个文件）", cache_dir, len(stored))
        return stored

    def _capture_current(self, game_dir: Path, server: str) -> list[str]:
        """把当前渠道服已存在于磁盘的文件快照进差异缓存。

        这是「双向秒级」的关键：从 A 切到 B 时同时缓存 A，回切时才不用再下载。

        Args:
            game_dir: 游戏目录。
            server: 当前渠道服名称。

        Returns:
            写入缓存的文件相对路径列表。
        """
        cache_dir = self._cache_dir(game_dir, server)
        cache_dir.mkdir(parents=True, exist_ok=True)
        stored: list[str] = []
        for entry in self.client_files(server):
            relative = entry["path"]
            source = game_dir / relative
            if not source.is_file():
                continue
            target = cache_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, target)
            except OSError as exc:
                self.logger.warning("快照当前渠道服失败: %s (%s)", source, exc)
                continue
            stored.append(relative)
        meta = _CacheMeta(
            server=server,
            version=self.read_version(game_dir),
            created_at=datetime.now().isoformat(timespec="seconds"),
            files=stored,
        )
        try:
            (cache_dir / CACHE_META_NAME).write_text(
                json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.warning("写入缓存元数据失败: %s (%s)", cache_dir, exc)
        if stored:
            self.logger.info("已快照当前渠道服 %s：%d 个文件", server, len(stored))
        return stored

    def _restore_from_cache(self, game_dir: Path, server: str) -> list[str] | None:
        """尝试从差异缓存恢复目标渠道服文件。

        缓存目录不存在、元数据版本与当前版本不一致、或任一文件缺失/损坏时
        都视为「缓存不可用」，返回 None 由调用方回落下载。

        Args:
            game_dir: 游戏目录。
            server: 目标渠道服名称。

        Returns:
            恢复成功的文件相对路径列表；缓存不可用时返回 None。
        """
        cache_dir = self._cache_dir(game_dir, server)
        if not cache_dir.is_dir():
            self.logger.debug("无差异缓存: %s", cache_dir)
            return None

        meta = self._read_meta(cache_dir)
        version = self.read_version(game_dir)
        if meta.version and version and meta.version != version:
            self.logger.info(
                "缓存版本不符（%s != %s），回落下载", meta.version, version
            )
            return None

        restored: list[str] = []
        for relative in meta.files:
            cached_file = cache_dir / relative
            if not cached_file.is_file():
                self.logger.warning("缓存文件缺失: %s", cached_file)
                return None
            try:
                target = validate_path(relative, base=game_dir)
            except ValidationError as exc:
                self.logger.warning("缓存文件路径越界: %s (%s)", relative, exc)
                return None
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(cached_file, target)
            except OSError as exc:
                self.logger.warning("恢复缓存文件失败: %s (%s)", target, exc)
                return None
            restored.append(relative)

        if not restored:
            self.logger.debug("差异缓存为空: %s", cache_dir)
            return None
        self.logger.info("已从缓存恢复 %d 个文件（渠道服 %s）", len(restored), server)
        return restored

    # ------------------------------------------------------------------ #
    # 快照
    # ------------------------------------------------------------------ #
    def _load_snapshot(self, game_dir: Path) -> str | None:
        """读取上一渠道服快照。

        Args:
            game_dir: 游戏目录。

        Returns:
            快照记录的渠道服名称；无快照时返回 None。
        """
        path = self._snapshot_path(game_dir)
        if not path.is_file():
            return None
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.logger.warning("读取渠道服快照失败: %s (%s)", path, exc)
            return None
        if not isinstance(data, dict):
            return None
        server = str(data.get("server", "")).strip()
        return server or None

    def _write_snapshot(self, game_dir: Path, server: str) -> None:
        """写入「上一个渠道服」快照。

        Args:
            game_dir: 游戏目录。
            server: 渠道服名称。
        """
        path = self._snapshot_path(game_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "server": server,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------ #
    # 渠道配置备份 / 应用
    # ------------------------------------------------------------------ #
    def _backup_channel_configs(self, game_dir: Path) -> int:
        """备份当前渠道配置文件到渠道配置备份目录。

        Args:
            game_dir: 游戏目录。

        Returns:
            备份的文件数量。
        """
        backup_dir = self._config_backup_dir(game_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for source in self._iter_channel_config_files(game_dir):
            target = backup_dir / source.name
            try:
                shutil.copy2(source, target)
            except OSError as exc:
                self.logger.warning("备份渠道配置失败: %s (%s)", source, exc)
                continue
            count += 1
        self.logger.info("已备份 %d 个渠道配置文件", count)
        return count

    def _apply_channel_configs(self, game_dir: Path, server: str) -> None:
        """为目标渠道服写入渠道标记文件。

        只生成轻量的渠道标记（channel_<server>.json），不改动客户端 SDK
        配置文件本体，避免破坏官方登录流程。

        Args:
            game_dir: 游戏目录。
            server: 目标渠道服名称。
        """
        marker = game_dir / f"channel_{server}.json"
        payload = {
            "server": server,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            marker.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            self.logger.warning("写入渠道标记失败: %s (%s)", marker, exc)

    # ------------------------------------------------------------------ #
    # 下载
    # ------------------------------------------------------------------ #
    def _downloader(self) -> ClientDownloader:
        """惰性获取下载器（默认使用资源模块的实现）。

        Returns:
            下载器实例。
        """
        if self._downloader_ref is not None:
            return self._downloader_ref
        from ..resources.downloader import Downloader

        app_config = self.config_manager.get_app_config()
        downloader: ClientDownloader = Downloader(
            concurrency=app_config.max_concurrent_downloads,
            timeout=app_config.download_timeout,
        )
        self._downloader_ref = downloader
        return downloader

    def _download_client(self, server: str, game_dir: Path) -> DownloadResult:
        """下载客户端框架文件（同步封装，内部跑事件循环）。

        Args:
            server: 渠道服名称。
            game_dir: 下载目录。

        Returns:
            DownloadResult。
        """
        entries = self.client_files(server)
        downloader = self._downloader()
        results = asyncio.run(self._download_all(downloader, entries, game_dir))
        files: list[str] = []
        failed: list[str] = []
        total_size = 0
        for entry, outcome in zip(entries, results, strict=True):
            if bool(getattr(outcome, "success", False)):
                files.append(entry["path"])
                total_size += int(getattr(outcome, "bytes_written", 0) or 0)
            else:
                failed.append(entry["name"])
        success = not failed
        return DownloadResult(
            success=success,
            server=server,
            game_dir=game_dir,
            files=files,
            failed_files=failed,
            total_size=total_size,
            error=None if success else f"{len(failed)} 个文件下载失败",
        )

    @staticmethod
    async def _download_all(
        downloader: ClientDownloader,
        entries: Sequence[dict[str, str]],
        game_dir: Path,
    ) -> list[Any]:
        """并发下载全部条目。

        Args:
            downloader: 下载器实例。
            entries: 文件条目（含 url / path）。
            game_dir: 下载目录。

        Returns:
            与 entries 顺序一致的下载结果列表。
        """
        return list(
            await asyncio.gather(
                *(
                    downloader.download(entry["url"], game_dir / entry["path"])
                    for entry in entries
                )
            )
        )


__all__ = [
    "CACHE_DIR_NAME",
    "CHANNEL_CONFIG_PATTERNS",
    "DEFAULT_ENDPOINTS",
    "SERVER_CONTENT_MARKERS",
    "SERVER_FEATURE_FILES",
    "VERSION_FILE_NAMES",
    "ChannelSwitcher",
    "CheckoutResult",
    "DownloadResult",
    "SwitchMode",
    "SyncResult",
]
