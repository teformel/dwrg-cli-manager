"""资源管理模块单元测试。

所有测试均使用 ``tmp_path`` 与注入的假传输层 / 假 aiohttp 会话，
**不访问真实网络**，也不会触碰真实 ``~/.dwrg``。
"""

import asyncio
import hashlib
import os
import time
from pathlib import Path

import pytest

from dwrg_manager.config.manager import ConfigManager
from dwrg_manager.resources.downloader import Downloader
from dwrg_manager.resources.manager import ResourceManager
from dwrg_manager.resources.models import (
    DownloadTask,
    ResourceFile,
    ResourceManifest,
    ResourceServer,
)
from dwrg_manager.resources.patcher import Patcher
from dwrg_manager.resources.validator import Validator


# --------------------------------------------------------------------------- #
# 测试替身 / 构造工具
# --------------------------------------------------------------------------- #
def make_config(tmp_path: Path) -> ConfigManager:
    """构造一个把数据/缓存目录指向 tmp_path 的 ConfigManager。"""
    config = ConfigManager(str(tmp_path / "config.yaml"))
    config.config.app.data_dir = str(tmp_path / "data")
    config.config.app.cache_dir = str(tmp_path / "cache")
    return config


class FakeTransport:
    """返回预设清单的假传输层。"""

    def __init__(self, manifest: ResourceManifest | None) -> None:
        self.manifest = manifest
        self.calls: list[str] = []

    async def fetch_manifest(self, server: ResourceServer) -> ResourceManifest | None:
        self.calls.append(server.name)
        return self.manifest


def make_file(
    name: str, data: bytes, *, path: str | None = None, version: str = "1.0.0"
) -> ResourceFile:
    """按内容构造一个 ResourceFile。"""
    return ResourceFile(
        name=name,
        path=path or name,
        size=len(data),
        md5=hashlib.md5(data).hexdigest(),
        version=version,
    )


def make_manifest(
    version: str,
    files: list[ResourceFile],
    download_url: str = "https://example.test/v1",
) -> ResourceManifest:
    """构造一个 ResourceManifest。"""
    return ResourceManifest(
        version=version,
        files=files,
        total_size=sum(f.size for f in files),
        download_url=download_url,
    )


class FakeStats:
    """记录并发请求数与峰值。"""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.requests = 0


class FakeContent:
    """可迭代块的假响应体。"""

    def __init__(self, body: bytes) -> None:
        self._body = body

    async def _gen(self, chunk_size: int):
        for index in range(0, len(self._body), chunk_size):
            await asyncio.sleep(0.005)
            yield self._body[index : index + chunk_size]

    def iter_chunked(self, chunk_size: int):
        return self._gen(chunk_size)


class FakeResponse:
    """假 aiohttp 响应（异步上下文管理器）。"""

    def __init__(self, status: int, body: bytes, stats: FakeStats) -> None:
        self.status = status
        self.headers: dict[str, str] = {}
        self.content = FakeContent(body)
        self._stats = stats

    async def __aenter__(self) -> "FakeResponse":
        self._stats.active += 1
        self._stats.requests += 1
        if self._stats.active > self._stats.max_active:
            self._stats.max_active = self._stats.active
        return self

    async def __aexit__(self, _exc_type=None, _exc=None, _tb=None) -> None:
        self._stats.active -= 1


class FakeSession:
    """假 aiohttp 会话（异步上下文管理器）。"""

    def __init__(self, stats: FakeStats, responder) -> None:
        self._stats = stats
        self._responder = responder

    def get(self, url: str, headers=None) -> FakeResponse:
        return self._responder(url, headers or {}, self._stats)

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, _exc_type=None, _exc=None, _tb=None) -> None:
        return None

    async def close(self) -> None:
        return None


def make_session_factory(
    files: dict[str, bytes],
    *,
    fail_times: int = 0,
    always_fail: bool = False,
    support_range: bool = True,
    stats: FakeStats | None = None,
):
    """构造一个按 URL 提供字节内容的假会话工厂。"""
    shared = stats or FakeStats()
    state = {"fails": fail_times}

    def responder(url: str, headers: dict, _stats: FakeStats) -> FakeResponse:
        if always_fail:
            return FakeResponse(500, b"", shared)
        if state["fails"] > 0:
            state["fails"] -= 1
            return FakeResponse(500, b"", shared)
        body = files.get(url, b"")
        range_header = headers.get("Range")
        if range_header and support_range:
            start = int(range_header.split("=")[1].split("-")[0])
            return FakeResponse(206, body[start:], shared)
        return FakeResponse(200, body, shared)

    def factory() -> FakeSession:
        return FakeSession(shared, responder)

    return factory, shared


# --------------------------------------------------------------------------- #
# Validator
# --------------------------------------------------------------------------- #
def test_hash_file_matches_hashlib(tmp_path: Path) -> None:
    """hash_file 结果必须与 hashlib 一致（md5 / sha256）。"""
    data = b"hello world" * 1000
    path = tmp_path / "a.bin"
    path.write_bytes(data)
    validator = Validator()
    assert validator.hash_file(path, "md5") == hashlib.md5(data).hexdigest()
    assert validator.hash_file(path, "sha256") == hashlib.sha256(data).hexdigest()


def test_verify_size_and_hash_mismatch(tmp_path: Path) -> None:
    """verify 在大小/哈希不符或文件缺失时返回 False。"""
    data = b"abcdef"
    path = tmp_path / "b.bin"
    path.write_bytes(data)
    validator = Validator()
    digest = hashlib.md5(data).hexdigest()

    assert validator.verify(path, size=6, md5=digest) is True
    assert validator.verify(path, size=7, md5=digest) is False
    assert validator.verify(path, size=6, md5="0" * 32) is False
    assert validator.verify(tmp_path / "missing.bin", size=6, md5=digest) is False
    assert validator.verify(path, size=6, md5=digest, sha256="1" * 64) is False


def test_human_size_boundaries() -> None:
    """human_size 在 0 / 1023 / 1024 / GB 等边界上正确格式化。"""
    validator = Validator()
    assert validator.human_size(0) == "0.00 B"
    assert validator.human_size(1023) == "1023.00 B"
    assert validator.human_size(1024) == "1.00 KB"
    assert validator.human_size(1024 * 1024) == "1.00 MB"
    assert validator.human_size(1024**3) == "1.00 GB"
    assert validator.human_size(int(1.5 * 1024**3)) == "1.50 GB"
    assert Validator.human_size(1024) == "1.00 KB"


def test_quick_check_requires_partial_hash(tmp_path: Path) -> None:
    """quick_check：大小一致且有抽样哈希时才可用；无抽样字段返回 False。"""
    data = b"x" * 5000
    path = tmp_path / "c.bin"
    path.write_bytes(data)
    validator = Validator()
    partial = Validator().sample_hash(path)

    assert validator.quick_check(path, len(data), partial) is True
    assert validator.quick_check(path, len(data), "0" * 32) is False
    assert validator.quick_check(path, len(data) + 1, partial) is False
    # 清单未提供抽样哈希字段 -> 不做抽样，返回 False 提示调用方全量校验。
    assert validator.quick_check(path, len(data), None) is False


# --------------------------------------------------------------------------- #
# Downloader
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_downloader_concurrency_limit(tmp_path: Path) -> None:
    """并发上限生效：峰值并发请求数不超过 concurrency。"""
    bodies = {f"https://t/{i}": bytes([i]) * 32 for i in range(5)}
    factory, stats = make_session_factory(bodies)
    downloader = Downloader(
        concurrency=2, retries=1, retry_backoff=0, chunk_size=4, session_factory=factory
    )
    tasks = [
        DownloadTask(
            url=url,
            dest=tmp_path / f"f{index}.bin",
            name=f"f{index}",
            expected_size=32,
            expected_md5=hashlib.md5(body).hexdigest(),
        )
        for index, (url, body) in enumerate(bodies.items())
    ]
    results = await downloader.download_many(tasks)

    assert len(results) == 5
    assert all(result.success for result in results)
    assert stats.max_active == 2


@pytest.mark.asyncio
async def test_downloader_retry_then_success(tmp_path: Path) -> None:
    """失败一次后重试成功，且 .part 被原子替换、不留残留。"""
    body = b"abcdef"
    factory, _stats = make_session_factory({"https://t/a": body}, fail_times=1)
    downloader = Downloader(retries=3, retry_backoff=0, session_factory=factory)
    dest = tmp_path / "a.bin"

    result = await downloader.download(
        "https://t/a",
        dest,
        expected_size=len(body),
        expected_md5=hashlib.md5(body).hexdigest(),
    )

    assert result.success is True
    assert result.attempts == 2
    assert dest.read_bytes() == body
    assert not (tmp_path / "a.bin.part").exists()


@pytest.mark.asyncio
async def test_downloader_retries_exhausted(tmp_path: Path) -> None:
    """重试耗尽后返回失败，尝试次数等于 retries，且不落地目标文件。"""
    factory, stats = make_session_factory({}, always_fail=True)
    downloader = Downloader(retries=3, retry_backoff=0, session_factory=factory)
    dest = tmp_path / "x.bin"

    result = await downloader.download("https://t/x", dest)

    assert result.success is False
    assert result.attempts == 3
    assert result.error
    assert not dest.exists()
    assert stats.requests == 3


@pytest.mark.asyncio
async def test_downloader_resume_with_range(tmp_path: Path) -> None:
    """服务器支持 Range 时基于 .part 断点续传。"""
    body = b"A" * 100
    dest = tmp_path / "r.bin"
    part = tmp_path / "r.bin.part"
    part.write_bytes(body[:40])
    factory, _stats = make_session_factory({"https://t/r": body}, support_range=True)
    downloader = Downloader(retries=1, retry_backoff=0, session_factory=factory)

    result = await downloader.download(
        "https://t/r",
        dest,
        expected_size=len(body),
        expected_md5=hashlib.md5(body).hexdigest(),
        resume=True,
    )

    assert result.success is True
    assert result.resumed is True
    assert dest.read_bytes() == body
    assert not part.exists()


@pytest.mark.asyncio
async def test_downloader_range_not_supported_falls_back(tmp_path: Path) -> None:
    """服务器不支持 Range（返回 200 整包）时优雅回退整文件重下。"""
    body = b"B" * 100
    dest = tmp_path / "r2.bin"
    part = tmp_path / "r2.bin.part"
    part.write_bytes(body[:40])
    factory, _stats = make_session_factory({"https://t/r2": body}, support_range=False)
    downloader = Downloader(retries=1, retry_backoff=0, session_factory=factory)

    result = await downloader.download(
        "https://t/r2",
        dest,
        expected_size=len(body),
        expected_md5=hashlib.md5(body).hexdigest(),
        resume=True,
    )

    assert result.success is True
    assert result.resumed is False
    assert dest.read_bytes() == body
    assert not part.exists()


# --------------------------------------------------------------------------- #
# Patcher
# --------------------------------------------------------------------------- #
def _make_patcher(tmp_path: Path) -> Patcher:
    return Patcher(
        manifest_path=tmp_path / "data" / "manifest.json",
        game_dir=tmp_path / "game",
    )


def test_patcher_plan_classification(tmp_path: Path) -> None:
    """plan 正确区分新增 / 更新 / 删除 / 未变化。"""
    file_a = make_file("a.bin", b"aaaa")
    file_b_old = make_file("b.bin", b"bbbb")
    file_b_new = make_file("b.bin", b"bbbbbb")
    file_c = make_file("c.bin", b"cccc")
    file_d = make_file("d.bin", b"dddd")

    local = make_manifest("1", [file_a, file_b_old, file_d])
    remote = make_manifest("2", [file_a, file_b_new, file_c])
    patcher = _make_patcher(tmp_path)

    plan = patcher.plan(local, remote)

    assert [f.path for f in plan.added] == ["c.bin"]
    assert [f.path for f in plan.updated] == ["b.bin"]
    assert [f.path for f in plan.removed] == ["d.bin"]
    assert [f.path for f in plan.unchanged] == ["a.bin"]
    assert plan.is_empty is False
    assert [f.path for f in plan.files_to_download()] == ["c.bin", "b.bin"]


def test_patcher_plan_none_local_all_added(tmp_path: Path) -> None:
    """本地无清单时所有远端文件都算新增。"""
    remote = make_manifest("1", [make_file("a.bin", b"a"), make_file("b.bin", b"b")])
    plan = _make_patcher(tmp_path).plan(None, remote)
    assert len(plan.added) == 2
    assert plan.updated == []
    assert plan.removed == []


@pytest.mark.asyncio
async def test_patcher_apply_downloads_and_saves_manifest(tmp_path: Path) -> None:
    """apply 下载新增文件、删除失效文件，并在成功后落盘远端清单。"""
    file_a = make_file("a.bin", b"aaaa")
    file_c = make_file("c.bin", b"cccc")
    file_d = make_file("d.bin", b"dddd")
    local = make_manifest("1", [file_a, file_d])
    remote = make_manifest("2", [file_a, file_c])

    patcher = _make_patcher(tmp_path)
    game_dir = tmp_path / "game"
    game_dir.mkdir(parents=True)
    (game_dir / "a.bin").write_bytes(b"aaaa")
    (game_dir / "d.bin").write_bytes(b"dddd")

    factory, _stats = make_session_factory({"https://example.test/v1/c.bin": b"cccc"})
    downloader = Downloader(retries=1, retry_backoff=0, session_factory=factory)

    plan = patcher.plan(local, remote)
    result = await patcher.apply(plan, downloader)

    assert result.success is True
    assert result.added == 1
    assert result.updated == 0
    assert result.removed == 1
    assert (game_dir / "c.bin").read_bytes() == b"cccc"
    assert not (game_dir / "d.bin").exists()
    assert patcher.manifest_path.exists()
    loaded = patcher.load_manifest()
    assert loaded is not None
    assert loaded.version == "2"


@pytest.mark.asyncio
async def test_patcher_apply_failure_does_not_save_manifest(tmp_path: Path) -> None:
    """下载失败时 success=False 且不落盘清单，便于下次重试。"""
    file_c = make_file("c.bin", b"cccc")
    remote = make_manifest("2", [file_c])
    patcher = _make_patcher(tmp_path)
    (tmp_path / "game").mkdir(parents=True)

    factory, _stats = make_session_factory({}, always_fail=True)
    downloader = Downloader(retries=2, retry_backoff=0, session_factory=factory)

    plan = patcher.plan(None, remote)
    result = await patcher.apply(plan, downloader)

    assert result.success is False
    assert result.failed_files == ["c.bin"]
    assert not patcher.manifest_path.exists()


# --------------------------------------------------------------------------- #
# ResourceManager
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_manager_check_counts(tmp_path: Path) -> None:
    """check_resources 对正常 / 缺失 / 损坏文件计数正确。"""
    good_data = b"hello"
    file_good = make_file("a.bin", good_data)
    file_missing = make_file("b.bin", b"missing!")
    file_corrupt = make_file("c.bin", b"corrupted-data")
    manifest = make_manifest("1", [file_good, file_missing, file_corrupt])

    manager = ResourceManager(make_config(tmp_path), transport=FakeTransport(manifest))
    (manager.game_dir / "a.bin").write_bytes(good_data)
    (manager.game_dir / "c.bin").write_bytes(b"bad")

    result = await manager.check_resources()

    assert result.total_files == 3
    assert result.healthy_files == 1
    assert result.missing_files == 1
    assert result.corrupted_files == 1


@pytest.mark.asyncio
async def test_manager_check_uses_selected_server(tmp_path: Path) -> None:
    """server 参数透传到传输层；未知资源源不触发请求。"""
    manifest = make_manifest("1", [])
    transport = FakeTransport(manifest)
    manager = ResourceManager(make_config(tmp_path), transport=transport)

    await manager.check_resources("oversea_legacy")
    await manager.check_resources("does-not-exist")

    assert transport.calls == ["oversea_legacy"]


@pytest.mark.asyncio
async def test_manager_update_up_to_date(tmp_path: Path) -> None:
    """版本未变且 force=False 时 downloaded_files == 0。"""
    file_a = make_file("a.bin", b"hello")
    manifest = make_manifest("1.2.3", [file_a])
    manager = ResourceManager(make_config(tmp_path), transport=FakeTransport(manifest))
    manager.patcher.save_manifest(manifest)

    result = await manager.update_resources(force=False)

    assert result.success is True
    assert result.downloaded_files == 0
    assert result.updated_files == 0


@pytest.mark.asyncio
async def test_manager_update_manifest_failure_is_explicit(tmp_path: Path) -> None:
    """清单拉取失败时 success=False 且 error 明确，不与「无更新」混淆。"""
    manager = ResourceManager(make_config(tmp_path), transport=FakeTransport(None))

    result = await manager.update_resources()

    assert result.success is False
    assert result.error
    assert result.downloaded_files == 0


@pytest.mark.asyncio
async def test_manager_auto_prefers_fresh_local_manifest(tmp_path: Path) -> None:
    """auto 模式下未过期的本地清单优先，不构造 HTTP 传输层。"""
    file_a = make_file("a.bin", b"hello")
    local = make_manifest("1", [file_a])
    manager = ResourceManager(make_config(tmp_path), source="auto")
    manager.patcher.save_manifest(local)
    (manager.game_dir / "a.bin").write_bytes(b"hello")

    def fail_build() -> FakeTransport:
        raise AssertionError("不应回落到 HTTP 索引")

    manager._build_transport = fail_build  # type: ignore[method-assign]

    result = await manager.check_resources()

    assert result.total_files == 1
    assert result.healthy_files == 1


@pytest.mark.asyncio
async def test_manager_auto_falls_back_when_local_manifest_stale(
    tmp_path: Path,
) -> None:
    """本地清单过期时回落到传输层拉取新清单。"""
    stale = make_manifest("1", [make_file("old.bin", b"old")])
    remote = make_manifest("2", [make_file("new.bin", b"new")])
    manager = ResourceManager(make_config(tmp_path), source="auto")
    manager.patcher.save_manifest(stale)
    manifest_path = manager.patcher.manifest_path
    old_time = time.time() - 2 * 86400
    os.utime(manifest_path, (old_time, old_time))

    def build() -> FakeTransport:
        return FakeTransport(remote)

    manager._build_transport = build  # type: ignore[method-assign]

    result = await manager.check_resources()

    assert result.total_files == 1
    assert result.missing_files == 1


@pytest.mark.asyncio
async def test_manager_force_repairs_from_disk_state(tmp_path: Path) -> None:
    """force=True 时按磁盘现状重建下载计划，修复损坏与缺失文件。"""
    good_data = b"good"
    bad_data = b"bad!!"
    missing_data = b"new!!"
    remote = make_manifest(
        "2",
        [
            make_file("a.bin", good_data),
            make_file("b.bin", bad_data),
            make_file("c.bin", missing_data),
        ],
    )
    manager = ResourceManager(make_config(tmp_path), transport=FakeTransport(remote))
    (manager.game_dir / "a.bin").write_bytes(good_data)
    (manager.game_dir / "b.bin").write_bytes(b"broken")
    factory, _stats = make_session_factory(
        {
            "https://example.test/v1/b.bin": bad_data,
            "https://example.test/v1/c.bin": missing_data,
        }
    )
    manager.downloader = Downloader(retries=1, retry_backoff=0, session_factory=factory)

    result = await manager.update_resources(force=True)

    assert result.success is True
    assert result.downloaded_files == 2
    assert result.updated_files == 1
    assert result.total_size == len(bad_data) + len(missing_data)
    assert (manager.game_dir / "b.bin").read_bytes() == bad_data
    assert (manager.game_dir / "c.bin").read_bytes() == missing_data


def test_manager_get_cache_info(tmp_path: Path) -> None:
    """get_cache_info 返回原始字节与人类可读体积等键。"""
    manager = ResourceManager(
        make_config(tmp_path), transport=FakeTransport(make_manifest("1", []))
    )
    (manager.cache_dir / "x.bin").write_bytes(b"1234")
    (manager.game_dir / "y.bin").write_bytes(b"123456")

    info = manager.get_cache_info()

    assert info["cache_size"] == 4
    assert info["cache_files"] == 1
    assert info["game_size"] == 6
    assert info["game_files"] == 1
    assert info["cache_size_human"] == "4.00 B"
    assert info["game_size_human"] == "6.00 B"
    assert info["cache_dir"] == str(manager.cache_dir)
    assert info["game_dir"] == str(manager.game_dir)


def test_manager_clean_cache_all(tmp_path: Path) -> None:
    """clean_cache(all_files=True) 清空缓存目录。"""
    manager = ResourceManager(
        make_config(tmp_path), transport=FakeTransport(make_manifest("1", []))
    )
    nested = manager.cache_dir / "sub"
    nested.mkdir()
    (nested / "x.bin").write_bytes(b"1")

    assert manager.clean_cache(all_files=True) is True
    assert list(manager.cache_dir.iterdir()) == []


def test_manager_clean_cache_temp_files(tmp_path: Path) -> None:
    """clean_cache(all_files=False) 清理 .part / .tmp 临时文件。"""
    manager = ResourceManager(
        make_config(tmp_path), transport=FakeTransport(make_manifest("1", []))
    )
    (manager.game_dir / "a.bin.part").write_bytes(b"1")
    (manager.game_dir / "b.tmp").write_bytes(b"1")
    (manager.game_dir / "keep.bin").write_bytes(b"1")

    assert manager.clean_cache(all_files=False) is True
    assert not (manager.game_dir / "a.bin.part").exists()
    assert not (manager.game_dir / "b.tmp").exists()
    assert (manager.game_dir / "keep.bin").exists()
