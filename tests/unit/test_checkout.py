"""秒级渠道服切换（checkout / sync / download）的单元测试。

全部用例基于 tmp_path 构造临时游戏目录，并通过注入不触网的假下载器
驱动下载路径，因此不会发起任何真实网络请求。

覆盖点：

* detect_current_server 的三种识别通道；
* checkout 的首次切换（建缓存）、二次切换（走缓存不触网）、
  缓存损坏回落下载、大版本变化重置缓存、目标即当前渠道服（NOOP）；
* checkout 的失败路径（未找到渠道配置文件、下载失败）；
* rollback 正常与无快照报错；
* sync 的健康 / 缺失 / 损坏 / 修复四种状态；
* download 从零下载并回写缓存；
* validate_path 的目录穿越防护；
* cache_info / reset_cache 的统计与清理。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dwrg_manager.exceptions import ServerError, ValidationError
from dwrg_manager.servers.checkout import (
    CACHE_DIR_NAME,
    ChannelSwitcher,
    SwitchMode,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# 测试替身
# --------------------------------------------------------------------------- #
class FakeDownloader:
    """不触网的下载器替身。

    download 会在目标路径写入占位内容，从而模拟一次成功的文件下载；
    fail_paths 中列出的文件会返回失败结果。
    """

    def __init__(self, *, fail_paths: set[str] | None = None) -> None:
        """初始化替身。

        Args:
            fail_paths: 需要模拟失败的相对路径集合。
        """
        self.fail_paths = fail_paths or set()
        self.calls: list[str] = []

    async def download(self, url: str, dest: Path) -> Any:
        """模拟下载：写入占位文件并返回结果对象。

        Args:
            url: 下载地址（仅记录）。
            dest: 目标路径。

        Returns:
            带 success / bytes_written 属性的结果对象。
        """
        self.calls.append(url)
        relative = dest.name
        if relative in self.fail_paths:
            return _Outcome(success=False, bytes_written=0)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("content-of-" + relative, encoding="utf-8")
        return _Outcome(success=True, bytes_written=dest.stat().st_size)


class _Outcome:
    """最小下载结果替身。"""

    def __init__(self, *, success: bool, bytes_written: int) -> None:
        """初始化结果。

        Args:
            success: 是否成功。
            bytes_written: 写入字节数。
        """
        self.success = success
        self.bytes_written = bytes_written


# --------------------------------------------------------------------------- #
# 辅助函数
# --------------------------------------------------------------------------- #
def _make_switcher(
    config_manager: Any, downloader: FakeDownloader | None = None
) -> ChannelSwitcher:
    """构造绑定了隔离配置与假下载器的切换器。

    Args:
        config_manager: 测试用配置管理器。
        downloader: 下载器替身；缺省自动创建。

    Returns:
        配置好的 ChannelSwitcher 实例。
    """
    return ChannelSwitcher(config_manager, downloader or FakeDownloader())


def _seed_channel_config(game_dir: Path, server: str) -> None:
    """在游戏目录写入指定渠道服的渠道配置文件。

    Args:
        game_dir: 游戏目录。
        server: 渠道服名称（official / bserver / test_server）。
    """
    markers = {
        "official": "netease",
        "bserver": "bilibili",
        "test_server": "testing",
    }
    marker = markers.get(server, server)
    (game_dir / "KRSDKConfig.json").write_text(
        '{"KR_ChannelId": 19, "channel": "' + marker + '"}', encoding="utf-8"
    )
    (game_dir / ("channel_" + server + ".json")).write_text(
        '{"channel": "' + marker + '"}', encoding="utf-8"
    )


def _seed_version(game_dir: Path, version: str) -> None:
    """写入版本文件。

    Args:
        game_dir: 游戏目录。
        version: 版本号内容。
    """
    (game_dir / "version").write_text(version, encoding="utf-8")


# --------------------------------------------------------------------------- #
# 目录解析与版本读取
# --------------------------------------------------------------------------- #
class TestResolveGameDir:
    """游戏目录解析与版本读取。"""

    def test_resolve_prefers_explicit_argument(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """显式参数优先级最高。"""
        switcher = _make_switcher(config_manager)
        explicit = tmp_path / "explicit"
        assert switcher.resolve_game_dir(explicit) == explicit.resolve()

    def test_resolve_falls_back_to_configured_game_path(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """未显式指定时读取配置中的 game_path。"""
        configured = tmp_path / "configured"
        config_manager.set_config("game_path", str(configured))
        switcher = _make_switcher(config_manager)
        assert switcher.resolve_game_dir() == configured.resolve()

    def test_resolve_rejects_non_string(self, config_manager: Any) -> None:
        """路径类型非法时抛出 ValidationError。"""
        switcher = _make_switcher(config_manager)
        with pytest.raises(ValidationError):
            switcher.resolve_game_dir(123)  # type: ignore[arg-type]

    def test_read_version_returns_stripped_content(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """版本文件内容去除空白后返回。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_version(game_dir, "  2.0.1863932\n")
        switcher = _make_switcher(config_manager)
        assert switcher.read_version(game_dir) == "2.0.1863932"

    def test_read_version_missing_returns_empty(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """没有版本文件时返回空字符串。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        switcher = _make_switcher(config_manager)
        assert switcher.read_version(game_dir) == ""


# --------------------------------------------------------------------------- #
# 渠道服识别
# --------------------------------------------------------------------------- #
class TestDetectCurrentServer:
    """当前渠道服识别。"""

    def test_detect_by_content_marker(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """通过 SDK 配置内容中的渠道标识识别。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "bserver")
        switcher = _make_switcher(config_manager)
        assert switcher.detect_current_server(game_dir) == "bserver"

    def test_detect_by_feature_filename(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """通过渠道标记文件名识别。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        (game_dir / "channel_official.json").write_text("{}", encoding="utf-8")
        switcher = _make_switcher(config_manager)
        assert switcher.detect_current_server(game_dir) == "official"

    def test_detect_returns_none_for_unknown_directory(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """无法识别时返回 None。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        (game_dir / "readme.txt").write_text("hello", encoding="utf-8")
        switcher = _make_switcher(config_manager)
        assert switcher.detect_current_server(game_dir) is None

    def test_detect_falls_back_to_snapshot(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """特征识别失败时回落到缓存快照。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        switcher = _make_switcher(config_manager)
        switcher._write_snapshot(game_dir, "official")
        assert switcher.detect_current_server(game_dir) == "official"

    def test_detect_missing_directory_returns_none(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """目录不存在时返回 None 而不抛异常。"""
        switcher = _make_switcher(config_manager)
        assert switcher.detect_current_server(tmp_path / "absent") is None


# --------------------------------------------------------------------------- #
# checkout
# --------------------------------------------------------------------------- #
class TestCheckout:
    """渠道服切换主流程。"""

    def test_first_checkout_builds_cache(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """首次切换建立差异缓存并下载文件。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        downloader = FakeDownloader()
        switcher = _make_switcher(config_manager, downloader)

        result = switcher.checkout("bserver", game_dir)

        assert result.success is True
        assert result.mode is SwitchMode.DOWNLOAD
        assert result.previous == "official"
        assert result.downloaded_files == 2
        assert result.backup_files >= 1
        assert len(downloader.calls) == 2
        assert (game_dir / CACHE_DIR_NAME / "bserver").is_dir()
        assert (game_dir / "IdentityV.exe").is_file()

    def test_second_checkout_uses_cache_without_network(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """两个渠道服都有缓存后，切换完全不触网。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        # 先完整下载 official，使两个渠道服都进入差异缓存
        switcher = _make_switcher(config_manager)
        assert switcher.download("official", game_dir).success is True
        _seed_channel_config(game_dir, "official")
        assert switcher.checkout("bserver", game_dir).success is True

        _seed_channel_config(game_dir, "bserver")
        second_downloader = FakeDownloader()
        switcher._downloader_ref = second_downloader
        result = switcher.checkout("official", game_dir)

        assert result.success is True
        assert result.mode is SwitchMode.CACHE
        assert result.restored_files >= 1
        assert second_downloader.calls == []

    def test_checkout_falls_back_when_cache_corrupted(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """缓存元数据损坏时回落下载路径。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True

        cache_meta = game_dir / CACHE_DIR_NAME / "bserver" / "cache_meta.json"
        cache_meta.write_text("{not-json", encoding="utf-8")

        _seed_channel_config(game_dir, "bserver")
        downloader = FakeDownloader()
        switcher._downloader_ref = downloader
        result = switcher.checkout("official", game_dir)

        assert result.success is True
        assert result.mode is SwitchMode.DOWNLOAD
        assert len(downloader.calls) == 2

    def test_checkout_resets_cache_on_version_change(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """大版本变化自动重置差异缓存。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        _seed_version(game_dir, "1.0.0")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True

        _seed_channel_config(game_dir, "bserver")
        _seed_version(game_dir, "2.0.0")
        result = switcher.checkout("official", game_dir)

        assert result.success is True
        assert result.cache_reset is True
        assert result.mode is SwitchMode.DOWNLOAD

    def test_checkout_noop_when_target_is_current(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """目标渠道服即当前渠道服时不作任何改动。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        downloader = FakeDownloader()
        switcher = _make_switcher(config_manager, downloader)

        result = switcher.checkout("official", game_dir)

        assert result.success is True
        assert result.mode is SwitchMode.NOOP
        assert downloader.calls == []

    def test_checkout_unknown_server_raises(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """目标渠道服不存在时抛出 ServerError。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)

        with pytest.raises(ServerError):
            switcher.checkout("not-a-server", game_dir)

    def test_checkout_fails_when_no_channel_config(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """识别出渠道服却找不到渠道配置文件时失败。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        (game_dir / "KRSDKConfig.json").write_text(
            '{"channel": "netease"}', encoding="utf-8"
        )
        switcher = _make_switcher(config_manager)
        switcher._channel_config_patterns = ("*_nonexistent_marker",)

        result = switcher.checkout("bserver", game_dir)

        assert result.success is False
        assert result.error is not None
        assert "渠道配置" in result.error

    def test_checkout_fails_when_download_fails(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """下载失败时返回失败结果且不写缓存。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        downloader = FakeDownloader(fail_paths={"IdentityV.exe"})
        switcher = _make_switcher(config_manager, downloader)

        result = switcher.checkout("bserver", game_dir)

        assert result.success is False
        assert result.error is not None
        assert not (game_dir / CACHE_DIR_NAME / "bserver").is_dir()

    def test_checkout_force_sync_skips_cache(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """force_sync 跳过缓存直接走下载。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True

        _seed_channel_config(game_dir, "bserver")
        downloader = FakeDownloader()
        switcher._downloader_ref = downloader
        result = switcher.checkout("official", game_dir, force_sync=True)

        assert result.success is True
        assert result.mode is SwitchMode.DOWNLOAD
        assert len(downloader.calls) == 2


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #
class TestRollback:
    """回滚到上一渠道服。"""

    def test_rollback_returns_to_snapshot_server(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """回滚目标为快照记录的上一个渠道服。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        switcher = _make_switcher(config_manager)
        # 下载 official → 切到 bserver，此时快照记录的是 bserver
        assert switcher.download("official", game_dir).success is True
        _seed_channel_config(game_dir, "official")
        assert switcher.checkout("bserver", game_dir).success is True
        _seed_channel_config(game_dir, "bserver")

        result = switcher.rollback(game_dir)

        assert result.success is True
        assert result.mode is SwitchMode.ROLLBACK
        assert result.target == "bserver"
        # 回滚前的当前渠道服为 bserver
        assert result.previous == "bserver"

    def test_rollback_without_snapshot_raises(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """没有快照时抛出 ServerError。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        switcher = _make_switcher(config_manager)

        with pytest.raises(ServerError):
            switcher.rollback(game_dir)


# --------------------------------------------------------------------------- #
# sync
# --------------------------------------------------------------------------- #
class TestSync:
    """全量校验与修复。"""

    def test_sync_reports_all_healthy(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """文件齐全且未损坏时全部健康。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True
        _seed_channel_config(game_dir, "bserver")

        result = switcher.sync(game_dir)

        assert result.success is True
        assert result.total_files == 2
        assert result.healthy_files == 2
        assert result.corrupted_files == []
        assert result.missing_files == []

    def test_sync_detects_missing_file(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """缺失文件被报告出来。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True
        _seed_channel_config(game_dir, "bserver")
        (game_dir / "IdentityV.exe").unlink()

        result = switcher.sync(game_dir)

        assert result.success is True
        assert "IdentityV.exe" in result.missing_files

    def test_sync_detects_corrupted_file(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """与缓存哈希不符的文件被判为损坏。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True
        _seed_channel_config(game_dir, "bserver")
        (game_dir / "IdentityV.exe").write_text("tampered", encoding="utf-8")

        result = switcher.sync(game_dir)

        assert result.success is True
        assert "IdentityV.exe" in result.corrupted_files

    def test_sync_repair_restores_from_cache(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """repair=True 时从缓存修复缺失与损坏文件。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True
        _seed_channel_config(game_dir, "bserver")
        (game_dir / "IdentityV.exe").write_text("tampered", encoding="utf-8")
        (game_dir / "UnityPlayer.dll").unlink()

        result = switcher.sync(game_dir, repair=True)

        assert result.success is True
        assert sorted(result.repaired_files) == ["IdentityV.exe", "UnityPlayer.dll"]
        assert result.corrupted_files == []
        assert result.missing_files == []

    def test_sync_fails_when_server_unrecognized(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """无法识别当前渠道服时返回失败。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        (game_dir / "readme.txt").write_text("x", encoding="utf-8")
        switcher = _make_switcher(config_manager)

        result = switcher.sync(game_dir)

        assert result.success is False
        assert result.error is not None


# --------------------------------------------------------------------------- #
# download 与缓存管理
# --------------------------------------------------------------------------- #
class TestDownloadAndCache:
    """从零下载与缓存统计 / 清理。"""

    def test_download_creates_cache_and_snapshot(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """下载成功后建立缓存、快照并记住游戏目录。"""
        game_dir = tmp_path / "game"
        downloader = FakeDownloader()
        switcher = _make_switcher(config_manager, downloader)

        result = switcher.download("official", game_dir)

        assert result.success is True
        assert result.files == ["IdentityV.exe", "UnityPlayer.dll"]
        assert result.total_size > 0
        assert (game_dir / CACHE_DIR_NAME / "official").is_dir()
        assert switcher.detect_current_server(game_dir) == "official"

    def test_download_unknown_server_raises(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """渠道服不存在时抛出 ServerError。"""
        switcher = _make_switcher(config_manager)
        with pytest.raises(ServerError):
            switcher.download("not-a-server", tmp_path / "game")

    def test_cache_info_reports_servers(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """缓存统计包含各渠道服的文件数与总大小。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True

        info = switcher.cache_info(game_dir)

        assert info["total_files"] >= 2
        assert info["total_size"] > 0
        assert "bserver" in info["servers"]

    def test_reset_cache_clears_servers(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """重置缓存后渠道服目录被清空。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)
        assert switcher.checkout("bserver", game_dir).success is True

        assert switcher.reset_cache(game_dir) is True
        info = switcher.cache_info(game_dir)
        assert info["servers"] == {}

    def test_reset_cache_without_cache_dir_returns_true(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """缓存目录不存在时重置仍返回 True。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        switcher = _make_switcher(config_manager)
        assert switcher.reset_cache(game_dir) is True


# --------------------------------------------------------------------------- #
# 安全：目录穿越防护
# --------------------------------------------------------------------------- #
class TestPathSafety:
    """validate_path 的目录穿越防护。"""

    def test_restore_single_rejects_traversal(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """相对路径越界时拒绝恢复。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        cache_dir = game_dir / CACHE_DIR_NAME / "official"
        cache_dir.mkdir(parents=True)
        (cache_dir / "evil.txt").write_text("x", encoding="utf-8")

        switcher = _make_switcher(config_manager)
        assert switcher._restore_single(game_dir, "official", "../evil.txt") is False
        assert not (tmp_path / "evil.txt").exists()

    def test_sync_skips_traversal_entry(
        self, config_manager: Any, tmp_path: Path
    ) -> None:
        """sync 中的越界条目被跳过而不崩溃。"""
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        _seed_channel_config(game_dir, "official")
        switcher = _make_switcher(config_manager)

        original = switcher.client_files
        switcher.client_files = lambda server: [
            {"name": "../escape.txt", "path": "../escape.txt", "url": "http://x"}
        ]
        try:
            result = switcher.sync(game_dir)
        finally:
            switcher.client_files = original

        assert result.success is True
        assert result.total_files == 1
        assert not (tmp_path / "escape.txt").exists()


# --------------------------------------------------------------------------- #
# 结果序列化
# --------------------------------------------------------------------------- #
class TestResultSerialization:
    """结构化结果的 to_dict。"""

    def test_checkout_result_to_dict(self) -> None:
        """CheckoutResult 可序列化且 mode 为字符串。"""
        from dwrg_manager.servers.checkout import CheckoutResult

        result = CheckoutResult(
            success=True, target="bserver", mode=SwitchMode.CACHE, restored_files=3
        )
        data = result.to_dict()

        assert data["mode"] == "cache"
        assert data["restored_files"] == 3
        assert data["target"] == "bserver"

    def test_sync_result_to_dict(self) -> None:
        """SyncResult 列表字段为副本。"""
        from dwrg_manager.servers.checkout import SyncResult

        result = SyncResult(success=True, missing_files=["a"])
        data = result.to_dict()
        data["missing_files"].append("b")

        assert result.missing_files == ["a"]

    def test_download_result_to_dict(self, tmp_path: Path) -> None:
        """DownloadResult 的 game_dir 转为字符串。"""
        from dwrg_manager.servers.checkout import DownloadResult

        result = DownloadResult(success=True, server="official", game_dir=tmp_path)
        data = result.to_dict()

        assert data["game_dir"] == str(tmp_path)
