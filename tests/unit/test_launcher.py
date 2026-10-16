"""
启动管理单元测试

覆盖 :mod:`dwrg_manager.launcher.models` 的 ``LaunchConfig`` / ``LaunchResult``
/ ``GameStatus`` 以及 :class:`dwrg_manager.launcher.manager.LauncherManager`
的路径解析、命令构造、启动、停止与状态查询。所有 ``subprocess.Popen`` 与
``psutil.Process`` 均被替换为测试替身，不会真正启动任何进程。
"""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil
import pytest
from pydantic import ValidationError as PydanticValidationError

from dwrg_manager.config import ConfigManager
from dwrg_manager.exceptions import LaunchError
from dwrg_manager.launcher import (
    GameStatus,
    LaunchConfig,
    LauncherManager,
    LaunchResult,
)
from dwrg_manager.launcher import manager as launcher_manager_module
from dwrg_manager.launcher.manager import default_game_candidates
from dwrg_manager.utils.system import SystemManager


class _FakeProcess:
    """``psutil.Process`` 的测试替身。"""

    def __init__(
        self, pid: int = 4321, *, running: bool = True, fail: bool = False
    ) -> None:
        """初始化替身进程。

        Args:
            pid: 进程 ID。
            running: ``is_running`` 的返回值。
            fail: 为 ``True`` 时 ``terminate`` / ``kill`` 抛出 ``NoSuchProcess``。
        """
        self.pid = pid
        self._running = running
        self._fail = fail
        self.terminated = False
        self.killed = False

    def is_running(self) -> bool:
        """返回进程是否运行中。"""
        return self._running

    def memory_info(self) -> Any:
        """返回伪造的内存信息。"""
        return SimpleNamespace(rss=104_857_600)

    def cpu_percent(self) -> float:
        """返回伪造的 CPU 占用率。"""
        return 5.0

    def terminate(self) -> None:
        """记录优雅终止。"""
        if self._fail:
            raise psutil.NoSuchProcess(self.pid)
        self.terminated = True

    def kill(self) -> None:
        """记录强制终止。"""
        if self._fail:
            raise psutil.NoSuchProcess(self.pid)
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        """模拟等待退出。"""
        _ = timeout
        return 0


class _FakePopen:
    """``subprocess.Popen`` 的测试替身。"""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """忽略参数并给出固定的进程 ID。"""
        self.pid = 4321


@pytest.fixture
def launcher(config_manager: ConfigManager) -> LauncherManager:
    """返回绑定隔离配置的启动管理器。

    Args:
        config_manager: 隔离的配置管理器。

    Returns:
        :class:`LauncherManager` 实例。
    """
    return LauncherManager(config_manager, SystemManager())


@pytest.mark.unit
class TestLauncherModels:
    """启动相关模型的字段约束。"""

    def test_launch_config_defaults(self) -> None:
        """默认值应与文档一致。"""
        config = LaunchConfig()

        assert config.account_id is None
        assert config.server_name is None
        assert config.priority == "normal"
        assert config.launch_params == []

    def test_launch_config_normalizes_priority_case(self) -> None:
        """优先级应被规范化为小写。"""
        assert LaunchConfig(priority="HIGH").priority == "high"

    def test_launch_config_with_invalid_priority_raises_validation_error(self) -> None:
        """非法优先级应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            LaunchConfig(priority="turbo")

    def test_launch_result_defaults(self) -> None:
        """失败结果除 ``success`` 外均有默认值。"""
        result = LaunchResult(success=False)

        assert result.process_id is None
        assert result.error_message is None

    def test_game_status_defaults(self) -> None:
        """未运行状态应填充零值。"""
        status = GameStatus(is_running=False)

        assert status.process_id is None
        assert status.cpu_usage == 0.0
        assert status.memory_usage == 0


@pytest.mark.unit
class TestGamePathResolution:
    """``_get_game_path`` 与默认候选路径。"""

    def test_default_candidates_are_paths(self) -> None:
        """候选列表应全部为 ``Path``。"""
        candidates = default_game_candidates()

        assert candidates
        assert all(isinstance(item, Path) for item in candidates)

    def test_get_game_path_prefers_explicit_config(
        self, launcher: LauncherManager, tmp_path: Path
    ) -> None:
        """显式配置的路径优先级最高。"""
        explicit = tmp_path / "custom.exe"
        config = LaunchConfig(game_path=str(explicit))

        assert launcher._get_game_path(config) == explicit

    def test_get_game_path_reads_environment_variable(
        self, launcher: LauncherManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无显式配置时读取环境变量。"""
        env_exe = tmp_path / "env.exe"
        monkeypatch.setenv(launcher_manager_module.ENV_GAME_PATH, str(env_exe))

        assert launcher._get_game_path(None) == env_exe

    def test_get_game_path_returns_none_when_no_candidate(
        self, launcher: LauncherManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """既无显式路径也无命中候选时返回 ``None``。"""
        monkeypatch.delenv(launcher_manager_module.ENV_GAME_PATH, raising=False)
        monkeypatch.setattr(
            launcher_manager_module, "default_game_candidates", lambda: []
        )

        assert launcher._get_game_path(None) is None


@pytest.mark.unit
class TestCommandBuilding:
    """命令与环境的构造。"""

    def test_build_launch_command_contains_params_and_targets(
        self, launcher: LauncherManager
    ) -> None:
        """命令应包含默认参数、账号与渠道服。"""
        launcher._prepare_launch_config(None, None)

        cmd = launcher._build_launch_command(Path("g.exe"), "acc-1", "official")

        assert cmd[0] == "g.exe"
        assert "-account" in cmd
        assert "acc-1" in cmd
        assert "-server" in cmd
        assert "official" in cmd

    def test_build_environment_marks_launch_context(
        self, launcher: LauncherManager
    ) -> None:
        """环境变量应包含启动标记与账号/渠道服。"""
        launcher._prepare_launch_config(None, None)
        launcher.launch_config.account_id = "acc-1"
        launcher.launch_config.server_name = "official"

        env = launcher._build_environment()

        assert env["DWRG_LAUNCHED"] == "1"
        assert env["DWRG_ACCOUNT"] == "acc-1"
        assert env["DWRG_SERVER"] == "official"


@pytest.mark.unit
class TestPrepareConfig:
    """``_prepare_launch_config`` 的校验。"""

    def test_prepare_uses_current_configuration(
        self, launcher: LauncherManager
    ) -> None:
        """未指定账号/渠道服时沿用配置中的当前项。"""
        config = launcher._prepare_launch_config(None, None)

        assert config.server_name == "official"
        assert config.account_id is None

    def test_prepare_with_unknown_account_raises_launch_error(
        self, launcher: LauncherManager
    ) -> None:
        """未知账号应抛出 :class:`LaunchError`。"""
        with pytest.raises(LaunchError):
            launcher._prepare_launch_config("nope", None)

    def test_prepare_with_unknown_server_raises_launch_error(
        self, launcher: LauncherManager
    ) -> None:
        """未知渠道服应抛出 :class:`LaunchError`。"""
        with pytest.raises(LaunchError):
            launcher._prepare_launch_config(None, "nope")


@pytest.mark.unit
class TestLaunch:
    """``launch`` / ``launch_game`` 的结果。"""

    def test_launch_reports_failure_when_game_missing(
        self, launcher: LauncherManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """找不到可执行文件时应返回失败结果而非抛异常。"""
        missing = tmp_path / "missing.exe"
        monkeypatch.setattr(launcher, "_get_game_path", lambda *_a, **_k: missing)

        result = launcher.launch()

        assert result.success is False
        assert "游戏可执行文件不存在" in (result.error_message or "")
        assert "DWRG_GAME_PATH" in (result.error_message or "")

    def test_launch_returns_failure_on_launch_error(
        self, launcher: LauncherManager, config_manager: ConfigManager
    ) -> None:
        """配置校验失败应被捕获并转为失败结果。"""
        config_manager.config.app.account = "nope"

        result = launcher.launch()

        assert result.success is False
        assert result.error_message is not None

    def test_launch_succeeds_with_mocked_process(
        self,
        launcher: LauncherManager,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """在替身进程下应返回成功结果并记录进程。"""
        exe = tmp_path / "game.exe"
        exe.write_text("stub", encoding="utf-8")
        monkeypatch.setenv(launcher_manager_module.ENV_GAME_PATH, str(exe))
        monkeypatch.setattr(launcher_manager_module.subprocess, "Popen", _FakePopen)
        monkeypatch.setattr(
            launcher_manager_module.psutil, "Process", lambda pid: _FakeProcess(pid)
        )

        result = launcher.launch()

        assert result.success is True
        assert result.process_id == 4321
        assert launcher.start_time is not None

    def test_launch_game_delegates_to_launch(
        self, launcher: LauncherManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``launch_game`` 应返回 ``launch`` 的成功布尔值。"""
        missing = tmp_path / "missing.exe"
        monkeypatch.setattr(launcher, "_get_game_path", lambda *_a, **_k: missing)

        assert launcher.launch_game() is False


@pytest.mark.unit
class TestStopAndStatus:
    """``stop_game`` 与 ``get_game_status``。"""

    def test_stop_without_process_returns_true(self, launcher: LauncherManager) -> None:
        """未运行时视为停止成功。"""
        assert launcher.stop_game() is True

    def test_stop_terminates_running_process(self, launcher: LauncherManager) -> None:
        """优雅停止应调用 ``terminate``。"""
        fake = _FakeProcess()
        launcher.game_process = fake  # type: ignore[assignment]

        assert launcher.stop_game() is True
        assert fake.terminated is True
        assert launcher.game_process is None

    def test_stop_force_kills_running_process(self, launcher: LauncherManager) -> None:
        """强制停止应调用 ``kill``。"""
        fake = _FakeProcess()
        launcher.game_process = fake  # type: ignore[assignment]

        assert launcher.stop_game(force=True) is True
        assert fake.killed is True

    def test_stop_returns_false_when_process_disappears(
        self, launcher: LauncherManager
    ) -> None:
        """终止时进程消失应返回 ``False``。"""
        fake = _FakeProcess(fail=True)
        launcher.game_process = fake  # type: ignore[assignment]

        assert launcher.stop_game() is False

    def test_status_when_not_running(self, launcher: LauncherManager) -> None:
        """未启动时状态为未运行。"""
        status = launcher.get_game_status()

        assert status.is_running is False
        assert status.process_id is None

    def test_status_reports_running_process(self, launcher: LauncherManager) -> None:
        """运行中时应给出 PID 与资源占用。"""
        launcher.game_process = _FakeProcess(pid=99)  # type: ignore[assignment]
        launcher.start_time = datetime.now()

        status = launcher.get_game_status()

        assert status.is_running is True
        assert status.process_id == 99
        assert status.memory_usage == 104_857_600


@pytest.mark.unit
class TestDiagnoseLaunch:
    """``diagnose_launch`` 的诊断字典。"""

    def test_diagnose_reports_missing_game_and_low_disk(
        self, launcher: LauncherManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """缺少客户端且磁盘不足时应给出建议。"""
        monkeypatch.setattr(launcher, "_get_game_path", lambda *_a, **_k: None)
        monkeypatch.setattr(
            launcher.system_manager, "free_space_bytes", lambda *_a: 1024
        )

        report = launcher.diagnose_launch()

        assert report["game_exists"] is False
        assert report["disk_space"] is False
        assert report["recommendations"]

    def test_diagnose_reports_healthy_environment(
        self, launcher: LauncherManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """磁盘充足且渠道服有效时应标记为通过。"""
        exe = tmp_path / "game.exe"
        exe.write_text("stub", encoding="utf-8")
        monkeypatch.setattr(launcher, "_get_game_path", lambda *_a, **_k: exe)
        monkeypatch.setattr(
            launcher.system_manager,
            "free_space_bytes",
            lambda *_a: 20 * 1024**3,
        )

        report = launcher.diagnose_launch()

        assert report["game_exists"] is True
        assert report["disk_space"] is True
        assert report["server_valid"] is True
