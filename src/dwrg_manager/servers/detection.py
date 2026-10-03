"""
渠道服检测工具
"""

import time
from typing import Any

import aiohttp


async def ping_server(endpoint: str, timeout: int = 10) -> float:
    """检测服务器延迟"""
    try:
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=timeout) as response:
                await response.text()
        end_time = time.time()
        return (end_time - start_time) * 1000  # 转换为毫秒
    except Exception as e:
        raise Exception(f"服务器连接失败: {e}")


async def check_server_status(endpoint: str, timeout: int = 10) -> dict[str, Any]:
    """检查服务器状态"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{endpoint}/status", timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"服务器返回状态码: {response.status}")
    except Exception as e:
        raise Exception(f"检查服务器状态失败: {e}")


async def detect_game_version(endpoint: str, timeout: int = 10) -> str:
    """检测游戏版本"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{endpoint}/version", timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('version', 'unknown')
                else:
                    raise Exception(f"获取版本信息失败: {response.status}")
    except Exception as e:
        raise Exception(f"检测游戏版本失败: {e}")


async def detect_server_region(endpoint: str, timeout: int = 10) -> str:
    """检测服务器地区"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{endpoint}/region", timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('region', 'unknown')
                else:
                    raise Exception(f"获取地区信息失败: {response.status}")
    except Exception as e:
        raise Exception(f"检测服务器地区失败: {e}")
