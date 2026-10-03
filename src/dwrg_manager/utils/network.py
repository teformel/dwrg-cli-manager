"""
网络工具

提供渠道服探测所需的最小异步 HTTP 能力。统一使用
:class:`aiohttp.ClientTimeout` 构造超时对象（``aiohttp>=3.11`` 起不再接受
裸数字作为 ``timeout`` 参数），并把底层异常包装为
:class:`~dwrg_manager.exceptions.ServerError`。
"""

from time import perf_counter
from typing import Any

import aiohttp

from ..exceptions import ServerError

#: 默认请求超时（秒）
DEFAULT_TIMEOUT = 10

#: 默认 User-Agent
USER_AGENT = "dwrg-cli-manager/1.0.0"


def _timeout(seconds: int | float) -> aiohttp.ClientTimeout:
    """构造 aiohttp 超时对象。

    Args:
        seconds: 总超时秒数。

    Returns:
        配置了 total 的 :class:`aiohttp.ClientTimeout`。
    """
    return aiohttp.ClientTimeout(total=seconds)


async def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """请求 URL 并解析 JSON 响应。

    Args:
        url: 目标地址。
        timeout: 超时秒数。

    Returns:
        解析后的 JSON 对象。

    Raises:
        ServerError: 网络异常、HTTP 非 2xx，或响应不是合法 JSON。
    """
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(url, timeout=_timeout(timeout)) as response:
                if response.status != 200:
                    raise ServerError(f"请求返回异常状态码 {response.status}", url=url)
                return await response.json(content_type=None)
    except ServerError:
        raise
    except aiohttp.ClientError as exc:
        raise ServerError("网络请求失败", url=url, reason=str(exc)) from exc
    except (TimeoutError, ValueError) as exc:
        raise ServerError("响应解析失败或超时", url=url, reason=str(exc)) from exc


async def ping_server(endpoint: str, timeout: int = DEFAULT_TIMEOUT) -> float:
    """测量到指定端点的往返延迟。

    Args:
        endpoint: 目标地址。
        timeout: 超时秒数。

    Returns:
        往返耗时（毫秒）。

    Raises:
        ServerError: 连接失败。
    """
    start = perf_counter()
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(endpoint, timeout=_timeout(timeout)) as response:
                await response.read()
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise ServerError("服务器连接失败", url=endpoint, reason=str(exc)) from exc
    return (perf_counter() - start) * 1000


async def check_server_status(
    endpoint: str, timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """查询渠道服 ``/status`` 接口。

    Args:
        endpoint: 渠道服基础地址。
        timeout: 超时秒数。

    Returns:
        状态字典。

    Raises:
        ServerError: 请求失败或返回非字典结构。
    """
    data = await fetch_json(f"{endpoint.rstrip('/')}/status", timeout=timeout)
    if not isinstance(data, dict):
        raise ServerError("状态接口返回的不是对象结构", url=endpoint)
    return data


async def detect_game_version(endpoint: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """查询渠道服 ``/version`` 接口。

    Args:
        endpoint: 渠道服基础地址。
        timeout: 超时秒数。

    Returns:
        版本号字符串；缺失时返回 ``"unknown"``。

    Raises:
        ServerError: 请求失败。
    """
    data = await fetch_json(f"{endpoint.rstrip('/')}/version", timeout=timeout)
    if isinstance(data, dict):
        return str(data.get("version", "unknown"))
    return "unknown"


async def detect_server_region(endpoint: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """查询渠道服 ``/region`` 接口。

    Args:
        endpoint: 渠道服基础地址。
        timeout: 超时秒数。

    Returns:
        地区代码；缺失时返回 ``"unknown"``。

    Raises:
        ServerError: 请求失败。
    """
    data = await fetch_json(f"{endpoint.rstrip('/')}/region", timeout=timeout)
    if isinstance(data, dict):
        return str(data.get("region", "unknown"))
    return "unknown"


__all__ = [
    "DEFAULT_TIMEOUT",
    "USER_AGENT",
    "check_server_status",
    "detect_game_version",
    "detect_server_region",
    "fetch_json",
    "ping_server",
]
