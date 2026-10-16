"""
网络工具

提供渠道服探测所需的最小异步 HTTP 能力。统一使用
:class:`aiohttp.ClientTimeout` 构造超时对象（``aiohttp>=3.11`` 起不再接受
裸数字作为 ``timeout`` 参数），并把底层异常包装为
:class:`~dwrg_manager.exceptions.ServerError`。
"""

import urllib.error
import urllib.request
from time import perf_counter
from typing import Any

import aiohttp

from ..exceptions import ServerError

#: 默认请求超时（秒）
DEFAULT_TIMEOUT = 10

#: 默认 User-Agent
USER_AGENT = "dwrg-cli-manager/1.0.0"

#: 资源源可达性探测（HEAD）的默认超时（秒）
PROBE_TIMEOUT = 5


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


def probe_url(url: str, timeout: int = PROBE_TIMEOUT) -> dict[str, Any]:
    """用 HEAD 请求探测一个资源地址的可达性。

    这是一个**同步**函数：资源源探测通常由诊断类命令在主线程里逐个调用，
    不值得为此引入事件循环；同时它也只依赖标准库 ``urllib``，避免额外拉起
    aiohttp 会话。

    任何失败（DNS、连接、超时、非 2xx/3xx 状态码）都会以
    ``reachable=False`` 的结果返回，而不抛出异常，保证诊断命令在离线环境下
    依然可以正常结束。

    Args:
        url: 待探测的完整地址。
        timeout: 超时秒数。

    Returns:
        含 ``reachable`` / ``status_code`` / ``elapsed_ms`` / ``error`` 的字典。

    Example:
        >>> probe_url("https://example.com")["reachable"]  # doctest: +SKIP
        True
    """
    request = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": USER_AGENT}
    )
    start = perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or response.getcode() or 0)
            elapsed = (perf_counter() - start) * 1000
            reachable = 200 <= status < 400
            return {
                "reachable": reachable,
                "status_code": status,
                "elapsed_ms": round(elapsed, 1),
                "error": None if reachable else f"意外的状态码 {status}",
            }
    except urllib.error.HTTPError as exc:
        return {
            "reachable": False,
            "status_code": int(exc.code),
            "elapsed_ms": round((perf_counter() - start) * 1000, 1),
            "error": f"HTTP {exc.code}",
        }
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {
            "reachable": False,
            "status_code": None,
            "elapsed_ms": round((perf_counter() - start) * 1000, 1),
            "error": str(getattr(exc, "reason", exc)),
        }


__all__ = [
    "DEFAULT_TIMEOUT",
    "PROBE_TIMEOUT",
    "USER_AGENT",
    "check_server_status",
    "detect_game_version",
    "detect_server_region",
    "fetch_json",
    "ping_server",
    "probe_url",
]
