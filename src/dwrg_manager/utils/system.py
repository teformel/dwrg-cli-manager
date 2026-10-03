"""
系统工具
"""

import logging
import os
import platform
import subprocess
from datetime import datetime

import psutil


def get_logger(name: str = "dwrg") -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


class SystemManager:
    """系统管理器"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.platform = platform.system().lower()

    def get_system_info(self) -> dict[str, str]:
        """获取系统信息"""
        info = {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
        }

        # 添加特定平台信息
        if self.platform == 'windows':
            info['windows_version'] = self._get_windows_version()
        elif self.platform == 'linux':
            info['distribution'] = platform.dist()[0] if platform.dist() else 'Unknown'
        elif self.platform == 'darwin':
            info['mac_version'] = platform.mac_ver()[0]

        return info

    def _get_windows_version(self) -> str:
        """获取Windows版本信息"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion")
            version = winreg.QueryValueEx(key, "ProductName")[0]
            winreg.CloseKey(key)
            return version
        except:
            return "Unknown"

    def get_disk_info(self) -> list[dict[str, str]]:
        """获取磁盘信息"""
        disk_info = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': self._format_bytes(usage.total),
                    'used': self._format_bytes(usage.used),
                    'free': self._format_bytes(usage.free),
                    'percent': f"{usage.percent:.1f}%"
                })
            except PermissionError:
                continue

        return disk_info

    def get_memory_info(self) -> dict[str, str]:
        """获取内存信息"""
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            'total': self._format_bytes(memory.total),
            'available': self._format_bytes(memory.available),
            'used': self._format_bytes(memory.used),
            'percent': f"{memory.percent:.1f}%",
            'swap_total': self._format_bytes(swap.total),
            'swap_used': self._format_bytes(swap.used),
            'swap_percent': f"{swap.percent:.1f}%"
        }

    def get_process_info(self, process_name: str | None = None) -> list[dict[str, str]]:
        """获取进程信息"""
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'username', 'memory_percent', 'cpu_percent']):
            try:
                if process_name is None or proc.info['name'].lower() == process_name.lower():
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'username': proc.info['username'],
                        'memory_percent': f"{proc.info['memory_percent']:.1f}%",
                        'cpu_percent': f"{proc.info['cpu_percent']:.1f}%"
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes

    def check_game_process(self) -> dict[str, str] | None:
        """检查游戏进程"""
        # 常见的游戏进程名
        game_processes = ['IdentityV.exe', 'identityv.exe', 'game.exe']

        for proc_name in game_processes:
            processes = self.get_process_info(proc_name)
            if processes:
                return processes[0]

        return None

    def kill_process(self, pid: int) -> bool:
        """终止进程"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            self.logger.info(f"终止进程: {pid}")
            return True
        except psutil.NoSuchProcess:
            self.logger.warning(f"进程不存在: {pid}")
            return False
        except psutil.AccessDenied:
            self.logger.error(f"无权限终止进程: {pid}")
            return False
        except Exception as e:
            self.logger.error(f"终止进程失败: {e}")
            return False

    def create_directory(self, path: str) -> bool:
        """创建目录"""
        try:
            os.makedirs(path, exist_ok=True)
            self.logger.info(f"创建目录: {path}")
            return True
        except Exception as e:
            self.logger.error(f"创建目录失败: {e}")
            return False

    def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(path)

    def file_size(self, path: str) -> int:
        """获取文件大小"""
        try:
            return os.path.getsize(path)
        except:
            return 0

    def get_file_info(self, path: str) -> dict[str, str]:
        """获取文件信息"""
        try:
            stat = os.stat(path)
            return {
                'size': self._format_bytes(stat.st_size),
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'is_file': os.path.isfile(path),
                'is_dir': os.path.isdir(path),
                'is_executable': os.access(path, os.X_OK)
            }
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {e}")
            return {}

    def run_command(self, command: list[str], timeout: int = 300) -> dict[str, str]:
        """运行命令"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )

            return {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            self.logger.error(f"命令执行超时: {' '.join(command)}")
            return {'error': '命令执行超时'}
        except subprocess.CalledProcessError as e:
            self.logger.error(f"命令执行失败: {e}")
            return {'error': str(e), 'returncode': e.returncode}
        except Exception as e:
            self.logger.error(f"命令执行异常: {e}")
            return {'error': str(e)}

    def _format_bytes(self, bytes_value: int) -> str:
        """格式化字节大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    def get_network_interfaces(self) -> list[dict[str, str]]:
        """获取网络接口信息"""
        interfaces = []

        try:
            for name, addresses in psutil.net_if_addrs().items():
                for addr in addresses:
                    if addr.family == psutil.AF_INET:
                        interfaces.append({
                            'interface': name,
                            'address': addr.address,
                            'netmask': addr.netmask,
                            'broadcast': addr.broadcast
                        })
        except Exception as e:
            self.logger.error(f"获取网络接口信息失败: {e}")

        return interfaces

    def check_port(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr and conn.laddr.port == port:
                    return True
            return False
        except Exception as e:
            self.logger.error(f"检查端口失败: {e}")
            return False
