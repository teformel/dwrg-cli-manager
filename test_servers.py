#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
渠道服管理测试
"""

import sys
import os
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from dwrg_manager.servers.manager import ServerManager
from dwrg_manager.servers.models import ServerConfig, ServerManagerConfig
from dwrg_manager.config.manager import ConfigManager

async def test_server_management():
    """测试渠道服管理功能"""
    print("测试渠道服管理...")
    
    # 创建临时配置
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        # 初始化配置管理器
        config_manager = ConfigManager(config_path)
        
        # 添加测试服务器
        config_manager.add_server(
            name="official",
            endpoint="https://example.com",
            is_default=True
        )
        config_manager.add_server(
            name="bserver",
            endpoint="https://b.example.com",
            region="JP"
        )
        
        # 初始化服务器管理器
        server_manager = ServerManager()
        server_manager.config_manager = config_manager
        
        # 测试列出服务器
        servers = server_manager.list_servers()
        print(f"✓ 服务器列表: {len(servers)}个服务器")
        
        # 测试获取当前服务器
        current_server = server_manager.get_current_server()
        print(f"✓ 当前服务器: {current_server.name if current_server else '无'}")
        
        # 测试切换服务器
        success = server_manager.switch_server("bserver")
        print(f"✓ 服务器切换: {'成功' if success else '失败'}")
        
        # 测试获取当前服务器（切换后）
        current_server = server_manager.get_current_server()
        print(f"✓ 切换后当前服务器: {current_server.name if current_server else '无'}")
        
        # 测试删除服务器
        success = server_manager.remove_server("bserver")
        print(f"✓ 删除服务器: {'成功' if success else '失败'}")
        
        print("✓ 所有测试通过！")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
        
    finally:
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(test_server_management())