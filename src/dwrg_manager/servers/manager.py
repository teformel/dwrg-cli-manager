"""
渠道服管理器

提供渠道服的同步 CRUD 与异步状态探测两条能力线：

* 同步：:meth:`ServerManager.list_servers` / :meth:`switch_server` 等，
  直接改写配置，供 CLI 即时调用。
* 异步：:meth:`ServerManager.probe_all` / :meth:`detect_current_server`，
  并发探测各渠道服的延迟与在线状态。探测失败不会抛异常，而是把该渠道服
  标记为 ``offline``，保证离线环境下命令依然可用。
"""

import asyncio
from datetime import datetime

from ..config.manager import ConfigManager
from ..config.models import ServerConfig
from ..exceptions import ConfigError, ServerError
from ..utils.logger import get_logger
from ..utils.network import check_server_status, ping_server
from .models import ServerManagerConfig, ServerStatus

logger = get_logger(__name__)


class ServerManager:
    """渠道服管理器。

    Args:
        config_manager: 注入的配置管理器；为 ``None`` 时使用默认配置。
        manager_config: 探测相关参数。

    Example:
        >>> from dwrg_manager.servers import ServerManager  # doctest: +SKIP
        >>> [s.name for s in ServerManager().list_servers()]  # doctest: +SKIP
        ['bserver', 'official', 'test_server']
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        manager_config: ServerManagerConfig | None = None,
    ) -> None:
        self.config_manager = config_manager or ConfigManager()
        self.server_config = manager_config or ServerManagerConfig()
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------ #
    # 同步 CRUD
    # ------------------------------------------------------------------ #
    def list_servers(self) -> list[ServerConfig]:
        """列出全部渠道服。

        Returns:
            按名称排序的渠道服列表。
        """
        return self.config_manager.list_servers()

    def get_server(self, name: str) -> ServerConfig | None:
        """获取指定渠道服。

        Args:
            name: 渠道服名称。

        Returns:
            渠道服配置；不存在时返回 ``None``。
        """
        return self.config_manager.get_server_config(name)

    def get_current_server(self) -> ServerConfig | None:
        """获取当前默认渠道服。

        Returns:
            渠道服配置；未设置时返回 ``None``。
        """
        return self.config_manager.get_current_server()

    def add_server(
        self,
        name: str,
        endpoint: str = "",
        region: str = "CN",
        status: str = "active",
        version: str = "1.0.0",
        is_default: bool = False,
    ) -> ServerConfig:
        """新增渠道服。

        Args:
            name: 渠道服名称。
            endpoint: 接口地址。
            region: 地区。
            status: 状态。
            version: 版本号。
            is_default: 是否设为默认渠道服。

        Returns:
            新建的渠道服配置。

        Raises:
            ConfigError: 配置不合法。
        """
        return self.config_manager.add_server(
            name=name,
            endpoint=endpoint,
            region=region,
            status=status,
            version=version,
            is_default=is_default,
        )

    def remove_server(self, name: str) -> bool:
        """删除渠道服。

        Args:
            name: 渠道服名称。

        Returns:
            是否删除成功。
        """
        return self.config_manager.remove_server(name)

    def switch_server(self, server_name: str) -> bool:
        """切换当前渠道服。

        Args:
            server_name: 目标渠道服名称。

        Returns:
            是否切换成功。
        """
        try:
            self.config_manager.set_default_server(server_name)
        except ConfigError as exc:
            self.logger.error("切换渠道服失败: %s", exc)
            return False
        return True

    def set_default(self, server_name: str) -> bool:
        """``switch_server`` 的语义化别名。

        Args:
            server_name: 目标渠道服名称。

        Returns:
            是否设置成功。
        """
        return self.switch_server(server_name)

    # ------------------------------------------------------------------ #
    # 异步探测
    # ------------------------------------------------------------------ #
    async def probe_server(self, server: ServerConfig) -> ServerStatus:
        """探测单个渠道服的在线状态与延迟。

        Args:
            server: 渠道服配置。

        Returns:
            探测结果。网络不可达时返回 ``status="offline"`` 且 ``ping`` 为
            ``inf``，不会抛出异常。
        """
        try:
            ping = await ping_server(
                server.endpoint, timeout=self.server_config.timeout
            )
            payload = await check_server_status(
                server.endpoint, timeout=self.server_config.timeout
            )
        except ServerError as exc:
            self.logger.debug("渠道服 %s 探测失败: %s", server.name, exc)
            return ServerStatus(
                name=server.name,
                status="offline",
                version=server.version,
                players=0,
                ping=float("inf"),
                last_check=datetime.now(),
            )

        return ServerStatus(
            name=server.name,
            status=str(payload.get("status", "active")),
            version=str(payload.get("version", server.version)),
            players=int(payload.get("players", 0) or 0),
            ping=ping,
            last_check=datetime.now(),
        )

    async def probe_all(
        self, servers: list[ServerConfig] | None = None
    ) -> dict[str, ServerStatus]:
        """并发探测多个渠道服，并把结果写回配置。

        Args:
            servers: 待探测的渠道服；为 ``None`` 时探测全部。

        Returns:
            以渠道服名称为键的探测结果字典。
        """
        targets = servers if servers is not None else self.list_servers()
        if not targets:
            return {}

        statuses = await asyncio.gather(
            *(self.probe_server(srv) for srv in targets), return_exceptions=True
        )
        results: dict[str, ServerStatus] = {}
        for server, status in zip(targets, statuses, strict=True):
            if isinstance(status, BaseException):
                self.logger.warning("渠道服 %s 探测异常: %s", server.name, status)
                continue
            results[server.name] = status
            # 写回配置（ServerConfig 已开启 validate_assignment）
            server.ping = None if status.ping == float("inf") else status.ping
            server.last_check = status.last_check
            server.players = status.players
            server.status = "inactive" if status.status == "offline" else status.status
        return results

    async def detect_current_server(self) -> str | None:
        """探测并返回延迟最低的可用渠道服。

        Returns:
            最佳渠道服名称；无可用渠道服时返回 ``None``。
        """
        self.logger.info("开始检测当前渠道服...")
        servers = self.list_servers()
        if not servers:
            self.logger.warning("没有可用的渠道服配置")
            return None

        results = await self.probe_all(servers)
        online = {
            name: status
            for name, status in results.items()
            if status.status != "offline"
        }
        if not online:
            self.logger.warning("所有渠道服均不可达")
            return None

        best = min(online.items(), key=lambda item: item[1].ping)
        self.logger.info("最佳渠道服: %s (延迟 %.1fms)", best[0], best[1].ping)
        return best[0]

    async def monitor_servers(
        self, interval: int | None = None, iterations: int | None = None
    ) -> None:
        """周期性监控渠道服状态。

        Args:
            interval: 探测间隔（秒）；为 ``None`` 时使用管理器配置。
                显式传入 ``0`` 表示不做间隔等待（用于测试或连续探测）。
            iterations: 最多执行的轮数；为 ``None`` 时无限循环。
        """
        # 注意：不能用 ``interval or check_interval``——显式传入 0 会被当成未指定，
        # 从而静默回落到 300 秒的默认间隔。
        period = self.server_config.check_interval if interval is None else interval
        count = 0
        self.logger.info("开始监控渠道服状态（间隔 %ss）...", period)
        while iterations is None or count < iterations:
            try:
                await self.probe_all()
                self.config_manager.save_config()
            except Exception as exc:  # noqa: BLE001 - 监控循环必须常驻
                self.logger.error("监控渠道服失败: %s", exc)
            count += 1
            if iterations is not None and count >= iterations:
                break
            await asyncio.sleep(period)


__all__ = ["ServerManager"]
