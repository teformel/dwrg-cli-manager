"""
工具模块单元测试

覆盖 :mod:`dwrg_manager.utils` 下 logger / system / version / network 的纯逻辑：
日志初始化、系统信息格式化、进程与命令封装、版本转发以及网络请求的异常包装。
所有网络与子进程调用均被替换为测试替身。
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiohttp
import pytest

from dwrg_manager import __version__
from dwrg_manager.exceptions import ServerError
from dwrg_manager.utils import logger as logger_module
from dwrg_manager.utils import network as network_module
from dwrg_manager.utils import system as system_module
from dwrg_manager.utils import updater as updater_module
from dwrg_manager.utils.logger import default_log_file, get_logger, setup_logging
from dwrg_manager.utils.network import (
    _timeout,
    check_server_status,
    detect_game_version,
    detect_server_region,
    fetch_json,
    ping_server,
)
from dwrg_manager.utils.system import SystemManager
from dwrg_manager.utils.updater import (
    STATUS_OUTDATED,
    STATUS_UNKNOWN,
    STATUS_UP_TO_DATE,
    UPGRADE_COMMANDS,
    WAIT_TIMEOUT,
    UpdateChecker,
    _is_prerelease,
    _normalize,
    build_upgrade_hint,
    check_latest_version,
    check_latest_version_async,
)
from dwrg_manager.utils.version import get_version


@pytest.mark.unit
class TestLoggerSetup:
    """日志初始化与获取。"""

    def test_setup_logging_returns_configured_logger(self, tmp_path: Path) -> None:
        """初始化应返回带文件处理器的根日志器。"""
        log_file = tmp_path / "dwrg.log"

        logger = setup_logging(level="DEBUG", log_file=log_file, force=True)

        assert logger.name == logger_module.ROOT_LOGGER_NAME
        assert logger.handlers
        assert log_file.exists()

    def test_setup_logging_with_empty_path_disables_file_handler(
        self, tmp_path: Path
    ) -> None:
        """传入空字符串应关闭文件日志。"""
        log_file = tmp_path / "dwrg.log"
        setup_logging(log_file=log_file, force=True)

        logger = setup_logging(log_file="", force=True)

        assert logger.handlers == []

    def test_setup_logging_is_idempotent_without_force(self, tmp_path: Path) -> None:
        """重复调用不应重复挂载处理器。"""
        log_file = tmp_path / "dwrg.log"
        first = setup_logging(log_file=log_file, force=True)
        handler_count = len(first.handlers)

        second = setup_logging(log_file=log_file)

        assert second is first
        assert len(second.handlers) == handler_count

    def test_get_logger_returns_named_logger(self) -> None:
        """``get_logger`` 应返回对应名称的日志器。"""
        logger = get_logger("dwrg.tests")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "dwrg.tests"

    def test_default_log_file_points_into_dwrg_dir(self) -> None:
        """默认日志文件应位于 ``.dwrg/logs`` 之下。"""
        path = default_log_file()

        assert path.name == "dwrg.log"
        assert path.parent.name == "logs"


@pytest.mark.unit
class TestSystemInfo:
    """系统信息采集与格式化。"""

    def test_get_system_info_contains_core_keys(self) -> None:
        """系统信息应包含平台与 Python 版本等键。"""
        info = SystemManager().get_system_info()

        assert "system" in info
        assert "python_version" in info
        assert "hostname" in info

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0.00 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024**3, "1.00 GB"),
        ],
    )
    def test_format_bytes_scales_units(self, value: int, expected: str) -> None:
        """字节格式化应按 1024 进制切换单位。"""
        assert SystemManager._format_bytes(value) == expected

    def test_get_memory_info_contains_expected_keys(self) -> None:
        """内存信息应包含总量与可用量。"""
        info = SystemManager().get_memory_info()

        assert {"total", "available", "used", "percent"} <= set(info)

    def test_get_disk_info_returns_list(self) -> None:
        """磁盘信息应返回列表。"""
        assert isinstance(SystemManager().get_disk_info(), list)

    def test_get_network_interfaces_returns_list(self) -> None:
        """网络接口应返回列表。"""
        assert isinstance(SystemManager().get_network_interfaces(), list)


@pytest.mark.unit
class TestFileHelpers:
    """文件相关辅助方法。"""

    def test_create_directory_is_recursive(self, tmp_path: Path) -> None:
        """应递归创建目录。"""
        target = tmp_path / "a" / "b"

        assert SystemManager().create_directory(target) is True
        assert target.is_dir()

    def test_file_exists_detects_presence(self, tmp_path: Path) -> None:
        """存在性判断应准确。"""
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")

        manager = SystemManager()
        assert manager.file_exists(target) is True
        assert manager.file_exists(tmp_path / "nope") is False

    def test_file_size_returns_zero_for_missing(self, tmp_path: Path) -> None:
        """缺失文件的大小应为 0。"""
        assert SystemManager().file_size(tmp_path / "nope") == 0

    def test_file_size_returns_byte_count(self, tmp_path: Path) -> None:
        """应返回真实字节数。"""
        target = tmp_path / "f.txt"
        target.write_text("hello", encoding="utf-8")

        assert SystemManager().file_size(target) == 5

    def test_get_file_info_reports_flags(self, tmp_path: Path) -> None:
        """文件信息应包含类型标记。"""
        target = tmp_path / "f.txt"
        target.write_text("hello", encoding="utf-8")

        info = SystemManager().get_file_info(target)

        assert info["is_file"] is True
        assert info["is_dir"] is False
        assert info["size_bytes"] == 5

    def test_get_file_info_returns_empty_for_missing(self, tmp_path: Path) -> None:
        """缺失路径应返回空字典。"""
        assert SystemManager().get_file_info(tmp_path / "nope") == {}


class _FakeIterProc:
    """``psutil.process_iter`` 元素的测试替身。"""

    def __init__(self, info: dict[str, Any]) -> None:
        """保存进程信息。

        Args:
            info: 进程信息字典。
        """
        self.info = info


@pytest.mark.unit
class TestProcessHelpers:
    """进程查询与终止。"""

    def test_get_process_info_filters_by_name_case_insensitively(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """进程名过滤应忽略大小写。"""

        def fake_process_iter(fields: list[str]) -> list[_FakeIterProc]:
            _ = fields
            return [
                _FakeIterProc(
                    {
                        "pid": 1,
                        "name": "IdentityV.exe",
                        "username": "u",
                        "memory_percent": 1.0,
                        "cpu_percent": 2.0,
                    }
                ),
                _FakeIterProc(
                    {
                        "pid": 2,
                        "name": "other.exe",
                        "username": "u",
                        "memory_percent": 0.0,
                        "cpu_percent": 0.0,
                    }
                ),
            ]

        monkeypatch.setattr(system_module.psutil, "process_iter", fake_process_iter)

        processes = SystemManager().get_process_info("identityv.exe")

        assert [item["pid"] for item in processes] == [1]

    def test_check_game_process_returns_first_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """命中游戏进程时应返回其信息。"""
        manager = SystemManager()
        monkeypatch.setattr(
            manager, "get_process_info", lambda name=None: [{"pid": 7, "name": name}]
        )

        assert manager.check_game_process() == {"pid": 7, "name": "IdentityV.exe"}

    def test_check_game_process_returns_none_when_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """没有匹配进程时返回 ``None``。"""
        manager = SystemManager()
        monkeypatch.setattr(manager, "get_process_info", lambda name=None: [])

        assert manager.check_game_process() is None

    def test_kill_process_returns_true_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """成功发出终止信号时返回 ``True``。"""
        fake = SimpleNamespace(kill=lambda: None, terminate=lambda: None)
        monkeypatch.setattr(
            system_module.psutil,
            "Process",
            lambda pid: fake,  # noqa: ARG005
        )

        assert SystemManager().kill_process(1234) is True

    def test_kill_process_returns_false_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """进程不存在时返回 ``False``。"""

        def raising(pid: int) -> Any:
            raise system_module.psutil.NoSuchProcess(pid)

        monkeypatch.setattr(system_module.psutil, "Process", raising)

        assert SystemManager().kill_process(1234) is False

    def test_kill_process_returns_false_when_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """权限不足时返回 ``False``。"""

        def raising(pid: int) -> Any:
            raise system_module.psutil.AccessDenied(pid)

        monkeypatch.setattr(system_module.psutil, "Process", raising)

        assert SystemManager().kill_process(1234) is False


@pytest.mark.unit
class TestRunCommandAndPort:
    """外部命令执行与端口探测。"""

    def test_run_command_returns_output_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """命令成功时返回 stdout/stderr/returncode。"""
        monkeypatch.setattr(
            system_module.subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(stdout="ok", stderr="", returncode=0),
        )

        result = SystemManager().run_command(["echo", "ok"])

        assert result["stdout"] == "ok"
        assert result["returncode"] == 0

    def test_run_command_reports_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """命令超时应返回错误字典。"""

        def raising(*_args: Any, **_kwargs: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd="slow", timeout=1)

        monkeypatch.setattr(system_module.subprocess, "run", raising)

        assert SystemManager().run_command(["slow"]) == {"error": "命令执行超时"}

    def test_run_command_reports_called_process_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """非零退出码应返回错误字典并保留返回码。"""

        def raising(*_args: Any, **_kwargs: Any) -> Any:
            raise subprocess.CalledProcessError(returncode=3, cmd=["bad"])

        monkeypatch.setattr(system_module.subprocess, "run", raising)

        result = SystemManager().run_command(["bad"])

        assert result["returncode"] == 3

    def test_check_port_returns_boolean(self) -> None:
        """端口探测应返回布尔值。"""
        assert isinstance(SystemManager().check_port(0), bool)


@pytest.mark.unit
class TestVersion:
    """版本号转发。"""

    def test_get_version_matches_package_version(self) -> None:
        """版本号应与包根 ``__version__`` 一致。"""
        assert get_version() == __version__


@pytest.mark.unit
class TestUpdateChecker:
    """自更新检查的版本比较与静默降级。"""

    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("1.2.3", (1, 2, 3)),
            ("v2.0", (2, 0, 0)),
            ("1.2.3rc1", (1, 2, 3)),
            ("10.20.30", (10, 20, 30)),
            ("abc", (0, 0, 0)),
        ],
    )
    def test_normalize(self, version: str, expected: tuple[int, ...]) -> None:
        """版本号应解析为三段整数元组，解析失败回落为零。"""
        assert _normalize(version) == expected

    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("1.0.0", False),
            ("2.3.4", False),
            ("1.0.0rc1", True),
            ("1.0.0b2", True),
            ("1.0.0.dev3", True),
        ],
    )
    def test_is_prerelease(self, version: str, expected: bool) -> None:
        """含预发布标记的版本应被识别。"""
        assert _is_prerelease(version) is expected

    def test_check_detects_outdated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PyPI 版本更高时应报告 ``outdated``。"""
        patch_pypi(monkeypatch, payload={"info": {"version": "1.1.0"}})

        info = UpdateChecker(current="1.0.0").check()

        assert info.status == STATUS_OUTDATED
        assert info.latest == "1.1.0"
        assert info.has_update is True

    def test_check_reports_up_to_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """版本相同应报告 ``up-to-date``。"""
        patch_pypi(monkeypatch, payload={"info": {"version": "1.0.0"}})

        info = UpdateChecker(current="1.0.0").check()

        assert info.status == STATUS_UP_TO_DATE
        assert info.has_update is False

    def test_check_degrades_when_offline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """网络异常应静默降级为 ``unknown``，不抛异常。"""
        patch_pypi(monkeypatch, error=OSError("offline"))

        info = UpdateChecker(current="1.0.0").check()

        assert info.status == STATUS_UNKNOWN
        assert info.latest is None
        assert info.has_update is False

    def test_check_marks_prerelease_as_no_update(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """最新版是预发布时不提示升级。"""
        patch_pypi(monkeypatch, payload={"info": {"version": "2.0.0rc1"}})

        info = UpdateChecker(current="1.0.0").check()

        assert info.status == STATUS_OUTDATED
        assert info.is_prerelease is True
        assert info.has_update is False

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {},
            {"info": None},
            {"info": {}},
            {"info": {"version": ""}},
            {"info": {"version": 123}},
        ],
    )
    def test_malformed_payload_is_unknown(
        self, monkeypatch: pytest.MonkeyPatch, payload: Any
    ) -> None:
        """响应结构不符合预期时按未知处理。"""
        patch_pypi(monkeypatch, payload=payload)

        assert UpdateChecker(current="1.0.0").check().status == STATUS_UNKNOWN

    def test_check_latest_version_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """便捷函数应同步等待后台查询结果。"""
        patch_pypi(monkeypatch, payload={"info": {"version": "2.0.0"}})

        info = check_latest_version(current="1.0.0")

        assert info.status == STATUS_OUTDATED
        assert info.latest == "2.0.0"

    def test_start_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """重复 ``start`` 返回同一个线程。"""
        patch_pypi(monkeypatch, payload={"info": {"version": "1.0.0"}})
        checker = UpdateChecker(current="1.0.0")

        first = checker.start()
        second = checker.start()

        assert first is second
        assert checker.wait().status == STATUS_UP_TO_DATE

    def test_wait_returns_unknown_after_timeout(self) -> None:
        """线程未在限定时间内完成时返回 ``unknown``。"""
        checker = UpdateChecker(current="1.0.0")
        stuck = _StuckThread()
        checker._thread = stuck  # type: ignore[assignment]

        info = checker.wait()

        assert stuck.timeout == WAIT_TIMEOUT
        assert info.status == STATUS_UNKNOWN

    def test_async_helper_returns_started_checker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """异步入口应立即返回已启动的检查器。"""
        patch_pypi(monkeypatch, payload={"info": {"version": "1.0.0"}})

        checker = check_latest_version_async(current="1.0.0")

        assert isinstance(checker, UpdateChecker)
        assert checker.wait().status == STATUS_UP_TO_DATE

    def test_default_current_uses_package_version(self) -> None:
        """未显式传版本时应读取包内版本号。"""
        assert UpdateChecker().current == __version__

    def test_build_upgrade_hint_returns_copy(self) -> None:
        """升级提示应返回副本，修改结果不影响全局常量。"""
        hint = build_upgrade_hint()
        assert hint == list(UPGRADE_COMMANDS)

        hint.clear()
        assert build_upgrade_hint() == list(UPGRADE_COMMANDS)


@pytest.mark.unit
class TestNetworkHelpers:
    """网络工具的纯逻辑与异常包装。"""

    def test_timeout_builds_client_timeout(self) -> None:
        """应构造携带 total 的 ``ClientTimeout``。"""
        assert _timeout(7).total == 7

    def test_fetch_json_returns_parsed_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """200 响应应返回解析后的 JSON。"""
        response = _FakeResponse(status=200, payload={"status": "ok"})
        monkeypatch.setattr(
            network_module.aiohttp,
            "ClientSession",
            lambda *_a, **_k: _FakeSession(response),
        )

        assert await_result(fetch_json("https://example.com")) == {"status": "ok"}

    def test_fetch_json_rejects_non_200_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """非 200 状态码应抛出 :class:`ServerError`。"""
        response = _FakeResponse(status=500, payload={})
        monkeypatch.setattr(
            network_module.aiohttp,
            "ClientSession",
            lambda *_a, **_k: _FakeSession(response),
        )

        with pytest.raises(ServerError):
            await_result(fetch_json("https://example.com"))

    def test_fetch_json_wraps_client_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """底层网络异常应包装为 :class:`ServerError`。"""
        response = _FakeResponse(status=200, error=aiohttp.ClientError("boom"))
        monkeypatch.setattr(
            network_module.aiohttp,
            "ClientSession",
            lambda *_a, **_k: _FakeSession(response),
        )

        with pytest.raises(ServerError):
            await_result(fetch_json("https://example.com"))

    def test_fetch_json_wraps_parse_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON 解析失败应包装为 :class:`ServerError`。"""
        response = _FakeResponse(status=200, json_error=ValueError("bad json"))
        monkeypatch.setattr(
            network_module.aiohttp,
            "ClientSession",
            lambda *_a, **_k: _FakeSession(response),
        )

        with pytest.raises(ServerError):
            await_result(fetch_json("https://example.com"))

    def test_check_server_status_rejects_non_mapping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """状态接口返回非对象时应抛出 :class:`ServerError`。"""

        async def fake_fetch(url: str, timeout: int = 10) -> Any:
            _ = (url, timeout)
            return ["not", "a", "dict"]

        monkeypatch.setattr(network_module, "fetch_json", fake_fetch)

        with pytest.raises(ServerError):
            await_result(check_server_status("https://example.com"))

    def test_check_server_status_returns_mapping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """状态接口返回对象时应原样返回。"""

        async def fake_fetch(url: str, timeout: int = 10) -> Any:
            _ = (url, timeout)
            return {"status": "active"}

        monkeypatch.setattr(network_module, "fetch_json", fake_fetch)

        assert await_result(check_server_status("https://x")) == {"status": "active"}

    def test_detect_game_version_returns_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """版本接口返回版本号时应透出。"""

        async def fake_fetch(url: str, timeout: int = 10) -> Any:
            _ = (url, timeout)
            return {"version": "2.3.4"}

        monkeypatch.setattr(network_module, "fetch_json", fake_fetch)

        assert await_result(detect_game_version("https://x")) == "2.3.4"

    def test_detect_game_version_falls_back_to_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """缺少版本字段时应回退为 ``unknown``。"""

        async def fake_fetch(url: str, timeout: int = 10) -> Any:
            _ = (url, timeout)
            return {}

        monkeypatch.setattr(network_module, "fetch_json", fake_fetch)

        assert await_result(detect_game_version("https://x")) == "unknown"

    def test_detect_server_region_returns_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """地区接口返回地区码时应透出。"""

        async def fake_fetch(url: str, timeout: int = 10) -> Any:
            _ = (url, timeout)
            return {"region": "CN"}

        monkeypatch.setattr(network_module, "fetch_json", fake_fetch)

        assert await_result(detect_server_region("https://x")) == "CN"

    def test_ping_server_returns_elapsed_milliseconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """成功请求应返回非负耗时。"""
        response = _FakeResponse(status=200, payload={})
        monkeypatch.setattr(
            network_module.aiohttp,
            "ClientSession",
            lambda *_a, **_k: _FakeSession(response),
        )

        elapsed = await_result(ping_server("https://x"))

        assert elapsed >= 0.0

    def test_ping_server_wraps_client_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """连接失败应包装为 :class:`ServerError`。"""
        response = _FakeResponse(status=200, error=aiohttp.ClientError("down"))
        monkeypatch.setattr(
            network_module.aiohttp,
            "ClientSession",
            lambda *_a, **_k: _FakeSession(response),
        )

        with pytest.raises(ServerError):
            await_result(ping_server("https://x"))


class _FakeResponse:
    """``aiohttp`` 响应对象的测试替身。"""

    def __init__(
        self,
        *,
        status: int,
        payload: Any = None,
        error: BaseException | None = None,
        json_error: BaseException | None = None,
        body: bytes = b"",
    ) -> None:
        """初始化假响应。

        Args:
            status: HTTP 状态码。
            payload: ``json()`` 返回的对象。
            error: 进入上下文时抛出的异常（用于模拟连接失败）。
            json_error: ``json()`` 调用时抛出的异常（用于模拟解析失败）。
            body: ``read()`` 返回的字节串。
        """
        self.status = status
        self._payload = payload
        self._error = error
        self._json_error = json_error
        self._body = body

    async def __aenter__(self) -> "_FakeResponse":
        """进入上下文；若配置了异常则抛出。"""
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        """退出上下文，不吞异常。"""
        return False

    async def json(self, content_type: str | None = None) -> Any:
        """返回预置的 JSON 负载。

        Args:
            content_type: 忽略。

        Returns:
            预置负载。

        Raises:
            配置了 ``json_error`` 时抛出该异常。
        """
        _ = content_type
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    async def read(self) -> bytes:
        """返回预置的响应体。"""
        return self._body


class _FakeSession:
    """``aiohttp.ClientSession`` 的测试替身。"""

    def __init__(self, response: _FakeResponse) -> None:
        """保存要返回的响应。

        Args:
            response: 假响应对象。
        """
        self._response = response

    async def __aenter__(self) -> "_FakeSession":
        """进入上下文。"""
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        """退出上下文。"""
        return False

    def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
        """返回预置响应。

        Returns:
            假响应对象。
        """
        return self._response


class _FakePypiResponse:
    """``urllib.request.urlopen`` 返回对象的测试替身。"""

    def __init__(self, payload: Any) -> None:
        """保存要序列化为 JSON 的响应体。

        Args:
            payload: 任意可 JSON 序列化的对象。
        """
        self._payload = payload

    def __enter__(self) -> "_FakePypiResponse":
        """进入上下文。"""
        return self

    def __exit__(self, *_exc: object) -> bool:
        """退出上下文。"""
        return False

    def read(self) -> bytes:
        """返回 JSON 编码后的字节串。"""
        return json.dumps(self._payload).encode("utf-8")


class _StuckThread:
    """永不完成的假线程，用于覆盖 ``wait`` 的超时分支。"""

    def __init__(self) -> None:
        self.timeout: float | None = None

    def join(self, timeout: float | None = None) -> None:
        """记录调用方传入的超时，并立即返回。

        Args:
            timeout: ``wait`` 传入的等待上限。
        """
        self.timeout = timeout


def patch_pypi(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: Any = None,
    error: BaseException | None = None,
) -> None:
    """把 PyPI 查询替换为本地假响应。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        payload: 假响应 JSON；``error`` 非空时忽略。
        error: 模拟网络异常时抛出的异常对象。
    """

    def fake_urlopen(_request: Any, timeout: float | None = None) -> Any:
        _ = timeout
        if error is not None:
            raise error
        return _FakePypiResponse(payload)

    monkeypatch.setattr(updater_module.urllib.request, "urlopen", fake_urlopen)


def await_result(coro: Any) -> Any:
    """以同步方式运行一个协程。

    借助 ``asyncio.run`` 执行，避免测试函数被 pytest-asyncio 收集为异步用例。

    Args:
        coro: 待执行的协程对象。

    Returns:
        协程的返回值。

    Raises:
        协程内部抛出的任何异常。
    """
    return asyncio.run(coro)
