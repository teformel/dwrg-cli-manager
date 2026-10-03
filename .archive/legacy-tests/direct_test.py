"""
直接测试核心模块
"""

import os
import sys

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_config():
    """测试配置模块"""
    print("测试配置模块...")

    # 直接导入配置模块
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'dwrg_manager', 'config'))
    from models import AccountConfig, ServerConfig

    # 测试配置模型
    server = ServerConfig(
        name="test_server",
        endpoint="https://test.example.com",
        region="CN"
    )
    assert server.name == "test_server"

    account = AccountConfig(
        id="test12345678",
        username="test_user",
        server="official",
        encrypted_password="encrypted_pass"
    )
    assert account.username == "test_user"

    print("✓ 配置模块测试通过")


def test_crypto():
    """测试加密模块"""
    print("测试加密模块...")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'dwrg_manager', 'utils'))
    from crypto import decrypt_data, encrypt_data

    original_data = "test_password"

    # 加密
    encrypted = encrypt_data(original_data)
    assert encrypted != original_data

    # 解密
    decrypted = decrypt_data(encrypted)
    assert decrypted == original_data

    print("✓ 加密模块测试通过")


def test_system():
    """测试系统模块"""
    print("测试系统模块...")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'dwrg_manager', 'utils'))
    from system import SystemManager

    system_manager = SystemManager()

    # 获取系统信息
    info = system_manager.get_system_info()
    assert 'platform' in info
    assert 'system' in info

    # 获取文件信息
    file_info = system_manager.get_file_info(__file__)
    assert 'size' in file_info

    print("✓ 系统模块测试通过")


if __name__ == "__main__":
    try:
        test_config()
        test_crypto()
        test_system()
        print("\n🎉 所有测试通过！")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
