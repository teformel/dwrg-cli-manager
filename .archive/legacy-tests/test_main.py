"""
主模块测试
"""

import pytest

from dwrg_manager.config.manager import ConfigManager
from dwrg_manager.main import app
from dwrg_manager.utils.crypto import decrypt_data, encrypt_data
from dwrg_manager.utils.system import SystemManager
from dwrg_manager.utils.version import get_version


def test_version():
    """测试版本获取"""
    version = get_version()
    assert version == "1.0.0"


def test_app_creation():
    """测试应用创建"""
    assert app is not None
    assert app.name == "dwrg"


def test_help_command():
    """测试帮助命令"""
    # 这里需要测试CLI命令，但需要mock typer
    pass


class TestConfigManager:
    """测试配置管理器"""

    def test_load_config(self):
        """测试加载配置"""
        config_manager = ConfigManager()
        assert config_manager is not None
        assert config_manager.config is not None

    def test_set_get_config(self):
        """测试设置和获取配置"""
        config_manager = ConfigManager()

        # 设置配置
        config_manager.set_config("auto_update", False)
        config_manager.set_config("verbose", True)

        # 获取配置
        config = config_manager.get_config()
        assert config['app']['auto_update'] is False
        assert config['app']['verbose'] is True

    def test_server_management(self):
        """测试服务器管理"""
        config_manager = ConfigManager()

        # 添加服务器
        server = config_manager.add_server(
            name="test_server",
            endpoint="https://test.example.com",
            region="CN"
        )
        assert server.name == "test_server"
        assert server.endpoint == "https://test.example.com"

        # 获取服务器
        retrieved_server = config_manager.get_server_config("test_server")
        assert retrieved_server is not None
        assert retrieved_server.name == "test_server"

        # 删除服务器
        success = config_manager.remove_server("test_server")
        assert success is True

    def test_account_management(self):
        """测试账号管理"""
        config_manager = ConfigManager()

        # 添加账号
        account = config_manager.add_account(
            username="test_user",
            server="official",
            password="test_password"
        )
        assert account.username == "test_user"
        assert account.server == "official"

        # 获取账号
        retrieved_account = config_manager.get_account_config(account.id)
        assert retrieved_account is not None
        assert retrieved_account.username == "test_user"


class TestCryptoManager:
    """测试加密管理器"""

    def test_encrypt_decrypt(self):
        """测试加密和解密"""
        original_data = "test_password"

        # 加密
        encrypted = encrypt_data(original_data)
        assert encrypted != original_data

        # 解密
        decrypted = decrypt_data(encrypted)
        assert decrypted == original_data

    def test_invalid_decrypt(self):
        """测试无效的解密数据"""
        with pytest.raises(Exception):
            decrypt_data("invalid_data")


class TestSystemManager:
    """测试系统管理器"""

    def test_system_info(self):
        """测试获取系统信息"""
        system_manager = SystemManager()
        info = system_manager.get_system_info()

        assert 'platform' in info
        assert 'system' in info
        assert 'python_version' in info

    def test_disk_info(self):
        """测试获取磁盘信息"""
        system_manager = SystemManager()
        disk_info = system_manager.get_disk_info()

        assert isinstance(disk_info, list)
        if disk_info:  # 如果有磁盘信息
            assert 'device' in disk_info[0]
            assert 'mountpoint' in disk_info[0]

    def test_memory_info(self):
        """测试获取内存信息"""
        system_manager = SystemManager()
        memory_info = system_manager.get_memory_info()

        assert 'total' in memory_info
        assert 'available' in memory_info
        assert 'used' in memory_info

    def test_file_operations(self):
        """测试文件操作"""
        system_manager = SystemManager()

        # 测试文件存在性检查
        assert system_manager.file_exists(__file__) is True

        # 获取文件信息
        file_info = system_manager.get_file_info(__file__)
        assert 'size' in file_info
        assert 'modified' in file_info
