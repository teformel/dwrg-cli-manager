"""
系统工具

封装跨平台的系统信息采集、进程管理与文件操作。所有方法都做了降级处理：
在权限不足或平台特性缺失时返回空结果并记录日志，而不是抛出异常，
以保证 CLI 的「诊断」类命令永远可执行。
"""

import importlib
import logging
import os
import platform
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from .logger import get_logger

#: 常见的第五人格客户端进程名（Windows）
GAME_PROCESS_NAMES: tuple[str, ...] = ("IdentityV.exe", "identityv.exe", "game.exe")


def _read_os_release() -> str:
    """读取 Linux 发行版名称。

    优先使用标准库 ``platform.freedesktop_os_release()``（Python 3.10+），
    失败时回退到手工解析 ``/etc/os-release``。

    Returns:
        发行版名称；无法判断时返回 ``"Unknown"``。
    """
    try:
        info = platform.freedesktop_os_release()
        name = info.get("NAME") or info.get("ID")
        version = info.get("VERSION_ID", "")
        if name:
            return f"{name} {version}".strip()
    except (OSError, AttributeError):  # pragma: no cover - 依平台而定
        pass

    try:
        with open("/etc/os-release", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:  # pragma: no cover - 依平台而定
        pass
    return "Unknown"


class SystemManager:
    """系统管理器：采集系统/磁盘/内存/进程信息并执行文件操作。

    Args:
        game_process_names: 判定「游戏进程」时使用的进程名集合。

    Example:
        >>> manager = SystemManager()
        >>> manager.get_system_info()["system"]  # doctest: +SKIP
        'Linux'
    """

    def __init__(
        self, game_process_names: tuple[str, ...] = GAME_PROCESS_NAMES
    ) -> None:
        self.logger: logging.Logger = get_logger(__name__)
        self.platform: str = platform.system().lower()
        self.game_process_names = game_process_names

    # ------------------------------------------------------------------ #
    # 系统信息
    # ------------------------------------------------------------------ #
    def get_system_info(self) -> dict[str, str]:
        """采集操作系统与运行时信息。

        Returns:
            包含 ``platform`` / ``system`` / ``release`` / ``version`` /
            ``machine`` / ``processor`` / ``python_version`` 等键的字典，
            并附带当前平台的补充信息（Windows 版本号或 Linux 发行版名）。
        """
        info: dict[str, str] = {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
        }

        if self.platform == "windows":
            info["windows_version"] = self._get_windows_version()
        elif self.platform == "linux":
            info["distribution"] = _read_os_release()
        elif self.platform == "darwin":
            info["mac_version"] = platform.mac_ver()[0]

        return info

    def _get_windows_version(self) -> str:
        """读取 Windows 产品名称。

        Returns:
            产品名称；读取失败时返回 ``"Unknown"``。
        """
        if self.platform != "windows":  # pragma: no cover - 仅在非 Windows 触发
            return "Unknown"
        try:
            # 动态导入：``winreg`` 的 typeshed 桩仅在 win32 平台可见，
            # 直接 ``import winreg`` 在 Linux/macOS 上做类型检查会误报 attr-defined。
            winreg: Any = importlib.import_module("winreg")

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            ) as key:
                return str(winreg.QueryValueEx(key, "ProductName")[0])
        except (ImportError, OSError) as exc:  # pragma: no cover - 依平台而定
            self.logger.debug("读取 Windows 版本失败: %s", exc)
            return "Unknown"

    # ------------------------------------------------------------------ #
    # 硬件信息
    # ------------------------------------------------------------------ #
    def get_disk_info(self) -> list[dict[str, Any]]:
        """采集磁盘分区使用情况。

        Returns:
            每个分区一个字典，包含人类可读的 ``total`` / ``used`` / ``free``
            以及原始字节数 ``total_bytes`` / ``used_bytes`` / ``free_bytes``。
        """
        disk_info: list[dict[str, Any]] = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (PermissionError, OSError):  # pragma: no cover - 依赖系统
                continue
            disk_info.append(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": self._format_bytes(usage.total),
                    "used": self._format_bytes(usage.used),
                    "free": self._format_bytes(usage.free),
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "percent": f"{usage.percent:.1f}%",
                }
            )
        return disk_info

    def get_memory_info(self) -> dict[str, str]:
        """采集物理内存与交换分区使用情况。

        Returns:
            包含 ``total`` / ``available`` / ``used`` / ``percent`` 与
            对应 swap 字段的字典。
        """
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total": self._format_bytes(memory.total),
            "available": self._format_bytes(memory.available),
            "used": self._format_bytes(memory.used),
            "percent": f"{memory.percent:.1f}%",
            "swap_total": self._format_bytes(swap.total),
            "swap_used": self._format_bytes(swap.used),
            "swap_percent": f"{swap.percent:.1f}%",
        }

    def get_network_interfaces(self) -> list[dict[str, str]]:
        """采集 IPv4 网络接口信息。

        Returns:
            每个 IPv4 地址一个字典，含 ``interface`` / ``address`` /
            ``netmask`` / ``broadcast``。
        """
        interfaces: list[dict[str, str]] = []
        try:
            for name, addresses in psutil.net_if_addrs().items():
                for addr in addresses:
                    if addr.family == socket.AF_INET:
                        interfaces.append(
                            {
                                "interface": name,
                                "address": addr.address,
                                "netmask": addr.netmask or "",
                                "broadcast": addr.broadcast or "",
                            }
                        )
        except (OSError, psutil.Error) as exc:  # pragma: no cover - 依赖系统
            self.logger.error("获取网络接口信息失败: %s", exc)
        return interfaces

    # ------------------------------------------------------------------ #
    # 进程管理
    # ------------------------------------------------------------------ #
    def get_process_info(self, process_name: str | None = None) -> list[dict[str, Any]]:
        """查询进程信息。

        Args:
            process_name: 进程名（大小写不敏感）。为 ``None`` 时返回全部进程。

        Returns:
            每个进程一个字典，含 ``pid`` / ``name`` / ``username`` /
            ``memory_percent`` / ``cpu_percent``。
        """
        processes: list[dict[str, Any]] = []
        target = process_name.lower() if process_name else None

        for proc in psutil.process_iter(
            ["pid", "name", "username", "memory_percent", "cpu_percent"]
        ):
            try:
                info = proc.info
                name = info.get("name") or ""
                if target is not None and name.lower() != target:
                    continue
                processes.append(
                    {
                        "pid": info.get("pid"),
                        "name": name,
                        "username": info.get("username") or "",
                        "memory_percent": f"{(info.get('memory_percent') or 0.0):.1f}%",
                        "cpu_percent": f"{(info.get('cpu_percent') or 0.0):.1f}%",
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return processes

    def check_game_process(self) -> dict[str, Any] | None:
        """检查游戏客户端是否正在运行。

        Returns:
            首个匹配到的游戏进程信息；未运行时返回 ``None``。
        """
        for proc_name in self.game_process_names:
            processes = self.get_process_info(proc_name)
            if processes:
                return processes[0]
        return None

    def kill_process(self, pid: int, *, force: bool = False) -> bool:
        """终止指定进程。

        Args:
            pid: 进程 ID。
            force: 为 ``True`` 时使用 ``kill``，否则先尝试优雅 ``terminate``。

        Returns:
            是否成功发出终止信号。
        """
        try:
            proc = psutil.Process(pid)
            if force:
                proc.kill()
            else:
                proc.terminate()
            self.logger.info("已终止进程: %s (force=%s)", pid, force)
            return True
        except psutil.NoSuchProcess:
            self.logger.warning("进程不存在: %s", pid)
            return False
        except psutil.AccessDenied:
            self.logger.error("无权限终止进程: %s", pid)
            return False
        except psutil.Error as exc:  # pragma: no cover - 依赖系统
            self.logger.error("终止进程失败: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    # 文件与命令
    # ------------------------------------------------------------------ #
    def create_directory(self, path: str | Path) -> bool:
        """创建目录（含父级）。

        Args:
            path: 目标目录。

        Returns:
            是否创建成功（已存在视为成功）。
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            self.logger.debug("创建目录: %s", path)
            return True
        except OSError as exc:
            self.logger.error("创建目录失败: %s", exc)
            return False

    def file_exists(self, path: str | Path) -> bool:
        """判断路径是否存在。

        Args:
            path: 待检查的路径。

        Returns:
            存在返回 ``True``。
        """
        return os.path.exists(path)

    def file_size(self, path: str | Path) -> int:
        """获取文件字节大小。

        Args:
            path: 文件路径。

        Returns:
            文件大小；文件不存在或不可访问时返回 ``0``。
        """
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def get_file_info(self, path: str | Path) -> dict[str, Any]:
        """采集文件元信息。

        Args:
            path: 文件或目录路径。

        Returns:
            含 ``size`` / ``modified`` / ``created`` / ``is_file`` /
            ``is_dir`` / ``is_executable`` 的字典；路径不可访问时返回空字典。
        """
        try:
            stat = os.stat(path)
        except OSError as exc:
            self.logger.error("获取文件信息失败: %s", exc)
            return {}
        return {
            "size": self._format_bytes(stat.st_size),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "created": datetime.fromtimestamp(stat.st_ctime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "is_file": os.path.isfile(path),
            "is_dir": os.path.isdir(path),
            "is_executable": os.access(path, os.X_OK),
        }

    def run_command(self, command: list[str], timeout: int = 300) -> dict[str, Any]:
        """执行外部命令并捕获输出。

        Args:
            command: 命令与参数列表。
            timeout: 超时秒数。

        Returns:
            成功时含 ``stdout`` / ``stderr`` / ``returncode``；
            失败时含 ``error``，可能附带 ``returncode``。
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
        except subprocess.TimeoutExpired:
            self.logger.error("命令执行超时: %s", " ".join(command))
            return {"error": "命令执行超时"}
        except subprocess.CalledProcessError as exc:
            self.logger.error("命令执行失败: %s", exc)
            return {"error": str(exc), "returncode": exc.returncode}
        except OSError as exc:
            self.logger.error("命令执行异常: %s", exc)
            return {"error": str(exc)}
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    def check_port(self, port: int, host: str = "127.0.0.1") -> bool:
        """检查本地端口是否被占用。

        先尝试通过 psutil 枚举连接；在权限不足（Linux 非 root）时回退到
        实际绑定测试。

        Args:
            port: 端口号。
            host: 绑定探测使用的主机地址。

        Returns:
            端口被占用返回 ``True``。
        """
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and getattr(conn.laddr, "port", None) == port:
                    return True
            return False
        except (psutil.AccessDenied, OSError):
            pass

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                return True
        return False

    @staticmethod
    def _format_bytes(value: float) -> str:
        """把字节数格式化为人类可读字符串。

        Args:
            value: 字节数。

        Returns:
            形如 ``1.23 GB`` 的字符串。
        """
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


__all__ = ["GAME_PROCESS_NAMES", "SystemManager"]
