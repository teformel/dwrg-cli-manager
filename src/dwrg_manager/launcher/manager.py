"""
启动管理器
"""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

import psutil

from ..config.manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.system import SystemManager
from .models import GameStatus, LaunchConfig

logger = get_logger(__name__)


class LauncherManager:
    """启动管理器"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.system_manager = SystemManager()
        self.game_process: psutil.Process | None = None
        self.launch_config: LaunchConfig | None = None
        self.start_time: datetime | None = None

    def launch_game(self, account_id: str | None = None,
                   server_name: str | None = None,
                   verbose: bool = False) -> bool:
        """启动游戏"""
        logger.info("准备启动游戏...")

        try:
            # 验证配置
            if not self._validate_launch_config(account_id, server_name):
                return False

            # 获取游戏路径
            game_path = self._get_game_path()
            if not game_path.exists():
                logger.error(f"游戏不存在: {game_path}")
                return False

            # 构建启动命令
            cmd = self._build_launch_command(game_path, account_id, server_name)

            # 设置工作目录
            working_dir = game_path.parent

            # 设置环境变量
            env = self._build_environment()

            # 启动游戏
            if platform.system() == 'Windows':
                # Windows平台
                creation_flags = subprocess.CREATE_NEW_CONSOLE
                if self.launch_config.is_admin:
                    creation_flags |= subprocess.CREATE_NO_WINDOW

                process = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    env=env,
                    creationflags=creation_flags,
                    stdout=subprocess.PIPE if verbose else subprocess.DEVNULL,
                    stderr=subprocess.PIPE if verbose else subprocess.DEVNULL
                )
            else:
                # Unix-like平台
                process = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    env=env,
                    stdout=subprocess.PIPE if verbose else subprocess.DEVNULL,
                    stderr=subprocess.PIPE if verbose else subprocess.DEVNULL
                )

            # 保存进程信息
            self.game_process = psutil.Process(process.pid)
            self.start_time = datetime.now()

            logger.info(f"游戏启动成功，进程ID: {process.pid}")
            return True

        except Exception as e:
            logger.error(f"启动游戏失败: {e}")
            return False

    def stop_game(self, force: bool = False) -> bool:
        """停止游戏"""
        logger.info("准备停止游戏...")

        try:
            if not self.game_process:
                logger.warning("游戏未运行")
                return True

            if force:
                # 强制终止
                self.game_process.kill()
                logger.info("强制终止游戏进程")
            else:
                # 优雅终止
                self.game_process.terminate()

                # 等待进程结束
                try:
                    self.game_process.wait(timeout=10)
                    logger.info("游戏进程已优雅终止")
                except psutil.TimeoutExpired:
                    # 超时后强制终止
                    self.game_process.kill()
                    logger.info("游戏进程已强制终止")

            # 清理状态
            self.game_process = None
            self.start_time = None
            self.launch_config = None

            return True

        except Exception as e:
            logger.error(f"停止游戏失败: {e}")
            return False

    def get_game_status(self) -> GameStatus:
        """获取游戏状态"""
        try:
            if not self.game_process:
                return GameStatus(
                    is_running=False,
                    launch_config=self.launch_config
                )

            # 检查进程是否仍在运行
            if not self.game_process.is_running():
                self.game_process = None
                self.start_time = None
                return GameStatus(
                    is_running=False,
                    launch_config=self.launch_config
                )

            # 获取进程信息
            cpu_usage = self.game_process.cpu_percent()
            memory_info = self.game_process.memory_info()

            # 计算运行时间
            if self.start_time:
                running_time = (datetime.now() - self.start_time).total_seconds()
            else:
                running_time = 0

            return GameStatus(
                is_running=True,
                process_id=self.game_process.pid,
                cpu_usage=cpu_usage,
                memory_usage=memory_info.rss,
                running_time=running_time,
                launch_config=self.launch_config
            )

        except Exception as e:
            logger.error(f"获取游戏状态失败: {e}")
            return GameStatus(
                is_running=False,
                launch_config=self.launch_config
            )

    def _validate_launch_config(self, account_id: str | None,
                              server_name: str | None) -> bool:
        """验证启动配置"""
        try:
            # 获取当前配置
            app_config = self.config_manager.get_app_config()

            # 使用提供的参数或默认值
            final_account_id = account_id or app_config.account
            final_server_name = server_name or app_config.server

            # 验证账号
            if final_account_id:
                account = self.config_manager.get_account_config(final_account_id)
                if not account:
                    logger.error(f"账号不存在: {final_account_id}")
                    return False

            # 验证服务器
            if final_server_name:
                server = self.config_manager.get_server_config(final_server_name)
                if not server:
                    logger.error(f"服务器不存在: {final_server_name}")
                    return False

            # 创建启动配置
            self.launch_config = LaunchConfig(
                account_id=final_account_id,
                server_name=final_server_name,
                launch_params=self._get_default_launch_params(),
                working_dir="",
                env_vars=self._get_default_env_vars(),
                is_admin=False,
                auto_restart=False,
                priority="normal"
            )

            return True

        except Exception as e:
            logger.error(f"验证启动配置失败: {e}")
            return False

    def _get_game_path(self) -> Path:
        """获取游戏路径"""
        # 这里可以根据实际情况调整游戏路径
        app_config = self.config_manager.get_app_config()
        game_path = Path.home() / 'Games' / 'IdentityV' / 'IdentityV.exe'

        if not game_path.exists():
            # 尝试其他可能的路径
            possible_paths = [
                Path('C:/Program Files (x86)/IdentityV/IdentityV.exe'),
                Path('C:/Program Files/IdentityV/IdentityV.exe'),
                Path.home() / 'AppData' / 'Local' / 'IdentityV' / 'IdentityV.exe'
            ]

            for path in possible_paths:
                if path.exists():
                    game_path = path
                    break

        return game_path

    def _build_launch_command(self, game_path: Path,
                             account_id: str | None,
                             server_name: str | None) -> list[str]:
        """构建启动命令"""
        cmd = [str(game_path)]

        # 添加启动参数
        if self.launch_config:
            cmd.extend(self.launch_config.launch_params)

        # 添加账号参数
        if account_id:
            cmd.extend(['-account', account_id])

        # 添加服务器参数
        if server_name:
            cmd.extend(['-server', server_name])

        return cmd

    def _build_environment(self) -> dict[str, str]:
        """构建环境变量"""
        env = os.environ.copy()

        if self.launch_config:
            env.update(self.launch_config.env_vars)

        # 添加游戏特定的环境变量
        env['DWRG_LAUNCHED'] = '1'
        if self.launch_config and self.launch_config.account_id:
            env['DWRG_ACCOUNT'] = self.launch_config.account_id
        if self.launch_config and self.launch_config.server_name:
            env['DWRG_SERVER'] = self.launch_config.server_name

        return env

    def _get_default_launch_params(self) -> list[str]:
        """获取默认启动参数"""
        return [
            '-fullscreen',
            '-high',
            '-thread',
            '4'
        ]

    def _get_default_env_vars(self) -> dict[str, str]:
        """获取默认环境变量"""
        return {
            'DXGI_DEBUG': '1',
            'ENABLE_DX12': '1'
        }

    def diagnose_launch(self) -> dict:
        """诊断启动问题"""
        diagnosis = {
            'game_exists': False,
            'game_path': None,
            'account_valid': False,
            'server_valid': False,
            'disk_space': False,
            'permissions': True,
            'recommendations': []
        }

        try:
            # 检查游戏路径
            game_path = self._get_game_path()
            diagnosis['game_exists'] = game_path.exists()
            diagnosis['game_path'] = str(game_path)

            if not diagnosis['game_exists']:
                diagnosis['recommendations'].append("请确保游戏已正确安装")

            # 检查账号
            if self.launch_config and self.launch_config.account_id:
                account = self.config_manager.get_account_config(self.launch_config.account_id)
                diagnosis['account_valid'] = account is not None
                if not diagnosis['account_valid']:
                    diagnosis['recommendations'].append("请检查账号配置")

            # 检查服务器
            if self.launch_config and self.launch_config.server_name:
                server = self.config_manager.get_server_config(self.launch_config.server_name)
                diagnosis['server_valid'] = server is not None
                if not diagnosis['server_valid']:
                    diagnosis['recommendations'].append("请检查服务器配置")

            # 检查磁盘空间
            disk_info = self.system_manager.get_disk_info()
            if disk_info:
                # 检查C盘空间
                c_drive = next((d for d in disk_info if 'C:' in d['device']), None)
                if c_drive:
                    free_space = int(c_drive['free'].split()[0])  # 假设格式是 "XX GB"
                    diagnosis['disk_space'] = free_space > 10  # 至少10GB空间
                    if not diagnosis['disk_space']:
                        diagnosis['recommendations'].append("磁盘空间不足，请清理磁盘")

            # 检查权限
            if platform.system() == 'Windows':
                import ctypes
                try:
                    # 检查是否是管理员
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                    diagnosis['permissions'] = is_admin
                    if not diagnosis['permissions']:
                        diagnosis['recommendations'].append("建议以管理员权限运行")
                except:
                    diagnosis['permissions'] = True

            return diagnosis

        except Exception as e:
            logger.error(f"诊断启动问题失败: {e}")
            return diagnosis
