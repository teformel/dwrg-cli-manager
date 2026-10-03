#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试测试
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("开始调试测试...")
print("=" * 50)

# 测试导入
try:
    from dwrg_manager.utils.security import encrypt_data, decrypt_data
    print("✓ 安全模块导入成功")
except ImportError as e:
    print(f"✗ 安全模块导入失败: {e}")

# 测试加密函数
try:
    password = "test_password"
    data = "test_data"
    encrypted = encrypt_data(data, password)
    print(f"✓ 加密成功: {encrypted}")
    
    decrypted = decrypt_data(encrypted, password)
    print(f"✓ 解密成功: {decrypted}")
    
    if decrypted == data:
        print("✓ 加密解密验证通过")
    else:
        print("✗ 加密解密验证失败")
        
except Exception as e:
    print(f"✗ 加密解密测试失败: {e}")

print("=" * 50)