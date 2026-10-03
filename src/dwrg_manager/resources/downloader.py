"""
资源下载器

使用 ``aiohttp`` 流式下载并写入 ``.part`` 临时文件，成功后通过 ``os.replace``
原子替换为目标文件；支持 ``asyncio.Semaphore`` 并发上限、有限次指数退避重试
以及基于 HTTP ``Range`` 的断点续传（服务器不支持 Range 时回退整文件重下）。

为避免阻塞事件循环，所有磁盘写入与哈希计算都通过 ``asyncio.to_thread`` 执行。
测试可通过 ``session_factory`` 注入假的 aiohttp 会话，从而完全不触碰真实网络。
"""

import asyncio
import os
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

import aiohttp

from ..utils.logger import get_logger
from .models import DownloadResult, DownloadTask, ProgressCallback
from .validator import Validator

logger = get_logger(__name__)

#: 会话工厂签名：返回一个可 ``async with`` 的会话对象。
SessionFactory = Callable[[], AbstractAsyncContextManager[Any]]


class DownloadError(Exception):
    """下载过程中的可重试错误。"""

    def __init__(self, message: str) -> None:
        """初始化下载错误。

        Args:
            message: 错误描述。
        """
        super().__init__(message)
        self.message = message


class Downloader:
    """并发下载器，支持退避重试与断点续传。

    Attributes:
        concurrency: 最大并发下载数。
        timeout: 单次请求总超时（秒）。
        retries: 单个文件的最大尝试次数。
        chunk_size: 流式读写块大小（字节）。
    """

    def __init__(
        self,
        *,
        concurrency: int = 5,
        timeout: int = 300,
        retries: int = 3,
        chunk_size: int = 1 << 16,
        retry_backoff: float = 0.5,
        session_factory: SessionFactory | None = None,
    ) -> None:
        """初始化下载器。

        Args:
            concurrency: 最大并发下载数，必须 >= 1。
            timeout: 单次请求总超时（秒）。
            retries: 单个文件的最大尝试次数，必须 >= 1。
            chunk_size: 流式读写块大小（字节）。
            retry_backoff: 指数退避基数（秒），第 n 次重试等待
                ``retry_backoff * 2 ** (n - 1)`` 秒。
            session_factory: 可选的会话工厂，用于注入测试替身；默认创建
                ``aiohttp.ClientSession``。

        Raises:
            ValueError: ``concurrency`` 或 ``retries`` 小于 1。
        """
        if concurrency < 1:
            raise ValueError("concurrency 必须 >= 1")
        if retries < 1:
            raise ValueError("retries 必须 >= 1")
        self.concurrency = concurrency
        self.timeout = timeout
        self.retries = retries
        self.chunk_size = chunk_size
        self.retry_backoff = retry_backoff
        self._session_factory = session_factory
        self._semaphore = asyncio.Semaphore(concurrency)
        self._validator = Validator()

    def _open_session(self) -> AbstractAsyncContextManager[Any]:
        """打开一个会话上下文。

        Returns:
            可 ``async with`` 的会话对象。
        """
        if self._session_factory is not None:
            return self._session_factory()
        session: AbstractAsyncContextManager[Any] = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return session

    async def download(
        self,
        url: str,
        dest: Path,
        *,
        expected_size: int | None = None,
        expected_md5: str | None = None,
        resume: bool = True,
    ) -> DownloadResult:
        """下载单个文件。

        Args:
            url: 文件下载地址。
            dest: 最终落盘路径（父目录会自动创建）。
            expected_size: 期望文件大小，用于下载后校验。
            expected_md5: 期望 MD5，用于下载后校验。
            resume: 是否允许基于 ``.part`` 文件断点续传。

        Returns:
            下载结果；失败时不抛异常，``success`` 为 ``False`` 且 ``error`` 有值。

        Example:
            >>> await downloader.download(url, Path("a.bin"), expected_size=3)
            DownloadResult(...)
        """
        async with self._semaphore:
            async with self._open_session() as session:
                return await self._download(
                    session,
                    url,
                    Path(dest),
                    expected_size=expected_size,
                    expected_md5=expected_md5,
                    resume=resume,
                    name=Path(dest).name,
                )

    async def download_many(
        self,
        tasks: Sequence[DownloadTask],
        *,
        on_progress: ProgressCallback | None = None,
    ) -> list[DownloadResult]:
        """并发下载多个文件，受 ``concurrency`` 限制。

        Args:
            tasks: 下载任务序列。
            on_progress: 每完成一个文件回调一次（可用于进度展示）。

        Returns:
            与 ``tasks`` 顺序一致的下载结果列表；空任务返回空列表。
        """
        if not tasks:
            return []
        async with self._open_session() as session:

            async def run(task: DownloadTask) -> DownloadResult:
                async with self._semaphore:
                    result = await self._download(
                        session,
                        task.url,
                        task.dest,
                        expected_size=task.expected_size,
                        expected_md5=task.expected_md5,
                        resume=task.resume,
                        name=task.name or task.dest.name,
                    )
                if on_progress is not None:
                    on_progress(result)
                return result

            results = await asyncio.gather(*(run(task) for task in tasks))
        return list(results)

    async def _download(
        self,
        session: Any,
        url: str,
        dest: Path,
        *,
        expected_size: int | None,
        expected_md5: str | None,
        resume: bool,
        name: str,
    ) -> DownloadResult:
        """执行带重试的下载流程。"""
        try:
            await asyncio.to_thread(dest.parent.mkdir, parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("创建目录失败: %s (%s)", dest.parent, exc)
            return DownloadResult(
                url=url,
                dest=dest,
                success=False,
                bytes_written=0,
                attempts=0,
                resumed=False,
                error=f"创建目录失败: {exc}",
            )

        part = dest.with_name(dest.name + ".part")
        last_error: str | None = None
        for attempt in range(1, self.retries + 1):
            try:
                written, resumed = await self._attempt(
                    session,
                    url,
                    dest,
                    part,
                    expected_size=expected_size,
                    expected_md5=expected_md5,
                    resume=resume,
                )
            except DownloadError as exc:
                last_error = exc.message
                logger.warning(
                    "下载失败(第 %d/%d 次): %s - %s",
                    attempt,
                    self.retries,
                    name,
                    exc.message,
                )
                if attempt < self.retries:
                    await asyncio.sleep(self.retry_backoff * (2 ** (attempt - 1)))
                continue
            return DownloadResult(
                url=url,
                dest=dest,
                success=True,
                bytes_written=written,
                attempts=attempt,
                resumed=resumed,
                error=None,
            )
        return DownloadResult(
            url=url,
            dest=dest,
            success=False,
            bytes_written=0,
            attempts=self.retries,
            resumed=False,
            error=last_error or "下载失败",
        )

    async def _attempt(
        self,
        session: Any,
        url: str,
        dest: Path,
        part: Path,
        *,
        expected_size: int | None,
        expected_md5: str | None,
        resume: bool,
    ) -> tuple[int, bool]:
        """单次下载尝试。

        Args:
            session: aiohttp 会话（或其测试替身）。
            url: 下载地址。
            dest: 最终目标路径。
            part: ``.part`` 临时文件路径。
            expected_size: 期望大小。
            expected_md5: 期望 MD5。
            resume: 是否允许断点续传。

        Returns:
            ``(总字节数, 是否使用了断点续传)``。

        Raises:
            DownloadError: 本次尝试失败（调用方决定是否重试）。
        """
        resume_from = 0
        if resume and part.exists():
            resume_from = part.stat().st_size
        headers: dict[str, str] = {}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        async with session.get(url, headers=headers) as response:
            status = int(response.status)
            if status == 416:
                await asyncio.to_thread(part.unlink, True)
                raise DownloadError("服务器拒绝 Range 请求(416)")
            if status == 206 and resume_from > 0:
                mode, used_resume = "ab", True
            elif status == 200:
                mode, used_resume = "wb", False
                resume_from = 0
            else:
                raise DownloadError(f"HTTP 状态码 {status}")
            written = await self._write_stream(response, part, mode)

        total = resume_from + written
        if expected_size is not None and total != expected_size:
            # 保留 .part 以便下次尝试继续续传，不删除。
            raise DownloadError(f"大小校验失败: {total} != {expected_size}")
        if expected_md5:
            actual = await asyncio.to_thread(self._validator.hash_file, part, "md5")
            if actual != expected_md5:
                await asyncio.to_thread(part.unlink, True)
                raise DownloadError("MD5 校验失败")
        await asyncio.to_thread(os.replace, part, dest)
        return total, used_resume

    async def _write_stream(self, response: Any, part: Path, mode: str) -> int:
        """把响应体流式写入 ``.part`` 文件，写入操作在子线程执行。

        Args:
            response: 已进入上下文的响应对象。
            part: 目标临时文件。
            mode: ``"wb"``（整文件重写）或 ``"ab"``（续传追加）。

        Returns:
            本次实际写入的字节数。
        """
        written = 0
        handle = await asyncio.to_thread(open, part, mode)
        try:
            async for chunk in response.content.iter_chunked(self.chunk_size):
                if not chunk:
                    continue
                await asyncio.to_thread(handle.write, chunk)
                written += len(chunk)
            await asyncio.to_thread(handle.flush)
        finally:
            await asyncio.to_thread(handle.close)
        return written
