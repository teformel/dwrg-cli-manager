#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dwrg_manager.utils.security import encrypt_data, decrypt_data

print("简单测试开始...")
print("=" * 50)

# 测试加密
password = "test_password"
data = "test_data"
encrypted = encrypt_data(data, password)
print(f"加密: {encrypted}")

decrypted = decrypt_data(encrypted, password)
print(f"解密: {decrypted}")

assert decrypted == data
print("✓ 加密解密测试通过")

print("=" * 50)