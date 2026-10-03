"""
基础使用示例
"""

import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from dwrg_manager.accounts.manager import AccountManager
from dwrg_manager.servers.manager import ServerManager


def main():
    """基础使用示例"""
    print("=== 第五人格命令行管理器 - 基础使用示例 ===\n")
    
    # 初始化管理器
    account_manager = AccountManager()
    server_manager = ServerManager()
    
    # 1. 列出渠道服
    print("1. 列出所有渠道服:")
    servers = server_manager.list_servers()
    for server in servers:
        print(f"   - {server.display_name} ({server.name}) - {server.status}")
    print()
    
    # 2. 添加账号
    print("2. 添加账号:")
    try:
        account = account_manager.create_account(
            username="test_player",
            server="official",
            password="test_password123"
        )
        print(f"   ✓ 账号创建成功: {account.username}")
    except Exception as e:
        print(f"   ✗ 账号创建失败: {e}")
    print()
    
    # 3. 列出账号
    print("3. 列出所有账号:")
    accounts = account_manager.list_accounts()
    for acc in accounts:
        print(f"   - {acc.username} ({acc.server})")
    print()
    
    # 4. 切换账号
    print("4. 切换账号:")
    if accounts:
        account_id = accounts[0].id
        success = account_manager.switch_account(account_id)
        if success:
            print(f"   ✓ 账号切换成功: {accounts[0].username}")
        else:
            print("   ✗ 账号切换失败")
    print()
    
    # 5. 显示当前状态
    print("5. 当前状态:")
    current_account = account_manager.get_current_account()
    current_server = server_manager.get_current_server()
    
    if current_account:
        print(f"   当前账号: {current_account.username}")
    if current_server:
        print(f"   当前渠道服: {current_server.display_name}")
    print()
    
    # 6. 清理测试数据
    print("6. 清理测试数据:")
    if accounts:
        for acc in accounts:
            account_manager.remove_account(acc.id)
            print(f"   ✓ 删除账号: {acc.username}")
    print()
    
    print("=== 示例完成 ===")


if __name__ == "__main__":
    main()