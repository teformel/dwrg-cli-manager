"""
启动管理器

负责游戏客户端的启动、停止与状态查询。启动路径按以下顺序解析：

1. :class:`~dwrg_manager.launcher.models.LaunchConfig` 中显式指定的 ``game_path``；
2. 环境变量 ``DWRG_GAME_PATH``；
3. 平台常见安装位置（Windows 下为 Program Files / AppData / 家目录 Games）。

若最终仍找不到可执行文件，:meth:`LauncherManager.launch_game` 会返回
``False`` 并记录原因，不会抛出异常。
"""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from ..config.manager import ConfigManager
from ..exceptions import LaunchError
from ..utils.logger import get_logger
from ..utils.system import SystemManager
from .models import GameStatus, LaunchConfig, LaunchResult

logger = get_logger(__name__)

#: 环境变量：显式指定游戏可执行文件路径
ENV_GAME_PATH = "DWRG_GAME_PATH"

#: 判定「磁盘空间充足」的下限（字节，10 GiB）
MIN_FREE_BYTES = 10 * 1024**3

#: 默认启动参数
DEFAULT_LAUNCH_PARAMS: tuple[str, ...] = ("-fullscreen", "-high", "-thread", "4")

#: 默认环境变量
DEFAULT_ENV_VARS: dict[str, str] = {"DXGI_DEBUG": "1", "ENABLE_DX12": "1"}


def default_game_candidates() -> list[Path]:
    """返回候选的游戏可执行文件路径列表。

    Returns:
        按优先级排列的候选路径。
    """
    home = Path.home()
    candidates = [
        home / "Games" / "IdentityV" / "IdentityV.exe",
        home / ".dwrg" / "game" / "IdentityV.exe",
    ]
    if platform.system() == "Windows":
        candidates.extend(
            [
                Path("C:/Program Files (x86)/IdentityV/IdentityV.exe"),
                Path("C:/Program Files/IdentityV/IdentityV.exe"),
                home / "AppData" / "Local" / "IdentityV" / "IdentityV.exe",
            ]
        )
    return candidates


class LauncherManager:
    """启动管理器。

    Args:
        config_manager: 注入的配置管理器；为 ``None`` 时使用默认配置。
        system_manager: 注入的系统管理器；为 ``None`` 时使用默认实现。
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        system_manager: SystemManager | None = None,
    ) -> None:
        self.config_manager = config_manager or ConfigManager()
        self.system_manager = system_manager or SystemManager()
        self.logger = get_logger(__name__)
        self.game_process: psutil.Process | None = None
        self.launch_config: LaunchConfig | None = None
        self.start_time: datetime | None = None

    # ------------------------------------------------------------------ #
    # 启动
    # ------------------------------------------------------------------ #
    def launch_game(
        self,
        account_id: str | None = None,
        server_name: str | None = None,
        verbose: bool = False,
    ) -> bool:
        """启动游戏客户端。

        Args:
            account_id: 使用的账号 ID；为 ``None`` 时沿用配置中的当前账号。
            server_name: 使用的渠道服；为 ``None`` 时沿用配置中的当前渠道服。
            verbose: 是否把游戏子进程的输出透传出来。

        Returns:
            是否成功拉起进程。
        """
        result = self.launch(
            account_id=account_id, server_name=server_name, verbose=verbose
        )
        return result.success

    def launch(
        self,
        account_id: str | None = None,
        server_name: str | None = None,
        verbose: bool = False,
    ) -> LaunchResult:
        """启动游戏客户端并返回结构化结果。

        Args:
            account_id: 使用的账号 ID。
            server_name: 使用的渠道服。
            verbose: 是否透传子进程输出。

        Returns:
            :class:`LaunchResult`；失败时 ``error_message`` 说明原因。
        """
        self.logger.info("准备启动游戏...")

        try:
            self._prepare_launch_config(account_id, server_name)
            assert self.launch_config is not None  # noqa: S101 - 上面必然赋值

            game_path = self._get_game_path(self.launch_config)
            if game_path is None or not game_path.exists():
                message = (
                    f"未找到游戏可执行文件（已尝试 {ENV_GAME_PATH} 与默认安装路径）"
                )
                self.logger.error(message)
                return LaunchResult(
                    success=False, error_message=message, config=self.launch_config
                )

            cmd = self._build_launch_command(game_path, account_id, server_name)
            working_dir = self.launch_config.working_dir or str(game_path.parent)
            env = self._build_environment()

            stdout = subprocess.PIPE if verbose else subprocess.DEVNULL
            stderr = subprocess.PIPE if verbose else subprocess.DEVNULL
            kwargs: dict[str, Any] = {
                "cwd": working_dir,
                "env": env,
                "stdout": stdout,
                "stderr": stderr,
            }
            if platform.system() == "Windows":  # pragma: no cover - 依平台而定
                creation_flags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
                kwargs["creationflags"] = creation_flags

            process = subprocess.Popen(cmd, **kwargs)
            self.game_process = psutil.Process(process.pid)
            self.start_time = datetime.now()
            self.logger.info("游戏启动成功，进程ID: %s", process.pid)
            return LaunchResult(
                success=True, process_id=process.pid, config=self.launch_config
            )

        except (OSError, LaunchError, subprocess.SubprocessError) as exc:
            self.logger.error("启动游戏失败: %s", exc)
            return LaunchResult(
                success=False, error_message=str(exc), config=self.launch_config
            )

    def _prepare_launch_config(
        self, account_id: str | None, server_name: str | None
    ) -> LaunchConfig:
        """校验并组装启动配置。

        Args:
            account_id: 账号 ID。
            server_name: 渠道服名称。

        Returns:
            组装好的 :class:`LaunchConfig`。

        Raises:
            LaunchError: 指定的账号或渠道服不存在。
        """
        app_config = self.config_manager.get_app_config()
        final_account = account_id or app_config.account
        final_server = server_name or app_config.server

        if (
            final_account
            and self.config_manager.get_account_config(final_account) is None
        ):
            raise LaunchError(f"账号不存在: {final_account}", account_id=final_account)
        if final_server and self.config_manager.get_server_config(final_server) is None:
            raise LaunchError(f"渠道服不存在: {final_server}", server=final_server)

        self.launch_config = LaunchConfig(
            account_id=final_account,
            server_name=final_server,
            launch_params=list(DEFAULT_LAUNCH_PARAMS),
            env_vars=dict(DEFAULT_ENV_VARS),
        )
        return self.launch_config

    # ------------------------------------------------------------------ #
    # 停止 / 状态
    # ------------------------------------------------------------------ #
    def stop_game(self, force: bool = False) -> bool:
        """停止游戏进程。

        Args:
            force: 为 ``True`` 时直接强杀，否则先尝试优雅终止。

        Returns:
            是否成功停止（进程本就不存在视为成功）。
        """
        self.logger.info("准备停止游戏...")
        if self.game_process is None or not self.game_process.is_running():
            self.logger.warning("游戏未运行")
            self.game_process = None
            return True

        try:
            if force:
                self.game_process.kill()
                self.logger.info("已强制终止游戏进程")
            else:
                self.game_process.terminate()
                try:
                    self.game_process.wait(timeout=10)
                    self.logger.info("游戏进程已优雅终止")
                except psutil.TimeoutExpired:
                    self.game_process.kill()
                    self.logger.info("优雅终止超时，已强制终止")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            self.logger.error("停止游戏失败: %s", exc)
            return False

        self.game_process = None
        self.start_time = None
        self.launch_config = None
        return True

    def get_game_status(self) -> GameStatus:
        """查询游戏运行状态。

        Returns:
            :class:`GameStatus`；进程已退出时 ``is_running`` 为 ``False``。
        """
        if self.game_process is None or not self.game_process.is_running():
            self.game_process = None
            self.start_time = None
            return GameStatus(is_running=False, launch_config=self.launch_config)

        try:
            memory_info = self.game_process.memory_info()
            cpu_usage = self.game_process.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            self.logger.warning("读取进程信息失败: %s", exc)
            return GameStatus(is_running=False, launch_config=self.launch_config)

        running_time = (
            (datetime.now() - self.start_time).total_seconds()
            if self.start_time
            else 0.0
        )
        return GameStatus(
            is_running=True,
            process_id=self.game_process.pid,
            cpu_usage=cpu_usage,
            memory_usage=memory_info.rss,
            running_time=running_time,
            launch_config=self.launch_config,
        )

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def _get_game_path(self, config: LaunchConfig | None = None) -> Path | None:
        """解析游戏可执行文件路径。

        Args:
            config: 启动配置（可能含显式 ``game_path``）。

        Returns:
            找到的路径；全部候选都不存在时返回 ``None``。
        """
        explicit = (config.game_path if config else "") or os.environ.get(
            ENV_GAME_PATH, ""
        )
        if explicit:
            path = Path(explicit).expanduser()
            return path

        for candidate in default_game_candidates():
            if candidate.exists():
                return candidate
        return None

    def _build_launch_command(
        self, game_path: Path, account_id: str | None, server_name: str | None
    ) -> list[str]:
        """构造启动命令行。

        Args:
            game_path: 游戏可执行文件路径。
            account_id: 账号 ID。
            server_name: 渠道服名称。

        Returns:
            命令与参数列表。
        """
        cmd = [str(game_path)]
        if self.launch_config:
            cmd.extend(self.launch_config.launch_params)
        if account_id:
            cmd.extend(["-account", account_id])
        if server_name:
            cmd.extend(["-server", server_name])
        return cmd

    def _build_environment(self) -> dict[str, str]:
        """构造子进程环境变量。

        Returns:
            环境变量字典。
        """
        env = os.environ.copy()
        if self.launch_config:
            env.update(self.launch_config.env_vars)
        env["DWRG_LAUNCHED"] = "1"
        if self.launch_config and self.launch_config.account_id:
            env["DWRG_ACCOUNT"] = self.launch_config.account_id
        if self.launch_config and self.launch_config.server_name:
            env["DWRG_SERVER"] = self.launch_config.server_name
        return env

    def diagnose_launch(self) -> dict[str, object]:
        """诊断启动环境。

        Returns:
            含 ``game_exists`` / ``game_path`` / ``account_valid`` /
            ``server_valid`` / ``disk_space`` / ``recommendations`` 的字典。
        """
        diagnosis: dict[str, object] = {
            "game_exists": False,
            "game_path": None,
            "account_valid": False,
            "server_valid": False,
            "disk_space": False,
            "recommendations": [],
        }
        recommendations: list[str] = diagnosis["recommendations"]  # type: ignore[assignment]

        game_path = self._get_game_path(self.launch_config)
        diagnosis["game_exists"] = game_path is not None
        diagnosis["game_path"] = str(game_path) if game_path else None
        if game_path is None:
            recommendations.append(
                f"未找到游戏客户端，请通过 {ENV_GAME_PATH} 环境变量或配置指定路径"
            )

        app_config = self.config_manager.get_app_config()
        account_id = (
            self.launch_config.account_id if self.launch_config else None
        ) or app_config.account
        if account_id:
            diagnosis["account_valid"] = (
                self.config_manager.get_account_config(account_id) is not None
            )
            if not diagnosis["account_valid"]:
                recommendations.append(f"账号配置无效: {account_id}")

        server_name = (
            self.launch_config.server_name if self.launch_config else None
        ) or app_config.server
        if server_name:
            diagnosis["server_valid"] = (
                self.config_manager.get_server_config(server_name) is not None
            )
            if not diagnosis["server_valid"]:
                recommendations.append(f"渠道服配置无效: {server_name}")

        free_bytes = 0
        for disk in self.system_manager.get_disk_info():
            if disk.get("free_bytes"):
                free_bytes = max(free_bytes, int(disk["free_bytes"]))
        diagnosis["disk_space"] = free_bytes >= MIN_FREE_BYTES
        if not diagnosis["disk_space"]:
            recommendations.append("可用磁盘空间不足 10 GiB，建议清理磁盘")

        return diagnosis


__all__ = [
    "DEFAULT_ENV_VARS",
    "DEFAULT_LAUNCH_PARAMS",
    "ENV_GAME_PATH",
    "LauncherManager",
    "default_game_candidates",
]
