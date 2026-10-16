"""
资源索引传输层

提供两种 :class:`~dwrg_manager.resources.models.ManifestTransport` 实现，
用于在「没有官方 manifest 文件」的前提下构造真实可用的资源清单：

* :class:`HttpIndexTransport`：对配置的安装包直链发 ``HEAD`` 请求，读取
  ``Content-Length`` / ``ETag`` / ``Last-Modified``，就地构造**单文件**
  :class:`~dwrg_manager.resources.models.ResourceManifest`。
  实测结论（见 ``memory/resource-source-research.md``）：网易 CDN 的 ``ETag``
  在「32 位十六进制且无 ``-N`` 后缀」时就是整文件 MD5，可直接用于完整性
  校验；带 ``-N`` 后缀说明对象是分片上传的，此时只能回落大小校验。
* :class:`LocalIndexTransport`：扫描本地游戏目录生成清单（含子目录），
  大小与 MD5 由 :class:`~dwrg_manager.resources.validator.Validator` 计算，
  可选把清单以「临时文件 + ``os.replace``」的原子方式写盘。

两种实现的共同约定：**网络 / 文件系统异常一律降级**，记录日志后返回
``None`` 或跳过该文件，绝不向上抛异常——资源域的失败必须表现为
「检查结果全 0 / 更新失败」，而不是让 CLI 崩溃。
"""

import json
import os
import re
import tempfile
from collections.abc import Callable, Iterable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import aiohttp

from ..config.models import ResourceSourceConfig, default_resource_sources
from ..utils.logger import get_logger
from .models import ResourceFile, ResourceManifest, ResourceServer
from .validator import Validator

logger = get_logger(__name__)

#: 整文件 MD5 形式的 ETag：32 位十六进制、无 ``-N`` 分片后缀。
_MD5_ETAG_PATTERN: re.Pattern[str] = re.compile(r'^"?[0-9a-fA-F]{32}"?$')

#: 扫描本地目录时默认忽略的文件名（临时文件与自身清单）。
DEFAULT_IGNORED_NAMES: tuple[str, ...] = (
    "manifest.json",
    ".DS_Store",
    "Thumbs.db",
)

#: 扫描本地目录时默认忽略的后缀（临时文件）。
DEFAULT_IGNORED_SUFFIXES: tuple[str, ...] = (".part", ".tmp")

#: HTTP 索引请求的默认超时（秒）。
DEFAULT_HTTP_TIMEOUT = 30

#: 会话工厂签名：返回一个可 ``async with`` 的会话对象（供测试注入替身）。
SessionFactory = Callable[[], AbstractAsyncContextManager[Any]]


def is_full_md5_etag(etag: str) -> bool:
    """判断 ``ETag`` 是否等价于整文件 MD5。

    网易 CDN 的 ``ETag`` 有两种形态：普通对象是整文件 MD5（32 位十六进制、
    无后缀），分片上传的对象则带 ``-N`` 后缀（例如
    ``"07814da3f6ce70ed2552697bda7ab6c8-7"``），后者**不是**整文件 MD5。

    Args:
        etag: 响应头中的 ``ETag`` 原值，可带或不带首尾双引号。

    Returns:
        当且仅当 ``etag`` 是 32 位十六进制且无 ``-N`` 后缀时返回 ``True``。

    Example:
        >>> is_full_md5_etag('"3af58ef90a035b275797507c1efecd05"')
        True
        >>> is_full_md5_etag('"07814da3f6ce70ed2552697bda7ab6c8-7"')
        False
    """
    return bool(_MD5_ETAG_PATTERN.match(etag.strip()))


def normalize_etag(etag: str) -> str:
    """去掉 ``ETag`` 的首尾双引号与空白。

    Args:
        etag: 响应头中的 ``ETag`` 原值。

    Returns:
        去除引号后的 ``ETag`` 字符串；输入为空时返回空串。
    """
    return etag.strip().strip('"')


def url_basename(url: str) -> str:
    """从 URL 中取出文件基名（去除查询串并做百分号解码）。

    Args:
        url: 目标 URL。

    Returns:
        路径最后一段；URL 以 ``/`` 结尾或没有路径时返回 ``"download"``。

    Example:
        >>> url_basename("https://host/dir/setup.exe?sig=abc")
        'setup.exe'
    """
    path = urlsplit(url).path
    name = unquote(path.rstrip("/").rsplit("/", 1)[-1]) if path else ""
    return name or "download"


class HttpIndexTransport:
    """基于 ``HEAD`` 请求构造单文件清单的传输层。

    每个配置的资源源对应清单中的一个 :class:`ResourceFile`；``md5`` 仅在
    ``ETag`` 确为整文件 MD5 时填写，否则留空（由
    :meth:`~dwrg_manager.resources.validator.Validator.verify` 回落到大小校验）。
    """

    def __init__(
        self,
        sources: Iterable[ResourceSourceConfig] | None = None,
        *,
        timeout: int = DEFAULT_HTTP_TIMEOUT,
        validator: Validator | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        """初始化 HTTP 索引传输层。

        Args:
            sources: 资源源列表；缺省时使用 :func:`default_resource_sources`
                提供的两条已实测国际服直链。
            timeout: 单次 ``HEAD`` 请求的总超时（秒）。
            validator: 校验器实例（当前实现未直接使用，保留以便复用与测试注入）。
            session_factory: 可选的会话工厂，用于注入测试替身；签名与
                :class:`~dwrg_manager.resources.downloader.Downloader` 一致。
        """
        if sources is None:
            sources = default_resource_sources()
        self._sources = [source for source in sources if source.is_available]
        self._timeout = timeout
        self._validator = validator or Validator()
        self._session_factory = session_factory

    @property
    def sources(self) -> list[ResourceSourceConfig]:
        """当前启用的资源源列表。

        Returns:
            已过滤 ``is_available=False`` 的资源源列表。
        """
        return list(self._sources)

    async def fetch_manifest(self, server: ResourceServer) -> ResourceManifest | None:
        """对所有启用的资源源做 ``HEAD`` 探测并构造清单。

        Args:
            server: 目标资源服务器；实现只用其名称作日志标识，真实地址来自
                配置的 ``resource_sources``。

        Returns:
            至少有一个源可用时返回 :class:`ResourceManifest`；
            全部源不可用（网络异常或响应异常）时返回 ``None``。
        """
        if not self._sources:
            logger.warning("没有可用的资源源（resource_sources 为空）")
            return None

        files: list[ResourceFile] = []
        versions: list[str] = []
        for source in self._sources:
            file_info = await self._probe(source, server_name=server.name)
            if file_info is None:
                continue
            files.append(file_info)
            versions.append(file_info.version)

        if not files:
            logger.error("所有资源源均不可用: %s", [s.name for s in self._sources])
            return None

        manifest = ResourceManifest(
            version="+".join(versions),
            files=files,
            total_size=sum(file_info.size for file_info in files),
            download_url=self._download_base(server),
        )
        logger.info(
            "HTTP 索引清单已生成: version=%s, 文件数=%d",
            manifest.version,
            len(files),
        )
        return manifest

    async def _probe(
        self, source: ResourceSourceConfig, *, server_name: str
    ) -> ResourceFile | None:
        """对单个资源源发 ``HEAD`` 请求并转换为 :class:`ResourceFile`。

        Args:
            source: 目标资源源。
            server_name: 服务器名称，仅用于日志。

        Returns:
            探测成功返回文件信息；任何网络异常或响应异常都返回 ``None``。
        """
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        try:
            async with self._open_session(timeout) as session:
                async with session.head(source.url) as response:
                    status = int(response.status)
                    if status != 200:
                        logger.error(
                            "资源源探测失败: HTTP %s (%s, server=%s)",
                            status,
                            source.url,
                            server_name,
                        )
                        return None
                    headers = {
                        key.lower(): value for key, value in response.headers.items()
                    }
        except Exception as exc:  # noqa: BLE001 - 网络边界，统一降级为 None
            logger.error("资源源探测异常: %s (%s)", exc, source.url)
            return None

        size = self._parse_int(headers.get("content-length"))
        if size is None:
            logger.error("资源源缺少 Content-Length，已跳过: %s", source.url)
            return None

        etag = normalize_etag(headers.get("etag", ""))
        last_modified = self._parse_http_date(headers.get("last-modified"))
        md5 = etag if is_full_md5_etag(etag) else ""
        if not md5:
            logger.info(
                "ETag 不是整文件 MD5（分片上传），回落为大小校验: %s (%s)",
                source.name,
                etag or "无 ETag",
            )
        version = self._derive_version(
            source=source, etag=etag, last_modified=last_modified
        )
        return ResourceFile(
            name=url_basename(source.url),
            path=url_basename(source.url),
            size=size,
            md5=md5,
            version=version,
            is_optional=False,
            last_modified=last_modified or datetime.now(),
        )

    def _open_session(
        self, timeout: aiohttp.ClientTimeout
    ) -> AbstractAsyncContextManager[Any]:
        """打开一个可 ``async with`` 的会话上下文。

        Args:
            timeout: 已构造的超时对象。

        Returns:
            会话对象；注入过 ``session_factory`` 时优先使用它。
        """
        if self._session_factory is not None:
            return self._session_factory()
        return aiohttp.ClientSession(timeout=timeout)

    @staticmethod
    def _parse_int(raw: str | None) -> int | None:
        """把响应头中的数字字符串解析为 ``int``。

        Args:
            raw: 原始响应头值。

        Returns:
            解析成功返回整数；缺失或非法时返回 ``None``。
        """
        if raw is None:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            logger.warning("无法解析响应头数字: %r", raw)
            return None

    @staticmethod
    def _parse_http_date(raw: str | None) -> datetime | None:
        """把 ``Last-Modified`` 解析为 ``datetime``。

        Args:
            raw: 原始响应头值（RFC 1123 格式）。

        Returns:
            解析成功返回**不带时区**的 :class:`datetime`；失败返回 ``None``。
        """
        if not raw:
            return None
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            logger.warning("无法解析 Last-Modified: %r", raw)
            return None
        if parsed.tzinfo is not None:
            return parsed.replace(tzinfo=None)
        return parsed

    @staticmethod
    def _derive_version(
        *, source: ResourceSourceConfig, etag: str, last_modified: datetime | None
    ) -> str:
        """从响应头派生该文件的版本号。

        优先级：``ETag``（整文件 MD5，最能反映内容变化）→ ``Last-Modified``
        时间戳 → 资源源名称。这样同一个源内容变化时版本号必然变化，
        从而让增量更新的「版本未变则短路」逻辑保持正确。

        Args:
            source: 目标资源源。
            etag: 已规范化的 ``ETag``。
            last_modified: 已解析的 ``Last-Modified``。

        Returns:
            版本号字符串。
        """
        if is_full_md5_etag(etag):
            return normalize_etag(etag)
        if last_modified is not None:
            return last_modified.strftime("%Y%m%d%H%M%S")
        return source.name

    @staticmethod
    def _download_base(server: ResourceServer) -> str:
        """推导清单的下载基础 URL。

        Args:
            server: 目标资源服务器。

        Returns:
            下载基础 URL；各类字段都为空时回落到 ``"local"``（本地索引场景）。
        """
        for candidate in (
            getattr(server, "download_url", ""),
            getattr(server, "endpoint", ""),
        ):
            if candidate:
                return str(candidate).rstrip("/")
        return "local"


class LocalIndexTransport:
    """扫描本地目录生成清单的传输层。

    适用于「国服无公开直链，只能管理本地已安装目录」的场景：把磁盘现状
    固化为一份清单，之后即可用同一套 ``check`` / ``update`` 流程做完整性
    校验与增量修复。
    """

    def __init__(
        self,
        directory: Path | str | None = None,
        *,
        manifest_path: Path | str | None = None,
        ignored_names: Iterable[str] = DEFAULT_IGNORED_NAMES,
        ignored_suffixes: Iterable[str] = DEFAULT_IGNORED_SUFFIXES,
        validator: Validator | None = None,
    ) -> None:
        """初始化本地索引传输层。

        Args:
            directory: 待扫描的游戏目录；``None`` 表示在调用
                :meth:`fetch_manifest` 时由 ``server`` 推导。
            manifest_path: 清单落盘路径；``None`` 表示只返回不落盘。
            ignored_names: 需要跳过的文件名集合。
            ignored_suffixes: 需要跳过的文件后缀集合。
            validator: 校验器实例，缺省自行创建（用于分块 MD5）。
        """
        self._directory = Path(directory) if directory is not None else None
        self._manifest_path = Path(manifest_path) if manifest_path is not None else None
        self._ignored_names = tuple(ignored_names)
        self._ignored_suffixes = tuple(ignored_suffixes)
        self._validator = validator or Validator()

    @property
    def directory(self) -> Path | None:
        """当前扫描目录。

        Returns:
            扫描目录路径；未设置时返回 ``None``。
        """
        return self._directory

    async def fetch_manifest(self, server: ResourceServer) -> ResourceManifest | None:
        """扫描目录并生成清单（可选写盘）。

        Args:
            server: 目标资源服务器；``directory`` 未在构造时指定时，用
                ``server.base_url`` 或 ``server.endpoint`` 作为目录。

        Returns:
            清单对象；目录不存在或没有任何文件时返回 ``None``。
        """
        directory = self._resolve_directory(server)
        if directory is None:
            logger.error("本地索引未指定扫描目录")
            return None
        if not directory.is_dir():
            logger.error("本地索引目录不存在: %s", directory)
            return None

        files: list[ResourceFile] = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or self._is_ignored(path):
                continue
            file_info = self._describe(path, directory)
            if file_info is None:
                continue
            files.append(file_info)

        if not files:
            logger.warning("本地索引未发现任何文件: %s", directory)
            return None

        manifest = ResourceManifest(
            version=datetime.now().strftime("%Y%m%d%H%M%S"),
            files=files,
            total_size=sum(file_info.size for file_info in files),
            download_url=str(directory),
        )
        logger.info(
            "本地索引清单已生成: %s (文件数=%d)", directory, len(manifest.files)
        )
        if self._manifest_path is not None:
            self.save_manifest(manifest, self._manifest_path)
        return manifest

    def _resolve_directory(self, server: ResourceServer) -> Path | None:
        """解析实际扫描目录。

        Args:
            server: 目标资源服务器，其 ``base_url`` / ``endpoint`` 在
                构造时未指定目录的情况下作为目录使用。

        Returns:
            目录路径；无法确定时返回 ``None``。
        """
        if self._directory is not None:
            return self._directory
        for candidate in (
            getattr(server, "base_url", ""),
            getattr(server, "endpoint", ""),
        ):
            if candidate:
                return Path(str(candidate)).expanduser()
        return None

    def _is_ignored(self, path: Path) -> bool:
        """判断文件是否应被跳过。

        Args:
            path: 候选文件路径。

        Returns:
            命中忽略名单（按文件名或后缀）时返回 ``True``。
        """
        if path.name in self._ignored_names:
            return True
        return path.suffix.lower() in self._ignored_suffixes

    def _describe(self, path: Path, root: Path) -> ResourceFile | None:
        """把单个文件转换为 :class:`ResourceFile`。

        Args:
            path: 文件绝对路径。
            root: 扫描根目录，用于计算相对路径。

        Returns:
            文件信息；读取大小或哈希失败时返回 ``None``（记日志后跳过）。
        """
        try:
            stat_result = path.stat()
            size = stat_result.st_size
            md5 = self._validator.hash_file(path, "md5")
            last_modified = datetime.fromtimestamp(stat_result.st_mtime)
        except OSError as exc:
            logger.warning("读取文件失败，已跳过: %s (%s)", path, exc)
            return None
        relative = path.relative_to(root).as_posix()
        return ResourceFile(
            name=path.name,
            path=relative,
            size=size,
            md5=md5,
            version=datetime.now().strftime("%Y%m%d%H%M%S"),
            is_optional=False,
            last_modified=last_modified,
        )

    @staticmethod
    def save_manifest(manifest: ResourceManifest, target: Path | str) -> bool:
        """以「临时文件 + ``os.replace``」原子写盘清单。

        Args:
            manifest: 待保存的清单。
            target: 目标路径（``.json``）。

        Returns:
            保存成功返回 ``True``，失败返回 ``False``。
        """
        path = Path(target)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = manifest.model_dump(mode="json")
            fd, tmp_name = tempfile.mkstemp(
                prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, path)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:  # pragma: no cover - 尽力而为
                    pass
                raise
        except OSError as exc:
            logger.error("保存本地索引清单失败: %s (%s)", path, exc)
            return False
        logger.info("已保存本地索引清单: %s", path)
        return True


__all__ = [
    "DEFAULT_HTTP_TIMEOUT",
    "DEFAULT_IGNORED_NAMES",
    "DEFAULT_IGNORED_SUFFIXES",
    "HttpIndexTransport",
    "LocalIndexTransport",
    "is_full_md5_etag",
    "normalize_etag",
    "url_basename",
]
