"""
完整项目测试
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_all_modules():
    """测试所有模块"""
    print("🧪 开始测试所有模块...")

    # 测试配置管理器
    print("\n1. 测试配置管理器...")
    try:
        from dwrg_manager.config.manager import ConfigManager
        config_manager = ConfigManager()

        # 设置配置
        config_manager.set_config("auto_update", False)
        config_manager.set_config("verbose", True)

        # 添加服务器
        config_manager.add_server(
            name="test_server",
            endpoint="https://test.example.com",
            region="CN"
        )

        # 添加账号
        account = config_manager.add_account(
            username="test_user",
            server="official",
            password="test_password"
        )

        print("✓ 配置管理器测试通过")
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        return False

    # 测试加密模块
    print("\n2. 测试加密模块...")
    try:
        from dwrg_manager.utils.crypto import decrypt_data, encrypt_data

        original_data = "test_password"
        encrypted = encrypt_data(original_data)
        decrypted = decrypt_data(encrypted)

        assert decrypted == original_data
        print("✓ 加密模块测试通过")
    except Exception as e:
        print(f"❌ 加密模块测试失败: {e}")
        return False

    # 测试系统模块
    print("\n3. 测试系统模块...")
    try:
        from dwrg_manager.utils.system import SystemManager

        system_manager = SystemManager()
        info = system_manager.get_system_info()
        assert 'platform' in info

        file_info = system_manager.get_file_info(__file__)
        assert 'size' in file_info

        print("✓ 系统模块测试通过")
    except Exception as e:
        print(f"❌ 系统模块测试失败: {e}")
        return False

    # 测试账号管理器
    print("\n4. 测试账号管理器...")
    try:
        from dwrg_manager.accounts.manager import AccountManager

        account_manager = AccountManager()

        # 创建账号
        account = account_manager.create_account(
            username="test_user2",
            server="official",
            password="test_password"
        )
        assert account.username == "test_user2"

        # 列出账号
        accounts = account_manager.list_accounts()
        assert len(accounts) > 0

        print("✓ 账号管理器测试通过")
    except Exception as e:
        print(f"❌ 账号管理器测试失败: {e}")
        return False

    # 测试服务器管理器
    print("\n5. 测试服务器管理器...")
    try:
        from dwrg_manager.servers.manager import ServerManager

        server_manager = ServerManager()

        # 列出服务器
        servers = server_manager.list_servers()
        assert len(servers) > 0

        # 获取服务器
        server = server_manager.get_server("official")
        assert server is not None

        print("✓ 服务器管理器测试通过")
    except Exception as e:
        print(f"❌ 服务器管理器测试失败: {e}")
        return False

    print("\n🎉 所有模块测试通过！")
    return True

if __name__ == "__main__":
    success = test_all_modules()
    sys.exit(0 if success else 1)
