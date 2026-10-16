"""
启动管理器

负责游戏客户端的启动、停止与状态查询。启动路径按以下顺序解析：

1. :class:`~dwrg_manager.launcher.models.LaunchConfig` 中显式指定的 ``game_path``；
2. 环境变量 ``DWRG_GAME_PATH``；
3. 平台常见安装位置（Windows 下为 Program Files / AppData / 家目录 Games）。

若最终仍找不到可执行文件，:meth:`LauncherManager.launch_game` 会返回
``False`` 并记录原因，不会抛出异常。传入 ``dry_run=True`` 时则只组装并返回
:class:`~dwrg_manager.launcher.models.LaunchPlan`，不拉起任何进程。

正式启动前会先跑一遍「启动前检查」（:meth:`LauncherManager.check_launch`），
覆盖磁盘空间、进程重复启动、可执行文件存在性与渠道服配置就绪四项；任一项
失败都会给出**可执行的修复建议**。
"""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from ..accounts.session import get_active_session
from ..config.manager import ConfigManager
from ..exceptions import LaunchError
from ..utils.logger import get_logger
from ..utils.system import SystemManager
from .models import (
    DEFAULT_GRAPHICS_LEVEL,
    CheckItem,
    GameStatus,
    LaunchCheck,
    LaunchConfig,
    LaunchPlan,
    LaunchResult,
)

logger = get_logger(__name__)

#: 环境变量：显式指定游戏可执行文件路径
ENV_GAME_PATH = "DWRG_GAME_PATH"

#: 判定「磁盘空间充足」的下限（字节，10 GiB）
MIN_FREE_BYTES = 10 * 1024**3

#: 默认启动参数
DEFAULT_LAUNCH_PARAMS: tuple[str, ...] = ("-fullscreen", "-high", "-thread", "4")

#: 默认环境变量
DEFAULT_ENV_VARS: dict[str, str] = {"DXGI_DEBUG": "1", "ENABLE_DX12": "1"}

#: 画质档位命令行前缀（IdentityV 客户端用 -graphics=<档位>）
GRAPHICS_FLAG = "-graphics="


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
        self.last_plan: LaunchPlan | None = None

    # ------------------------------------------------------------------ #
    # 启动
    # ------------------------------------------------------------------ #
    def launch_game(
        self,
        account_id: str | None = None,
        server_name: str | None = None,
        verbose: bool = False,
        *,
        graphics: str | None = None,
        dry_run: bool = False,
    ) -> bool:
        """启动游戏客户端。

        Args:
            account_id: 使用的账号 ID；为 ``None`` 时沿用配置中的当前账号。
            server_name: 使用的渠道服；为 ``None`` 时沿用配置中的当前渠道服。
            verbose: 是否把游戏子进程的输出透传出来。
            graphics: 画质档位（``sd`` / ``hd`` / ``uhd``）；为 ``None``
                时使用默认档位 ``hd``，透传为 ``-graphics=<档位>``。
            dry_run: 为 ``True`` 时只做启动前检查与计划组装，不真正拉起进程，
                返回值代表「是否具备启动条件」。

        Returns:
            是否成功拉起进程（``dry_run`` 时为是否通过启动前检查）。
        """
        result = self.launch(
            account_id=account_id,
            server_name=server_name,
            verbose=verbose,
            graphics=graphics,
            dry_run=dry_run,
        )
        return result.success

    def launch(
        self,
        account_id: str | None = None,
        server_name: str | None = None,
        verbose: bool = False,
        *,
        graphics: str | None = None,
        dry_run: bool = False,
    ) -> LaunchResult:
        """启动游戏客户端并返回结构化结果。

        Args:
            account_id: 使用的账号 ID。
            server_name: 使用的渠道服。
            verbose: 是否透传子进程输出。
            graphics: 画质档位；为 ``None`` 时使用默认档位
                :data:`DEFAULT_GRAPHICS_LEVEL`。
            dry_run: 为 ``True`` 时**不启动任何进程**，仅返回启动前检查结果；
                失败时 ``error_message`` 汇总各检查项的修复建议。

        Returns:
            :class:`LaunchResult`；失败时 ``error_message`` 说明原因。
        """
        self.logger.info("准备启动游戏...")

        try:
            self._prepare_launch_config(account_id, server_name, graphics=graphics)
            assert self.launch_config is not None  # noqa: S101 - 上面必然赋值

            check = self.check_launch()
            if not check.ready:
                message = "；".join(
                    f"{item.message}（建议: {item.suggestion}）"
                    for item in check.failures
                    if item.suggestion
                ) or "；".join(item.message for item in check.failures)
                self.logger.error("启动前检查未通过: %s", message)
                return LaunchResult(
                    success=False, error_message=message, config=self.launch_config
                )

            game_path = self._get_game_path(self.launch_config)
            assert game_path is not None  # noqa: S101 - 检查已保证其存在
            cmd = self._build_launch_command(game_path, account_id, server_name)
            working_dir = self.launch_config.working_dir or str(game_path.parent)
            env = self._build_environment()

            if dry_run:
                self.logger.info("dry-run：跳过实际启动，仅返回启动计划")
                self.last_plan = LaunchPlan(
                    command=cmd,
                    working_dir=working_dir,
                    env_vars={
                        key: value
                        for key, value in env.items()
                        if key.startswith("DWRG_")
                    },
                    account_id=self.launch_config.account_id,
                    server_name=self.launch_config.server_name,
                    game_path=str(game_path),
                )
                return LaunchResult(success=True, config=self.launch_config)

            stdout = subprocess.PIPE if verbose else subprocess.DEVNULL
            stderr = subprocess.PIPE if verbose else subprocess.DEVNULL
            kwargs: dict[str, Any] = {
                "cwd": working_dir,
                "env": env,
                "stdout": stdout,
                "stderr": stderr,
            }
            if platform.system() == "Windows":  # pragma: no cover - 依平台而定
                # 用 getattr 取属性：Windows 上为 CREATE_NEW_CONSOLE，
                # 其它平台上该分支不会执行（属性缺失时回退 0）。
                creation_flags: int = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
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

    def dry_run_plan(
        self, account_id: str | None = None, server_name: str | None = None
    ) -> LaunchPlan | None:
        """组装启动计划而不启动进程。

        这是 :meth:`launch` 的 ``dry_run=True`` 变体，直接返回
        :class:`~dwrg_manager.launcher.models.LaunchPlan`，便于 CLI 把
        「将执行的命令行 + 环境变量 + 工作目录」原样展示给用户。

        Args:
            account_id: 使用的账号 ID。
            server_name: 使用的渠道服。

        Returns:
            启动计划；启动前检查未通过时返回 ``None``。
        """
        self.launch(account_id=account_id, server_name=server_name, dry_run=True)
        return self.last_plan

    def _prepare_launch_config(
        self,
        account_id: str | None,
        server_name: str | None,
        *,
        graphics: str | None = None,
    ) -> LaunchConfig:
        """校验并组装启动配置。

        Args:
            account_id: 账号 ID。
            server_name: 渠道服名称。
            graphics: 画质档位；为 ``None`` 时使用
                :data:`DEFAULT_GRAPHICS_LEVEL`。

        Returns:
            组装好的 :class:`LaunchConfig`。

        Raises:
            LaunchError: 指定的账号或渠道服不存在。
            ValueError: 画质档位非法。
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
            graphics=graphics or DEFAULT_GRAPHICS_LEVEL,
        )
        return self.launch_config

    # ------------------------------------------------------------------ #
    # 启动前检查
    # ------------------------------------------------------------------ #
    def check_launch(self, config: LaunchConfig | None = None) -> LaunchCheck:
        """执行启动前检查。

        检查项（任一失败都会附带可执行的修复建议）：

        1. ``executable``：可执行文件存在且是文件；
        2. ``disk_space``：目标盘剩余空间不低于 :data:`MIN_FREE_BYTES`；
        3. ``process``：游戏进程未在运行（避免重复启动）；
        4. ``server``：渠道服配置就绪；
        5. ``account``：账号配置就绪（未配置账号时不视为失败）。

        Args:
            config: 待检查的启动配置；为 ``None`` 时使用
                :attr:`launch_config`（可能为空，此时按环境变量与默认候选
                路径重新解析）。

        Returns:
            :class:`LaunchCheck`；``ready`` 为 ``True`` 表示可以启动。
        """
        target = config or self.launch_config
        result = LaunchCheck()

        game_path = self._get_game_path(target)
        if game_path is None:
            result.add(
                CheckItem(
                    name="executable",
                    passed=False,
                    message=f"未找到游戏可执行文件（已尝试 {ENV_GAME_PATH} 与默认安装路径）",
                    suggestion=(
                        f"请设置环境变量 {ENV_GAME_PATH} 指向客户端可执行文件，"
                        "或运行 dwrg diagnose 查看已探测到的安装位置"
                    ),
                )
            )
        elif not game_path.exists():
            result.add(
                CheckItem(
                    name="executable",
                    passed=False,
                    message=f"游戏可执行文件不存在: {game_path}",
                    suggestion=f"请确认 {game_path} 是否被移动或删除，并更新 {ENV_GAME_PATH}",
                )
            )
        elif not game_path.is_file():
            result.add(
                CheckItem(
                    name="executable",
                    passed=False,
                    message=f"路径不是可执行文件: {game_path}",
                    suggestion=f"请把 {ENV_GAME_PATH} 指向 .exe 文件本身，而不是目录",
                )
            )
        else:
            result.add(
                CheckItem(
                    name="executable",
                    passed=True,
                    message=f"游戏可执行文件就绪: {game_path}",
                )
            )

        result.add(self._check_disk_space(game_path))
        result.add(self._check_running_process(game_path))
        result.add(self._check_server_config(target))
        result.add(self._check_account_config(target))
        return result

    def _check_disk_space(self, game_path: Path | None) -> CheckItem:
        """检查游戏所在盘的剩余空间。

        Args:
            game_path: 游戏可执行文件路径；为 ``None`` 时检查当前工作目录。

        Returns:
            磁盘空间检查项。
        """
        target = game_path.parent if game_path else Path.cwd()
        free_bytes = self.system_manager.free_space_bytes(target)
        if free_bytes >= MIN_FREE_BYTES:
            return CheckItem(
                name="disk_space",
                passed=True,
                message=f"磁盘空间充足（剩余 {self._format_gib(free_bytes)} GiB）",
            )
        return CheckItem(
            name="disk_space",
            passed=False,
            message=(
                f"磁盘剩余空间不足：{self._format_gib(free_bytes)} GiB "
                f"< {self._format_gib(MIN_FREE_BYTES)} GiB"
            ),
            suggestion="请清理该磁盘的临时文件或卸载不常用程序后重试",
        )

    def _check_running_process(self, game_path: Path | None) -> CheckItem:
        """检查游戏进程是否已在运行。

        Args:
            game_path: 游戏可执行文件路径，用于按目录匹配命令行。

        Returns:
            进程检查项；已运行时给出 PID 与「先停止再启动」的建议。
        """
        game_dir = game_path.parent if game_path else None
        try:
            processes = self.system_manager.find_game_processes(game_dir)
        except Exception as exc:  # noqa: BLE001 - 探测失败不应阻断启动
            self.logger.debug("进程探测失败: %s", exc)
            return CheckItem(
                name="process",
                passed=True,
                message="未能探测进程状态，跳过重复启动检查",
            )

        if not processes:
            return CheckItem(name="process", passed=True, message="游戏进程未在运行")

        first = processes[0]
        return CheckItem(
            name="process",
            passed=False,
            message=(
                f"游戏已在运行（PID {first.get('pid')}，共 {len(processes)} 个进程）"
            ),
            suggestion="请先运行 dwrg launch stop 停止现有进程，或直接切换到已运行的客户端",
        )

    def _check_server_config(self, config: LaunchConfig | None) -> CheckItem:
        """检查渠道服配置是否就绪。

        Args:
            config: 启动配置。

        Returns:
            渠道服检查项。
        """
        app_config = self.config_manager.get_app_config()
        server_name = (config.server_name if config else None) or app_config.server
        if not server_name:
            return CheckItem(
                name="server",
                passed=False,
                message="未设置当前渠道服",
                suggestion="请运行 dwrg server list 查看可用渠道服，再用 dwrg server switch 选择",
            )
        if self.config_manager.get_server_config(server_name) is None:
            available = (
                ", ".join(sorted(self.config_manager.get_config().servers)) or "（无）"
            )
            return CheckItem(
                name="server",
                passed=False,
                message=f"渠道服不存在: {server_name}",
                suggestion=f"可用渠道服: {available}；或用 dwrg server add 新增",
            )
        return CheckItem(
            name="server", passed=True, message=f"渠道服配置就绪: {server_name}"
        )

    def _check_account_config(self, config: LaunchConfig | None) -> CheckItem:
        """检查账号配置是否就绪（未配置账号时视为通过）。

        Args:
            config: 启动配置。

        Returns:
            账号检查项。
        """
        app_config = self.config_manager.get_app_config()
        account_id = (config.account_id if config else None) or app_config.account
        if not account_id:
            return CheckItem(
                name="account", passed=True, message="未配置账号（按游客模式启动）"
            )
        if self.config_manager.get_account_config(account_id) is None:
            available = (
                ", ".join(sorted(self.config_manager.get_config().accounts)) or "（无）"
            )
            return CheckItem(
                name="account",
                passed=False,
                message=f"账号不存在: {account_id}",
                suggestion=f"可用账号: {available}；或用 dwrg account list 查看",
            )
        return CheckItem(
            name="account", passed=True, message=f"账号配置就绪: {account_id}"
        )

    @staticmethod
    def _format_gib(value: int | float) -> str:
        """把字节数格式化为 GiB 字符串。

        Args:
            value: 字节数。

        Returns:
            保留一位小数的 GiB 数值字符串。
        """
        return f"{value / 1024**3:.1f}"

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
            命令与参数列表；画质档位以 `-graphics=<档位>` 形式附在末尾。
        """
        cmd = [str(game_path)]
        if self.launch_config:
            cmd.extend(self.launch_config.launch_params)
        if account_id:
            cmd.extend(["-account", account_id])
        if server_name:
            cmd.extend(["-server", server_name])
        if self.launch_config and self.launch_config.graphics:
            cmd.append(f"{GRAPHICS_FLAG}{self.launch_config.graphics}")
        return cmd

    def _build_environment(self) -> dict[str, str]:
        """构造子进程环境变量。

        启动配置中的账号/渠道服优先；未显式指定时回落到
        :func:`~dwrg_manager.accounts.session.get_active_session` 读到的登录态。

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

        session = get_active_session()
        if session is not None:
            # 登录态只补充启动配置缺失的字段，不覆盖显式指定值
            env.setdefault("DWRG_ACCOUNT", session.account_id)
            if session.server:
                env.setdefault("DWRG_SERVER", session.server)
            if session.username:
                env.setdefault("DWRG_ACCOUNT_NAME", session.username)
        return env

    def diagnose_launch(self) -> dict[str, object]:
        """诊断启动环境。

        复用 :meth:`check_launch` 的各检查项，并把结果折叠成历史稳定的扁平
        字典（``game_exists`` / ``game_path`` / ``account_valid`` /
        ``server_valid`` / ``disk_space``），同时额外输出 ``checks``（逐项
        明细）与 ``recommendations``（可执行的修复建议）。

        Returns:
            诊断结果字典。
        """
        check = self.check_launch()
        by_name = {item.name: item for item in check.items}

        game_path = self._get_game_path(self.launch_config)
        app_config = self.config_manager.get_app_config()
        account_id = (
            self.launch_config.account_id if self.launch_config else None
        ) or app_config.account
        server_name = (
            self.launch_config.server_name if self.launch_config else None
        ) or app_config.server

        recommendations: list[str] = []
        for item in check.failures:
            advice = (
                f"{item.message}（建议: {item.suggestion}）"
                if item.suggestion
                else item.message
            )
            recommendations.append(advice)

        return {
            "game_exists": by_name["executable"].passed,
            "game_path": str(game_path) if game_path else None,
            "account_valid": account_id is None or by_name["account"].passed,
            "server_valid": server_name is None or by_name["server"].passed,
            "disk_space": by_name["disk_space"].passed,
            "process_running": not by_name["process"].passed,
            "checks": check.to_dict(),
            "recommendations": recommendations,
        }


__all__ = [
    "DEFAULT_ENV_VARS",
    "DEFAULT_LAUNCH_PARAMS",
    "ENV_GAME_PATH",
    "LauncherManager",
    "default_game_candidates",
]
