#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
账号管理功能测试
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dwrg_manager.config.manager import ConfigManager
from dwrg_manager.accounts.manager import AccountManager
from dwrg_manager.accounts.models import Account
from dwrg_manager.utils.security import encrypt_data, decrypt_data, generate_key

def test_account_creation():
    """测试账号创建功能"""
    print("测试账号创建...")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        # 初始化配置管理器
        config_manager = ConfigManager(config_path)
        account_manager = AccountManager()
        account_manager.config_manager = config_manager
        
        # 测试创建账号
        username = "test_user"
        server = "official"
        password = "test_password"
        
        account = account_manager.create_account(username, server, password)
        
        # 验证账号创建
        assert account is not None
        assert account.username == username
        assert account.server == server
        assert account.encrypted_password != password  # 应该是加密的
        
        print("✓ 账号创建测试通过")
        
        # 测试列出账号
        accounts = account_manager.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].username == username
        
        print("✓ 账号列表测试通过")
        
        # 测试获取账号
        retrieved_account = account_manager.get_account(account.id)
        assert retrieved_account is not None
        assert retrieved_account.username == username
        
        print("✓ 账号获取测试通过")
        
        # 测试切换账号
        success = account_manager.switch_account(account.id)
        assert success
        
        print("✓ 账号切换测试通过")
        
        # 测试获取当前账号
        current_account = account_manager.get_current_account()
        assert current_account is not None
        assert current_account.id == account.id
        
        print("✓ 当前账号获取测试通过")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)

def test_account_encryption():
    """测试账号加密功能"""
    print("测试账号加密...")
    
# 测试加密解密
    password = "test_password"
    encrypted = encrypt_data(password, password)
    decrypted = decrypt_data(encrypted, password)
    
    assert decrypted == password
    assert encrypted != password
    
    print("✓ 加密解密测试通过")
    
    return True

if __name__ == "__main__":
    print("开始账号管理功能测试")
    print("=" * 50)
    
    # 运行测试
    test1_passed = test_account_creation()
    test2_passed = test_account_encryption()
    
    print("=" * 50)
    if test1_passed and test2_passed:
        print("所有测试通过！✓")
        sys.exit(0)
    else:
        print("部分测试失败！✗")
        sys.exit(1)