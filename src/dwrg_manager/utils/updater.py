"""
自更新检查

查询 PyPI 上 ``dwrg-cli-manager`` 的最新版本，并与当前安装版本比较。

设计约束：

* **静默失败**：任何网络异常、JSON 解析失败、字段缺失都统一返回 ``None``。
  自更新检查绝不能因为「没有网」而让 CLI 崩溃——它只是锦上添花的提示。
* **有界等待**：查询跑在后台线程里并带 3 秒超时，调用方通过
  :meth:`UpdateChecker.wait` 领取结果；即使线程卡住，主线程最多也只阻塞
  到超时为止。
* **可测试**：网络出口只有 ``urllib.request.urlopen`` 一处，测试用
  ``monkeypatch`` 替换它即可完全隔离真实网络。
"""

import json
import threading
import urllib.request
from dataclasses import dataclass
from typing import Any

from .logger import get_logger
from .version import get_version

logger = get_logger(__name__)

#: PyPI JSON API 地址
PYPI_JSON_URL = "https://pypi.org/pypi/dwrg-cli-manager/json"

#: 查询超时（秒）
REQUEST_TIMEOUT = 3

#: 后台线程最长等待时间（秒）
WAIT_TIMEOUT = REQUEST_TIMEOUT + 2

#: 建议使用的升级命令
UPGRADE_COMMANDS: tuple[str, ...] = (
    "uv tool install -U dwrg-cli-manager",
    "pipx upgrade dwrg-cli-manager",
    "pip install -U dwrg-cli-manager",
)

#: 状态：已是最新
STATUS_UP_TO_DATE = "up-to-date"

#: 状态：有新版本
STATUS_OUTDATED = "outdated"

#: 状态：无法确认（离线、请求失败等）
STATUS_UNKNOWN = "unknown"


@dataclass(frozen=True)
class VersionInfo:
    """一次版本检查的结果。

    Attributes:
        current: 本地版本号。
        latest: PyPI 上的最新版本号；查询失败时为 ``None``。
        status: 取值见 :data:`STATUS_UP_TO_DATE` / :data:`STATUS_OUTDATED`
            / :data:`STATUS_UNKNOWN`。
        is_prerelease: 最新版本是否为预发布版本（含 ``a`` / ``b`` / ``rc``）。
    """

    current: str
    latest: str | None
    status: str
    is_prerelease: bool = False

    @property
    def has_update(self) -> bool:
        """是否存在可用的新版本。

        Returns:
            有新版本且不是预发布时返回 ``True``。
        """
        return self.status == STATUS_OUTDATED and not self.is_prerelease


def _normalize(version: str) -> tuple[int, ...]:
    """把版本号解析为可比较的整数元组。

    仅取 ``主.次.修订`` 三段中的数字部分，其余（预发布标记、构建号等）忽略，
    因此 ``1.2.3rc1`` 与 ``1.2.3`` 视为相等——是否属于预发布由调用方
    单独判断。

    Args:
        version: 版本号字符串。

    Returns:
        长度 3 的整数元组；解析失败时返回 ``(0, 0, 0)``。
    """
    parts: list[int] = []
    for chunk in str(version).strip().lstrip("vV").split("."):
        digits = ""
        for char in chunk:
            if char.isdigit():
                digits += char
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _is_prerelease(version: str) -> bool:
    """判断版本号是否为预发布版本。

    Args:
        version: 版本号字符串。

    Returns:
        含 ``a`` / ``b`` / ``rc`` / ``dev`` / ``pre`` 等标记时返回
        ``True``。
    """
    lowered = str(version).lower()
    return any(marker in lowered for marker in ("a", "b", "rc", "dev", "pre"))


def _fetch_latest_version(url: str = PYPI_JSON_URL) -> str | None:
    """从 PyPI JSON 接口读取最新版本号。

    Args:
        url: PyPI JSON 接口地址。

    Returns:
        最新版本号；任何失败都返回 ``None`` 而不抛异常。
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload: Any = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - 自更新检查必须静默降级
        logger.debug("查询 PyPI 最新版本失败: %s", exc)
        return None

    if not isinstance(payload, dict):
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    version = info.get("version")
    return str(version) if isinstance(version, str) and version.strip() else None


class UpdateChecker:
    """版本检查器。

    查询在后台线程中执行，因此调用方（通常是 CLI 启动路径）不会因为网络慢
    而被阻塞超过 :data:`WAIT_TIMEOUT`` 秒。

    Args:
        current: 当前版本号；为 ``None`` 时读取包内版本。
        url: PyPI JSON 接口地址，便于测试指向假地址。

    Example:
        >>> checker = UpdateChecker(current="1.0.0")
        >>> checker.check().status in {"up-to-date", "outdated", "unknown"}
        True
    """

    def __init__(self, current: str | None = None, url: str = PYPI_JSON_URL) -> None:
        self.current = current or get_version()
        self.url = url
        self._thread: threading.Thread | None = None
        self._result: VersionInfo | None = None

    def start(self) -> threading.Thread:
        """在后台线程中发起查询。

        Returns:
            已启动的线程对象；重复调用会返回同一个线程。
        """

        if self._thread is not None:
            return self._thread
        self._thread = threading.Thread(
            target=self._run, name="dwrg-update-check", daemon=False
        )
        self._thread.start()
        return self._thread

    def _run(self) -> None:
        """线程入口：执行查询并缓存结果。"""
        self._result = self.check()

    def check(self) -> VersionInfo:
        """同步执行一次版本检查。

        Returns:
            :class:`VersionInfo`；查询失败时 ``status`` 为
            :data:`STATUS_UNKNOWN` 且 ``latest`` 为 ``None``。
        """
        latest = _fetch_latest_version(self.url)
        if latest is None:
            return VersionInfo(current=self.current, latest=None, status=STATUS_UNKNOWN)
        status = (
            STATUS_OUTDATED
            if _normalize(latest) > _normalize(self.current)
            else STATUS_UP_TO_DATE
        )
        return VersionInfo(
            current=self.current,
            latest=latest,
            status=status,
            is_prerelease=_is_prerelease(latest),
        )

    def wait(self) -> VersionInfo:
        """等待后台查询结束并返回结果。

        Returns:
            检查结果；查询尚未启动时先 :meth:`start`` 再等待。

        Note:
            即使线程因网络问题挂起，最多也只阻塞 :data:`WAIT_TIMEOUT`` 秒，
            随后返回 :data:`STATUS_UNKNOWN`，保证 CLI 永远可退出。
        """
        thread = self.start()
        thread.join(timeout=WAIT_TIMEOUT)
        if self._result is not None:
            return self._result
        logger.debug("版本查询超时，按未知处理")
        return VersionInfo(current=self.current, latest=None, status=STATUS_UNKNOWN)


def check_latest_version(
    current: str | None = None, url: str = PYPI_JSON_URL
) -> VersionInfo:
    """查询最新版本并与当前版本比较（后台线程 + 静默降级）。

    Args:
        current: 当前版本号；``None`` 时读取包内版本。
        url: PyPI JSON 接口地址。

    Returns:
        :class:`VersionInfo`。无网络或请求失败时 ``status`` 为
        :data:`STATUS_UNKNOWN``。

    Example:
        >>> check_latest_version(current="1.0.0").status
        'unknown'
    """

    checker = UpdateChecker(current=current, url=url)
    return checker.wait()


def check_latest_version_async(
    current: str | None = None, url: str = PYPI_JSON_URL
) -> UpdateChecker:
    """发起一次非阻塞的版本检查。

    适用于「不希望等待网络」的场景：调用方先做别的事，稍后再用
    :meth:`UpdateChecker.wait` 领取结果。

    Args:
        current: 当前版本号；``None`` 时读取包内版本。
        url: PyPI JSON 接口地址。

    Returns:
        已启动查询的 :class:`UpdateChecker`。
    """
    checker = UpdateChecker(current=current, url=url)
    checker.start()
    return checker


def build_upgrade_hint() -> list[str]:
    """构造可执行的升级命令提示列表。

    Returns:
        形如 ``uv tool install -U dwrg-cli-manager`` 的命令字符串列表。
    """
    return list(UPGRADE_COMMANDS)


__all__ = [
    "PYPI_JSON_URL",
    "REQUEST_TIMEOUT",
    "STATUS_OUTDATED",
    "STATUS_UNKNOWN",
    "STATUS_UP_TO_DATE",
    "UPGRADE_COMMANDS",
    "UpdateChecker",
    "VersionInfo",
    "build_upgrade_hint",
    "check_latest_version",
    "check_latest_version_async",
]
