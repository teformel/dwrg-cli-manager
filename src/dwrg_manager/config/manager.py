"""
配置管理器
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..utils.crypto import encrypt_data
from ..utils.logger import get_logger
from .models import AccountConfig, AppConfig, Config, ServerConfig


class DateTimeEncoder(json.JSONEncoder):
    """自定义JSON编码器，支持datetime对象"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: str | None = None):
        self.logger = get_logger(__name__)
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()

    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        home_dir = Path.home()
        config_dir = home_dir / ".config" / "dwrg"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "config.yaml")

    def _load_config(self) -> Config:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding='utf-8') as f:
                    if self.config_path.endswith('.json'):
                        data = json.load(f)
                    else:
                        data = yaml.safe_load(f)

                self.logger.info(f"加载配置文件: {self.config_path}")
                return Config(**data)
            else:
                self.logger.info("配置文件不存在，创建默认配置")
                return Config()
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            return Config()

    def save_config(self):
        """保存配置文件"""
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            # 转换为字典
            config_dict = self.config.dict()

            # 保存到文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.endswith('.json'):
                    json.dump(config_dict, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

            self.logger.info(f"保存配置文件: {self.config_path}")
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            raise

    def get_config(self) -> Config:
        """获取配置对象"""
        return self.config

    def get_app_config(self) -> AppConfig:
        """获取应用配置"""
        return self.config.app

    def get_server_config(self, name: str) -> ServerConfig | None:
        """获取服务器配置"""
        return self.config.get_server(name)

    def get_account_config(self, account_id: str) -> AccountConfig | None:
        """获取账号配置"""
        return self.config.get_account(account_id)

    def get_current_server(self) -> ServerConfig | None:
        """获取当前服务器配置"""
        return self.config.get_current_server()

    def get_current_account(self) -> AccountConfig | None:
        """获取当前账号配置"""
        return self.config.get_current_account()

    def set_config(self, key: str, value: Any):
        """设置配置项"""
        try:
            if key == "server":
                self.config.app.server = value
            elif key == "account":
                self.config.app.account = value
            elif key == "auto_update":
                self.config.app.auto_update = value
            elif key == "verbose":
                self.config.app.verbose = value
            elif key == "language":
                self.config.app.language = value
            elif key == "data_dir":
                self.config.app.data_dir = value
            elif key == "cache_dir":
                self.config.app.cache_dir = value
            elif key == "log_level":
                self.config.app.log_level = value
            elif key == "max_concurrent_downloads":
                self.config.app.max_concurrent_downloads = value
            elif key == "download_timeout":
                self.config.app.download_timeout = value
            else:
                # 尝试设置嵌套配置
                keys = key.split('.')
                if len(keys) == 2 and keys[0] == 'app':
                    setattr(self.config.app, keys[1], value)
                else:
                    raise ValueError(f"不支持的配置项: {key}")

            self.save_config()
            self.logger.info(f"设置配置: {key} = {value}")
        except Exception as e:
            self.logger.error(f"设置配置失败: {e}")
            raise

    def unset_config(self, key: str):
        """删除配置项"""
        try:
            if key == "server":
                self.config.app.server = "official"
            elif key == "account":
                self.config.app.account = None
            elif key == "auto_update":
                self.config.app.auto_update = True
            elif key == "verbose":
                self.config.app.verbose = False
            elif key == "language":
                self.config.app.language = "zh-CN"
            elif key == "data_dir":
                self.config.app.data_dir = "~/.dwrg"
            elif key == "cache_dir":
                self.config.app.cache_dir = "~/.dwrg/cache"
            elif key == "log_level":
                self.config.app.log_level = "INFO"
            elif key == "max_concurrent_downloads":
                self.config.app.max_concurrent_downloads = 5
            elif key == "download_timeout":
                self.config.app.download_timeout = 300
            else:
                raise ValueError(f"不支持的配置项: {key}")

            self.save_config()
            self.logger.info(f"删除配置: {key}")
        except Exception as e:
            self.logger.error(f"删除配置失败: {e}")
            raise

    def add_server(self, name: str, endpoint: str, region: str = "CN",
                  status: str = "active", version: str = "1.0.0",
                  is_default: bool = False) -> ServerConfig:
        """添加服务器配置"""
        try:
            server = ServerConfig(
                name=name,
                endpoint=endpoint,
                region=region,
                status=status,
                version=version,
                is_default=is_default
            )

            self.config.add_server(server)

            # 如果设置为默认服务器，更新其他服务器
            if is_default:
                for srv_name, srv_config in self.config.servers.items():
                    srv_config.is_default = (srv_name == name)

            self.save_config()
            self.logger.info(f"添加服务器: {name}")
            return server
        except Exception as e:
            self.logger.error(f"添加服务器失败: {e}")
            raise

    def remove_server(self, name: str) -> bool:
        """删除服务器配置"""
        try:
            success = self.config.remove_server(name)
            if success:
                # 如果删除的是当前服务器，重置为官方服
                if self.config.app.server == name:
                    self.config.app.server = "official"
                self.save_config()
                self.logger.info(f"删除服务器: {name}")
            return success
        except Exception as e:
            self.logger.error(f"删除服务器失败: {e}")
            raise

    def add_account(self, username: str, server: str, password: str,
                   account_id: str | None = None) -> AccountConfig:
        """添加账号配置"""
        try:
            # 生成账号ID
            if not account_id:
                import uuid
                account_id = str(uuid.uuid4())

            # 加密密码
            encrypted_password = encrypt_data(password)

            # 创建账号配置
            account = AccountConfig(
                id=account_id,
                username=username,
                server=server,
                encrypted_password=encrypted_password,
                last_login=datetime.now(),
                is_current=False
            )

            self.config.add_account(account)
            self.save_config()
            self.logger.info(f"添加账号: {username} ({account_id})")
            return account
        except Exception as e:
            self.logger.error(f"添加账号失败: {e}")
            raise

    def remove_account(self, account_id: str) -> bool:
        """删除账号配置"""
        try:
            success = self.config.remove_account(account_id)
            if success:
                # 如果删除的是当前账号，重置
                if self.config.app.account == account_id:
                    self.config.app.account = None
                self.save_config()
                self.logger.info(f"删除账号: {account_id}")
            return success
        except Exception as e:
            self.logger.error(f"删除账号失败: {e}")
            raise

    def switch_account(self, account_id: str) -> bool:
        """切换当前账号"""
        try:
            # 重置所有账号的当前状态
            for acc in self.config.accounts.values():
                acc.is_current = (acc.id == account_id)

            self.config.app.account = account_id
            self.save_config()
            self.logger.info(f"切换账号: {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"切换账号失败: {e}")
            return False

    def switch_server(self, server_name: str) -> bool:
        """切换当前服务器"""
        try:
            # 重置所有服务器的默认状态
            for srv in self.config.servers.values():
                srv.is_default = (srv.name == server_name)

            self.config.app.server = server_name
            self.save_config()
            self.logger.info(f"切换服务器: {server_name}")
            return True
        except Exception as e:
            self.logger.error(f"切换服务器失败: {e}")
            return False

    def list_servers(self) -> list:
        """列出所有服务器"""
        return list(self.config.servers.values())

    def list_accounts(self, server: str | None = None) -> list:
        """列出所有账号"""
        accounts = list(self.config.accounts.values())
        if server:
            accounts = [acc for acc in accounts if acc.server == server]
        return accounts

    def export_config(self, export_path: str, format: str = "yaml") -> bool:
        """导出配置"""
        try:
            config_dict = self.config.dict()

            with open(export_path, 'w', encoding='utf-8') as f:
                if format == "json":
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

            self.logger.info(f"导出配置到: {export_path}")
            return True
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """导入配置"""
        try:
            with open(import_path, encoding='utf-8') as f:
                if import_path.endswith('.json'):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)

            self.config = Config(**data)
            self.save_config()
            self.logger.info(f"导入配置从: {import_path}")
            return True
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            return False
