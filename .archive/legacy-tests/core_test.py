"""
简单的核心框架测试
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dwrg_manager.config.manager import ConfigManager
from dwrg_manager.utils.crypto import decrypt_data, encrypt_data
from dwrg_manager.utils.system import SystemManager


def test_config_manager():
    """测试配置管理器"""
    print("测试配置管理器...")

    config_manager = ConfigManager()

    # 设置配置
    config_manager.set_config("auto_update", False)
    config_manager.set_config("verbose", True)

    # 获取配置
    config = config_manager.get_config()
    assert config['app']['auto_update'] is False
    assert config['app']['verbose'] is True
    print("✓ 配置管理器测试通过")


def test_crypto():
    """测试加密功能"""
    print("测试加密功能...")

    original_data = "test_password"

    # 加密
    encrypted = encrypt_data(original_data)
    assert encrypted != original_data

    # 解密
    decrypted = decrypt_data(encrypted)
    assert decrypted == original_data
    print("✓ 加密功能测试通过")


def test_system_manager():
    """测试系统管理器"""
    print("测试系统管理器...")

    system_manager = SystemManager()

    # 获取系统信息
    info = system_manager.get_system_info()
    assert 'platform' in info
    assert 'system' in info
    assert 'python_version' in info

    # 获取文件信息
    file_info = system_manager.get_file_info(__file__)
    assert 'size' in file_info
    assert 'modified' in file_info
    print("✓ 系统管理器测试通过")


if __name__ == "__main__":
    try:
        test_config_manager()
        test_crypto()
        test_system_manager()
        print("\n🎉 所有测试通过！")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
