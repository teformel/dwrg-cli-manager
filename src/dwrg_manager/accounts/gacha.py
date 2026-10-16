"""
抽卡记录导出

对标参考项目 ``wutheringwaves-cli-manager`` 的 ``ww log``：扫描游戏客户端
留下的日志目录，从日志文本中提取抽卡记录页 URL，供玩家在浏览器中查看。

平台分支：

* Windows：``%LOCALAPPDATA%\\IdentityV``（或用户通过 ``--dir`` 指定）；
* Linux / macOS：``~/.IdentityV``。

日志被客户端加密时不会抛异常，而是返回带 ``encrypted`` 标记的结果，
由 CLI 打印明确提示。
"""

import os
import platform
import re
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 日志文件名后缀（只读取日志，避免误读二进制资源）
LOG_SUFFIXES: tuple[str, ...] = (".log", ".txt", ".json")

#: 单个日志文件的最大读取体积（8 MiB），防止异常大的文件拖慢扫描
MAX_LOG_BYTES: int = 8 * 1024 * 1024

#: 抽卡记录 URL 特征：路径含 ``gacha`` 或 ``record`` 关键词
_GACHA_URL_RE = re.compile(
    r"https?://[^\s\"'<>\]\)]+?(?:gacha|record|draw)[^\s\"'<>\]\)]*",
    re.IGNORECASE,
)

#: 日志被加密的典型特征：Fernet 密文片段或客户端加密标记
_ENCRYPTED_HINT_RE = re.compile(
    r"(?:\bencrypted\b|\bcipher\b|gAAAAA[A-Za-z0-9_\-]{16,})", re.IGNORECASE
)

__all__ = [
    "GachaScanResult",
    "default_log_dirs",
    "extract_gacha_urls",
    "open_url",
    "scan_gacha_logs",
]


@dataclass
class GachaScanResult:
    """一次抽卡记录扫描的结果。

    Attributes:
        log_dir: 实际扫描的日志目录；未找到时为 ``None``。
        urls: 去重后按出现顺序排列的抽卡记录 URL 列表。
        scanned_files: 实际读取的日志文件数。
        encrypted: 是否检测到加密日志（此时 ``urls`` 通常为空）。
        message: 面向用户的补充说明。
    """

    log_dir: Path | None = None
    urls: list[str] = field(default_factory=list)
    scanned_files: int = 0
    encrypted: bool = False
    message: str = ""

    @property
    def found(self) -> bool:
        """是否至少找到一条抽卡记录链接。

        Returns:
            ``urls`` 非空时为 ``True``。
        """
        return bool(self.urls)


def default_log_dirs(game_dir: str | Path | None = None) -> list[Path]:
    """返回按平台分支推导的候选日志目录。

    Args:
        game_dir: 用户显式指定的游戏目录；提供时只返回该目录。

    Returns:
        候选目录列表（按优先级排列）。
    """
    if game_dir:
        return [Path(game_dir).expanduser()]

    home = Path.home()
    system = platform.system()
    candidates: list[Path] = []
    if system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "IdentityV")
        candidates.append(home / "AppData" / "Local" / "IdentityV")
    elif system == "Darwin":
        candidates.append(home / "Library" / "Application Support" / "IdentityV")
    candidates.append(home / ".IdentityV")
    return candidates


def _iter_log_files(directory: Path) -> list[Path]:
    """列出目录下待扫描的日志文件。

    只保留 :data:`LOG_SUFFIXES` 中的后缀，且体积不超过
    :data:`MAX_LOG_BYTES`，按文件名排序以保证结果稳定。

    Args:
        directory: 待遍历的目录。

    Returns:
        日志文件路径列表。
    """
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in LOG_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_LOG_BYTES:
                logger.debug("跳过大日志文件: %s", path)
                continue
        except OSError:  # pragma: no cover - 依赖文件系统
            continue
        files.append(path)
    return files


def _looks_encrypted(text: str) -> bool:
    """判断日志文本是否为客户端加密后的内容。

    Args:
        text: 日志文件内容。

    Returns:
        命中加密特征时返回 ``True``。
    """
    return bool(_ENCRYPTED_HINT_RE.search(text))


def extract_gacha_urls(text: str) -> list[str]:
    """从日志文本中提取抽卡记录 URL。

    Args:
        text: 日志内容。

    Returns:
        去重且保持出现顺序的 URL 列表。
    """
    seen: dict[str, None] = {}
    for match in _GACHA_URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:\"'")
        if url and url not in seen:
            seen[url] = None
    return list(seen)


def scan_gacha_logs(game_dir: str | Path | None = None) -> GachaScanResult:
    """扫描游戏日志目录并提取抽卡记录链接。

    Args:
        game_dir: 用户显式指定的日志目录；为 ``None`` 时按平台分支探测
            :func:`default_log_dirs`。

    Returns:
        :class:`GachaScanResult`。目录不存在或日志加密时不会抛异常，
        而是通过 ``message`` / ``encrypted`` 表达。
    """
    result = GachaScanResult()
    for directory in default_log_dirs(game_dir):
        if not directory.exists() or not directory.is_dir():
            continue
        result.log_dir = directory
        break
    if result.log_dir is None:
        result.message = "未找到游戏日志目录，请用 --dir 指定"
        logger.debug("未找到日志目录，候选: %s", default_log_dirs(game_dir))
        return result

    urls: dict[str, None] = {}
    encrypted = False
    for path in _iter_log_files(result.log_dir):
        result.scanned_files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - 依赖文件系统
            logger.debug("读取日志失败 %s: %s", path, exc)
            continue
        if _looks_encrypted(text):
            encrypted = True
            logger.debug("检测到加密日志: %s", path)
            continue
        for url in extract_gacha_urls(text):
            urls.setdefault(url, None)

    result.urls = list(urls)
    result.encrypted = encrypted
    if encrypted:
        result.message = "日志已被客户端加密，无法提取抽卡记录链接"
    elif not result.urls:
        result.message = "未在日志中找到抽卡记录链接"
    else:
        result.message = f"找到 {len(result.urls)} 条抽卡记录链接"
    logger.info("%s（扫描 %d 个文件）", result.message, result.scanned_files)
    return result


def open_url(url: str) -> bool:
    """在默认浏览器中打开链接。

    Args:
        url: 待打开的链接。

    Returns:
        是否成功交给浏览器；无可用浏览器或调用失败时返回 ``False``。
    """
    try:
        return bool(webbrowser.open(url))
    except Exception as exc:  # pragma: no cover - 依平台而定
        logger.warning("打开浏览器失败: %s", exc)
        return False
