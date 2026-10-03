"""
渠道服管理单元测试

覆盖 :mod:`dwrg_manager.servers.models` 的 ``ServerStatus`` / ``ServerManagerConfig``
以及 :class:`dwrg_manager.servers.manager.ServerManager` 的 CRUD 与异步探测。
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from dwrg_manager.exceptions import ConfigError, ServerError
from dwrg_manager.servers import (
    ServerConfig,
    ServerManager,
    ServerManagerConfig,
    ServerStatus,
)
from dwrg_manager.servers import manager as servers_manager_module


@pytest.mark.unit
class TestServerModels:
    """``ServerStatus`` 与 ``ServerManagerConfig`` 的字段约束。"""

    def test_status_defaults_fill_optional_fields(self) -> None:
        """未提供的字段应取默认值。"""
        status = ServerStatus(name="official", status="active", ping=12.5)

        assert status.version == "1.0.0"
        assert status.players == 0

    def test_status_with_negative_players_raises_validation_error(self) -> None:
        """在线人数不能为负。"""
        with pytest.raises(PydanticValidationError):
            ServerStatus(name="official", status="active", ping=1.0, players=-1)

    def test_manager_config_defaults(self) -> None:
        """管理器配置默认值应与文档一致。"""
        config = ServerManagerConfig()

        assert config.auto_detect is True
        assert config.check_interval == 300
        assert config.timeout == 10
        assert config.preferred_servers == []

    def test_manager_config_with_small_interval_raises_validation_error(self) -> None:
        """检测间隔不得小于 10 秒。"""
        with pytest.raises(PydanticValidationError):
            ServerManagerConfig(check_interval=5)

    def test_manager_config_with_zero_timeout_raises_validation_error(self) -> None:
        """超时不得小于 1 秒。"""
        with pytest.raises(PydanticValidationError):
            ServerManagerConfig(timeout=0)


@pytest.mark.unit
class TestSynchronousCrud:
    """渠道服的同步增删改查。"""

    def test_list_servers_returns_sorted_defaults(
        self, server_manager: ServerManager
    ) -> None:
        """默认应返回排序后的内置渠道服。"""
        names = [server.name for server in server_manager.list_servers()]

        assert names == sorted(names)
        assert "official" in names

    def test_get_server_returns_none_for_unknown(
        self, server_manager: ServerManager
    ) -> None:
        """未知渠道服返回 ``None``。"""
        assert server_manager.get_server("nope") is None

    def test_get_current_server_returns_official(
        self, server_manager: ServerManager
    ) -> None:
        """默认当前渠道服为 ``official``。"""
        current = server_manager.get_current_server()

        assert current is not None
        assert current.name == "official"

    def test_add_server_returns_config(self, server_manager: ServerManager) -> None:
        """新增应返回创建好的配置对象。"""
        server = server_manager.add_server("guild", endpoint="https://g.example")

        assert isinstance(server, ServerConfig)
        assert server_manager.get_server("guild") is server

    def test_add_server_with_illegal_name_raises_config_error(
        self, server_manager: ServerManager
    ) -> None:
        """非法名称应触发配置异常。"""
        with pytest.raises(ConfigError):
            server_manager.add_server("bad name")

    def test_remove_server_returns_true_then_false(
        self, server_manager: ServerManager
    ) -> None:
        """删除返回布尔结果。"""
        server_manager.add_server("guild")

        assert server_manager.remove_server("guild") is True
        assert server_manager.remove_server("guild") is False

    def test_switch_server_returns_true_on_success(
        self, server_manager: ServerManager
    ) -> None:
        """切换到已存在渠道服返回 ``True`` 并更新当前项。"""
        assert server_manager.switch_server("bserver") is True
        assert server_manager.get_current_server().name == "bserver"

    def test_switch_server_returns_false_for_unknown(
        self, server_manager: ServerManager
    ) -> None:
        """切换到不存在渠道服返回 ``False`` 而不抛异常。"""
        assert server_manager.switch_server("nope") is False

    def test_set_default_is_alias_of_switch(
        self, server_manager: ServerManager
    ) -> None:
        """``set_default`` 应与 ``switch_server`` 行为一致。"""
        assert server_manager.set_default("test_server") is True
        assert server_manager.get_current_server().name == "test_server"


async def _fake_ping(endpoint: str, timeout: int = 10) -> float:
    """返回固定延迟的假探测函数。

    Args:
        endpoint: 目标地址（忽略）。
        timeout: 超时秒数（忽略）。

    Returns:
        固定延迟 12.5 毫秒。
    """
    _ = (endpoint, timeout)
    return 12.5


def _install_online_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """把网络探测替换为确定性的在线响应。

    Args:
        monkeypatch: pytest 补丁工具。
    """

    async def fake_status(endpoint: str, timeout: int = 10) -> dict[str, object]:
        _ = (endpoint, timeout)
        return {"status": "active", "version": "2.0.0", "players": 42}

    monkeypatch.setattr(servers_manager_module, "ping_server", _fake_ping)
    monkeypatch.setattr(servers_manager_module, "check_server_status", fake_status)


@pytest.mark.unit
class TestProbeServer:
    """``probe_server`` 的单点探测。"""

    async def test_probe_online_returns_status_and_ping(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """在线渠道服应返回其状态与延迟。"""
        _install_online_mocks(monkeypatch)
        server = ServerConfig(name="official", endpoint="https://idv.163.com")

        status = await server_manager.probe_server(server)

        assert status.status == "active"
        assert status.version == "2.0.0"
        assert status.players == 42
        assert status.ping == 12.5

    async def test_probe_failure_returns_offline_without_raising(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """探测异常时应降级为 ``offline`` 且不抛异常。"""

        async def failing_ping(endpoint: str, timeout: int = 10) -> float:
            _ = (endpoint, timeout)
            raise ServerError("网络不可达")

        monkeypatch.setattr(servers_manager_module, "ping_server", failing_ping)
        server = ServerConfig(name="official", endpoint="https://idv.163.com")

        status = await server_manager.probe_server(server)

        assert status.status == "offline"
        assert status.ping == float("inf")


@pytest.mark.unit
class TestProbeAll:
    """``probe_all`` 的批量探测与写回。"""

    async def test_probe_all_writes_back_to_config(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """探测结果应写回渠道服配置。"""
        _install_online_mocks(monkeypatch)
        servers = [server_manager.get_server("official")]

        results = await server_manager.probe_all(servers)

        assert set(results) == {"official"}
        official = server_manager.get_server("official")
        assert official.ping == 12.5
        assert official.players == 42
        assert official.last_check is not None

    async def test_probe_all_marks_offline_as_inactive(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """离线渠道服的状态应写回为 ``inactive`` 且延迟清空。"""

        async def failing_ping(endpoint: str, timeout: int = 10) -> float:
            _ = (endpoint, timeout)
            raise ServerError("超时")

        monkeypatch.setattr(servers_manager_module, "ping_server", failing_ping)
        servers = [server_manager.get_server("official")]

        await server_manager.probe_all(servers)

        official = server_manager.get_server("official")
        assert official.status == "inactive"
        assert official.ping is None

    async def test_probe_all_with_empty_list_returns_empty_dict(
        self, server_manager: ServerManager
    ) -> None:
        """空输入应直接返回空字典。"""
        assert await server_manager.probe_all([]) == {}


@pytest.mark.unit
class TestDetectCurrentServer:
    """``detect_current_server`` 的最优选择。"""

    async def test_detect_returns_lowest_latency_server(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """应返回延迟最低的在线渠道服。"""

        async def fake_probe_all(
            _servers: list[ServerConfig] | None = None,
        ) -> dict[str, ServerStatus]:
            return {
                "official": ServerStatus(name="official", status="active", ping=50.0),
                "bserver": ServerStatus(name="bserver", status="active", ping=5.0),
            }

        monkeypatch.setattr(server_manager, "probe_all", fake_probe_all)

        assert await server_manager.detect_current_server() == "bserver"

    async def test_detect_returns_none_when_all_offline(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """全部离线时应返回 ``None``。"""

        async def fake_probe_all(
            _servers: list[ServerConfig] | None = None,
        ) -> dict[str, ServerStatus]:
            return {
                "official": ServerStatus(
                    name="official", status="offline", ping=float("inf")
                )
            }

        monkeypatch.setattr(server_manager, "probe_all", fake_probe_all)

        assert await server_manager.detect_current_server() is None

    async def test_detect_returns_none_without_servers(
        self, server_manager: ServerManager
    ) -> None:
        """没有任何渠道服时返回 ``None``。"""
        for name in list(server_manager.config_manager.get_config().servers):
            server_manager.remove_server(name)

        assert await server_manager.detect_current_server() is None


@pytest.mark.unit
class TestMonitorServers:
    """``monitor_servers`` 的有限轮次监控。"""

    async def test_monitor_runs_requested_iterations(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """指定的轮数应被执行且结果落盘。"""
        calls = {"count": 0}

        async def fake_probe_all(
            _servers: list[ServerConfig] | None = None,
        ) -> dict[str, ServerStatus]:
            calls["count"] += 1
            return {}

        monkeypatch.setattr(server_manager, "probe_all", fake_probe_all)
        monkeypatch.setattr(
            server_manager.config_manager, "save_config", lambda *_a, **_k: None
        )

        await server_manager.monitor_servers(interval=0, iterations=2)

        assert calls["count"] == 2

    async def test_explicit_zero_interval_is_honored(
        self, server_manager: ServerManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """显式传入 ``interval=0`` 不应被当成未指定而回落到默认的 300 秒。"""
        periods: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            periods.append(seconds)

        async def fake_probe_all(
            _servers: list[ServerConfig] | None = None,
        ) -> dict[str, ServerStatus]:
            return {}

        monkeypatch.setattr(server_manager, "probe_all", fake_probe_all)
        monkeypatch.setattr(
            server_manager.config_manager, "save_config", lambda *_a, **_k: None
        )
        monkeypatch.setattr(servers_manager_module.asyncio, "sleep", fake_sleep)

        await server_manager.monitor_servers(interval=0, iterations=2)

        assert periods == [0.0]
