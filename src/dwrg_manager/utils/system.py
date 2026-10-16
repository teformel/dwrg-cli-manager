"""
系统工具

封装跨平台的系统信息采集、进程管理与文件操作。所有方法都做了降级处理：
在权限不足或平台特性缺失时返回空结果并记录日志，而不是抛出异常，
以保证 CLI 的「诊断」类命令永远可执行。

除基础采集外，本模块还提供两类「探测」能力，供启动前检查与系统诊断复用：

* :meth:`SystemManager.find_game_processes`：按进程名 + 命令行匹配游戏进程，
  用于判断「游戏是否已在运行」，避免重复启动；
* :meth:`SystemManager.detect_install_locations`：按平台惯例枚举可能的安装
  位置（Windows 读注册表卸载信息，Linux/macOS 读常见目录），全部失败时
  返回空列表而不抛异常。
"""

import importlib
import logging
import os
import platform
import shutil
import socket
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from .logger import get_logger

#: 常见的第五人格客户端进程名（Windows）
GAME_PROCESS_NAMES: tuple[str, ...] = ("IdentityV.exe", "identityv.exe", "game.exe")

#: 常见的第五人格客户端可执行文件名（跨平台，含无后缀的 Linux/macOS 形态）
GAME_EXECUTABLE_NAMES: tuple[str, ...] = (
    "IdentityV.exe",
    "identityv.exe",
    "IdentityV",
    "identityv",
    "game.exe",
)

#: Windows 注册表中需要扫描的「卸载信息」根键
_WINDOWS_UNINSTALL_KEYS: tuple[str, ...] = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)


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

    def find_game_processes(
        self, game_dir: str | Path | None = None
    ) -> list[dict[str, Any]]:
        """按进程名与命令行查找游戏进程。

        匹配策略是「进程名命中」或「命令行中出现游戏目录」二者其一：

        * 进程名（不区分大小写）命中 :data:`GAME_PROCESS_NAMES` 中的任意一项；
        * 命令行参数中包含 ``game_dir``（或其任一子路径），用于在用户把客户端
          改名为其他可执行文件时仍然能识别。

        Args:
            game_dir: 游戏安装目录；为 ``None`` 时只按进程名匹配。

        Returns:
            每个匹配进程一个字典，含 ``pid`` / ``name`` / ``username`` /
            ``cmdline`` / ``create_time`` / ``running_seconds``。任何单个
            进程读取失败都被跳过，不会中断整体扫描。
        """
        targets = {name.lower() for name in self.game_process_names}
        needle = str(game_dir).lower() if game_dir else ""
        found: list[dict[str, Any]] = []
        now = datetime.now()

        for proc in psutil.process_iter(["pid", "name", "username", "cmdline"]):
            try:
                info = proc.info
                name = str(info.get("name") or "")
                cmdline = [str(item) for item in (info.get("cmdline") or [])]
                joined = " ".join(cmdline).lower()
                matched = name.lower() in targets or (bool(needle) and needle in joined)
                if not matched:
                    continue
                create_time = proc.create_time()
                found.append(
                    {
                        "pid": info.get("pid"),
                        "name": name,
                        "username": info.get("username") or "",
                        "cmdline": cmdline,
                        "create_time": create_time,
                        "running_seconds": max(0.0, now.timestamp() - create_time),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as exc:  # noqa: BLE001 - 探测必须永不中断
                self.logger.debug("读取进程信息失败: %s", exc)
                continue
        return found

    def detect_install_locations(self) -> list[Path]:
        """按平台惯例枚举可能的游戏安装位置。

        解析顺序：

        1. Windows：读取注册表卸载信息中的 ``InstallLocation`` /
           ``UninstallString``，反推出可执行文件所在目录；
        2. 平台常见路径（Windows Program Files / AppData，Linux
           ``~/.local/share`` 与 ``/usr/share/games``，macOS ``/Applications``
           与 ``~/Applications``）；
        3. 配置的数据目录（``~/.dwrg/game``）。

        所有平台分支都做了降级：注册表不可用（非 Windows 或权限不足）时
        直接跳过，不会抛出异常。结果只保留真实存在且含已知可执行文件名
        （见 :data:`GAME_EXECUTABLE_NAMES`）的目录，因此返回值可直接当作
        「已发现的安装位置」使用。

        Returns:
            按优先级排列的**目录**路径列表，已去重且保持顺序。
        """
        candidates: list[Path] = []
        for location in self._registry_install_locations():
            candidates.append(location)
        candidates.extend(self._default_install_locations())
        return [
            path
            for path in self._dedupe_paths(candidates)
            if self._contains_executable(path)
        ]

    def _contains_executable(self, directory: Path) -> bool:
        """判断目录中是否存在已知的游戏可执行文件。

        Args:
            directory: 待检查的目录。

        Returns:
            目录存在且含任一已知可执行文件名时返回 ``True``。
        """
        if not directory.is_dir():
            return False
        return any((directory / name).is_file() for name in GAME_EXECUTABLE_NAMES)

    def _registry_install_locations(self) -> list[Path]:
        """从 Windows 注册表卸载信息反推安装目录。

        Returns:
            目录路径列表；非 Windows 平台或读取失败时返回空列表。
        """
        if self.platform != "windows":
            return []
        try:
            winreg: Any = importlib.import_module("winreg")
        except (ImportError, OSError) as exc:  # pragma: no cover - 依平台而定
            self.logger.debug("无法导入 winreg，跳过注册表探测: %s", exc)
            return []

        roots: list[int] = []
        for attribute in ("HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER"):
            value = getattr(winreg, attribute, None)
            if isinstance(value, int):
                roots.append(value)
        if not roots:  # pragma: no cover - 极端平台
            return []

        locations: list[Path] = []
        for root in roots:
            for sub_key in _WINDOWS_UNINSTALL_KEYS:
                locations.extend(self._scan_uninstall_key(winreg, root, sub_key))
        return locations

    def _scan_uninstall_key(self, winreg: Any, root: int, sub_key: str) -> list[Path]:
        """扫描单个卸载信息根键下的所有子项。

        Args:
            winreg: 已导入的 ``winreg`` 模块。
            root: 注册表根键句柄。
            sub_key: 卸载信息键路径。

        Returns:
            从 ``InstallLocation`` / ``UninstallString`` 推出的目录列表。
        """
        found: list[Path] = []
        try:
            with winreg.OpenKey(root, sub_key) as key:
                total = winreg.QueryInfoKey(key)[0]
                for index in range(total):
                    try:
                        child_name = winreg.EnumKey(key, index)
                    except OSError:  # pragma: no cover - 并发删除子项
                        continue
                    found.extend(
                        self._read_uninstall_entry(winreg, root, sub_key, child_name)
                    )
        except OSError as exc:
            self.logger.debug("读取注册表 %s 失败: %s", sub_key, exc)
            return found
        return found

    def _read_uninstall_entry(
        self, winreg: Any, root: int, sub_key: str, child_name: str
    ) -> list[Path]:
        """读取单个卸载项并反推其安装目录。

        Args:
            winreg: 已导入的 ``winreg`` 模块。
            root: 注册表根键句柄。
            sub_key: 卸载信息键路径。
            child_name: 子项名称（通常是 GUID 或程序名）。

        Returns:
            该卸载项指示的目录列表；信息不含路径时返回空列表。
        """
        path = f"{sub_key}\\{child_name}"
        try:
            with winreg.OpenKey(root, path) as entry:
                values: list[str] = []
                for value_name in ("InstallLocation", "UninstallString"):
                    try:
                        values.append(str(winreg.QueryValueEx(entry, value_name)[0]))
                    except OSError:
                        continue
        except OSError as exc:
            self.logger.debug("读取卸载项 %s 失败: %s", path, exc)
            return []

        result: list[Path] = []
        for raw in values:
            cleaned = raw.strip().strip('"')
            if not cleaned:
                continue
            candidate = Path(cleaned).expanduser()
            if candidate.suffix.lower() in {".exe", ".bat", ".cmd"}:
                candidate = candidate.parent
            if candidate.is_dir():
                result.append(candidate)
        return result

    def _default_install_locations(self) -> list[Path]:
        """返回平台惯例上的常见安装目录。

        Returns:
            候选目录列表（不保证存在）。
        """
        home = Path.home()
        candidates: list[Path] = []

        if self.platform == "windows":
            program_dirs = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
                Path(os.environ.get("ProgramW6432", "C:\\Program Files")),
            ]
            for folder in (
                "IdentityV",
                "Identity V",
                "dwrg",
                "NetEase Games",
            ):
                candidates.extend(directory / folder for directory in program_dirs)
            local = Path(
                os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
            )
            candidates.extend(
                [
                    local / "IdentityV",
                    local / "NetEase" / "IdentityV",
                    home / "AppData" / "Local" / "IdentityV",
                ]
            )
        elif self.platform == "darwin":
            candidates.extend(
                [
                    Path("/Applications") / "IdentityV.app",
                    Path("/Applications") / "Identity V.app",
                    home / "Applications" / "IdentityV.app",
                ]
            )
        else:
            candidates.extend(
                [
                    home / ".local" / "share" / "IdentityV",
                    home / ".local" / "share" / "games" / "IdentityV",
                    home / "Games" / "IdentityV",
                    Path("/usr/share/games") / "IdentityV",
                    Path("/usr/local/share/games") / "IdentityV",
                    Path("/opt") / "IdentityV",
                ]
            )

        candidates.append(home / ".dwrg" / "game")
        return candidates

    @staticmethod
    def _dedupe_paths(paths: list[Path]) -> list[Path]:
        """按首次出现顺序去重路径。

        Args:
            paths: 可能重复的路径列表。

        Returns:
            去重后的路径列表（不存在的路径也保留，交由调用方判断）。
        """
        seen: set[str] = set()
        result: list[Path] = []
        for item in paths:
            key = str(item).lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def free_space_bytes(path: str | Path) -> int:
        """返回路径所在文件系统的可用字节数。

        Args:
            path: 目标路径（文件或目录均可）。

        Returns:
            可用字节数；无法读取时返回 ``0``。
        """
        target = Path(path).expanduser()
        try:
            return shutil.disk_usage(target).free
        except OSError:
            # 目标尚不存在时退回到最近的父目录再试一次
            try:
                return shutil.disk_usage(target.parent).free
            except OSError:
                return 0

    @staticmethod
    def is_writable(path: str | Path) -> bool:
        """判断目录是否可写。

        采用「写临时文件」的实测方式，而不是 ``os.access``：后者在 Windows 上
        对只读目录仍可能返回 ``True``，无法反映真实写入能力。

        Args:
            path: 目标目录；不存在时返回 ``False``。

        Returns:
            可写入返回 ``True``。
        """
        target = Path(path).expanduser()
        if not target.is_dir():
            return False
        probe = target / f".dwrg-write-test-{os.getpid()}"
        try:
            probe.write_text("", encoding="utf-8")
        except OSError:
            return False
        finally:
            try:
                probe.unlink()
            except OSError:  # pragma: no cover - 尽力清理
                pass
        return True

    @staticmethod
    def key_file_mode_ok(path: str | Path) -> bool:
        """判断密钥文件权限是否为 0600（仅属主可读写）。

        Windows 上 POSIX 权限位由文件系统映射得到，因此这里放宽为
        「不存在组/其他读写位」；POSIX 平台则严格要求 ``0600``。

        Args:
            path: 密钥文件路径。

        Returns:
            权限合规返回 ``True``；文件不存在或读取失败时返回 ``False``。
        """
        target = Path(path).expanduser()
        try:
            mode = stat.S_IMODE(os.stat(target).st_mode)
        except OSError:
            return False
        if os.name == "nt":
            return not (
                mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
            )
        return mode == 0o600

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


__all__ = ["GAME_EXECUTABLE_NAMES", "GAME_PROCESS_NAMES", "SystemManager"]
