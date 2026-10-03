#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安全工具测试
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dwrg_manager.utils.security import encrypt_data, decrypt_data

def test_encryption():
    """测试加密解密功能"""
    print("测试加密解密...")
    
    password = "test_password"
    data = "test_data"
    
    # 加密数据
    encrypted = encrypt_data(data, password)
    print(f"加密结果: {encrypted}")
    
    # 解密数据
    decrypted = decrypt_data(encrypted, password)
    print(f"解密结果: {decrypted}")
    
    # 验证
    assert decrypted == data
    assert encrypted != data
    
    print("✓ 加密解密测试通过")
    return True

if __name__ == "__main__":
    test_encryption()