#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最终测试
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

# 测试安全模块
try:
    from dwrg_manager.utils.security import encrypt_data, decrypt_data
    print("✓ 安全模块导入成功")
except ImportError as e:
    print(f"✗ 安全模块导入失败: {e}")
    sys.exit(1)

# 测试加密
password = "test_password"
data = "test_data"
encrypted = encrypt_data(data, password)
print(f"✓ 加密成功: {encrypted}")

decrypted = decrypt_data(encrypted, password)
print(f"✓ 解密成功: {decrypted}")

assert decrypted == data
print("✓ 加密解密验证通过")

# 测试账号管理器
try:
    from dwrg_manager.accounts.manager import AccountManager
    print("✓ 账号管理器导入成功")
except ImportError as e:
    print(f"✗ 账号管理器导入失败: {e}")
    sys.exit(1)

# 创建临时配置
import tempfile
import shutil
temp_dir = tempfile.mkdtemp()
config_path = os.path.join(temp_dir, "config.json")

try:
    from dwrg_manager.config.manager import ConfigManager
    config_manager = ConfigManager(config_path)
    account_manager = AccountManager()
    account_manager.config_manager = config_manager
    
    # 测试创建账号
    account = account_manager.create_account("test_user", "official", "test_password")
    print("✓ 账号创建成功")
    
    # 测试列出账号
    accounts = account_manager.list_accounts()
    print(f"✓ 账号列表: {len(accounts)}个账号")
    
    # 测试获取账号
    retrieved = account_manager.get_account(account.id)
    print("✓ 账号获取成功")
    
    print("✓ 所有测试通过！")
    
finally:
    shutil.rmtree(temp_dir)