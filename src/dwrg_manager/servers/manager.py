"""
渠道服管理器
"""

import asyncio
from datetime import datetime

from ..config.manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.network import check_server_status, ping_server
from .models import ServerConfig, ServerManagerConfig, ServerStatus

logger = get_logger(__name__)


class ServerManager:
    """渠道服管理器"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.config_manager.get_config()  # 确保配置已加载
        self.server_config = ServerManagerConfig()  # 使用默认配置

    async def detect_current_server(self) -> str | None:
        """检测当前渠道服"""
        logger.info("开始检测当前渠道服...")

        try:
            # 获取所有可用服务器
            servers = self.list_servers()
            if not servers:
                logger.warning("没有可用的服务器配置")
                return None

            # 检测每个服务器的状态
            server_statuses = await asyncio.gather(
                *[self._check_server_status(server) for server in servers],
                return_exceptions=True
            )

            # 找到最佳服务器
            best_server = None
            best_ping = float('inf')

            for server, status in zip(servers, server_statuses):
                if isinstance(status, Exception):
                    logger.error(f"检测服务器 {server.name} 失败: {status}")
                    continue

                if status.ping < best_ping:
                    best_ping = status.ping
                    best_server = server.name

            if best_server:
                logger.info(f"检测到最佳服务器: {best_server} (延迟: {best_ping}ms)")
                return best_server
            else:
                logger.warning("无法检测到合适的服务器")
                return None

        except Exception as e:
            logger.error(f"检测渠道服失败: {e}")
            return None

    async def _check_server_status(self, server: ServerConfig) -> ServerStatus:
        """检查单个服务器状态"""
        try:
            # 检测服务器延迟
            ping = await ping_server(server.endpoint, timeout=self.server_config.timeout)

            # 检查服务器状态
            status = await check_server_status(server.endpoint, timeout=self.server_config.timeout)

            # 更新服务器配置
            server.last_check = datetime.now()
            server.ping = ping

            return ServerStatus(
                name=server.name,
                status=status,
                version=server.version,
                players=status.get('players', 0),
                ping=ping,
                last_check=datetime.now()
            )

        except Exception as e:
            logger.error(f"检查服务器 {server.name} 状态失败: {e}")
            return ServerStatus(
                name=server.name,
                status="offline",
                version=server.version,
                players=0,
                ping=float('inf'),
                last_check=datetime.now()
            )

    def list_servers(self) -> list[ServerConfig]:
        """列出所有服务器"""
        return list(self.config_manager.get_config().servers.values())

    def get_server(self, name: str) -> ServerConfig | None:
        """获取服务器配置"""
        return self.config_manager.get_config().servers.get(name)

    def add_server(self, name: str, endpoint: str, region: str = "CN",
                  status: str = "active", version: str = "1.0.0",
                  is_default: bool = False) -> ServerConfig:
        """添加服务器配置"""
        try:
            config = self.config_manager.get_config()
            server = ServerConfig(
                name=name,
                endpoint=endpoint,
                region=region,
                status=status,
                version=version,
                is_default=is_default
            )

            config.servers[name] = server

            # 如果设置为默认服务器，更新其他服务器
            if is_default:
                for srv_name, srv_config in config.servers.items():
                    srv_config.is_default = (srv_name == name)

            self.config_manager.save_config()
            logger.info(f"添加服务器: {name}")
            return server

        except Exception as e:
            logger.error(f"添加服务器失败: {e}")
            raise

    def remove_server(self, name: str) -> bool:
        """删除服务器配置"""
        try:
            config = self.config_manager.get_config()
            if name in config.servers:
                del config.servers[name]
                self.config_manager.save_config()
                logger.info(f"删除服务器: {name}")
                return True
            return False

        except Exception as e:
            logger.error(f"删除服务器失败: {e}")
            raise

    def switch_server(self, server_name: str) -> bool:
        """切换当前服务器"""
        try:
            config = self.config_manager.get_config()
            if server_name not in config.servers:
                logger.error(f"服务器 {server_name} 不存在")
                return False

            # 更新服务器配置
            for srv_name, srv_config in config.servers.items():
                srv_config.is_default = (srv_name == server_name)

            self.config_manager.save_config()
            logger.info(f"切换服务器: {server_name}")
            return True

        except Exception as e:
            logger.error(f"切换服务器失败: {e}")
            return False

    def get_current_server(self) -> ServerConfig | None:
        """获取当前服务器"""
        config = self.config_manager.get_config()
        for server in config.servers.values():
            if server.is_default:
                return server
        return None

    async def monitor_servers(self, interval: int = 300):
        """监控服务器状态"""
        logger.info("开始监控服务器状态...")

        while True:
            try:
                servers = self.list_servers()
                if servers:
                    # 检测服务器状态
                    server_statuses = await asyncio.gather(
                        *[self._check_server_status(server) for server in servers],
                        return_exceptions=True
                    )

                    # 更新服务器配置
                    for server, status in zip(servers, server_statuses):
                        if not isinstance(status, Exception):
                            server.ping = status.ping
                            server.last_check = status.last_check
                            server.players = status.players

                    self.config_manager.save_config()

                # 等待下一次检测
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"监控服务器失败: {e}")
                await asyncio.sleep(interval)
