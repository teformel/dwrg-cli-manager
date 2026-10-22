"""
资源索引传输层单元测试

覆盖 :mod:`dwrg_manager.resources.transports` 的两条实现：

* :class:`~dwrg_manager.resources.transports.HttpIndexTransport`：用注入的假
  ``aiohttp`` 会话驱动 ``HEAD`` 探测，覆盖 MD5 ETag、分片 ETag、缺失 / 非法
  ``Content-Length``、非 200、异常降级与空资源源等分支。**不访问真实网络**。
* :class:`~dwrg_manager.resources.transports.LocalIndexTransport`：在
  ``tmp_path`` 上构造目录树，覆盖递归扫描、忽略名单、清单落盘、目录推导
  与读写失败降级。

另含 ``is_full_md5_etag`` / ``normalize_etag`` / ``url_basename`` 三个纯函数。
"""

import hashlib
import json
from pathlib import Path

import pytest

from dwrg_manager.config.models import ResourceSourceConfig
from dwrg_manager.resources.models import ResourceManifest, ResourceServer
from dwrg_manager.resources.transports import (
    HttpIndexTransport,
    LocalIndexTransport,
    is_full_md5_etag,
    normalize_etag,
    url_basename,
)
from dwrg_manager.resources.validator import Validator


# --------------------------------------------------------------------------- #
# 测试替身 / 构造工具
# --------------------------------------------------------------------------- #
class _FakeHeadResponse:
    """``aiohttp`` ``HEAD`` 响应的测试替身。"""

    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """初始化假响应。

        Args:
            status: HTTP 状态码。
            headers: 响应头；键会原样保留，被测代码负责转小写。
            error: 进入上下文时抛出的异常，用于模拟连接失败。
        """
        self.status = status
        self.headers: dict[str, str] = headers or {}
        self._error = error

    async def __aenter__(self) -> "_FakeHeadResponse":
        """进入上下文；若配置了异常则抛出。"""
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        """退出上下文，不吞异常。"""
        return False


class _FakeSession:
    """``aiohttp.ClientSession`` 的测试替身，只实现 ``head``。"""

    def __init__(self, response: _FakeHeadResponse) -> None:
        """保存要返回的响应。

        Args:
            response: 假响应对象。
        """
        self._response = response
        self.requested: list[str] = []

    async def __aenter__(self) -> "_FakeSession":
        """进入上下文。"""
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        """退出上下文。"""
        return False

    def head(self, url: str) -> _FakeHeadResponse:
        """记录请求 URL 并返回预置响应。

        Args:
            url: 请求地址。

        Returns:
            假响应对象。
        """
        self.requested.append(url)
        return self._response


def make_source(
    name: str = "oversea",
    url: str = "https://dl.example/dir/setup.exe?sig=1",
    *,
    available: bool = True,
) -> ResourceSourceConfig:
    """构造一个资源源配置。"""
    return ResourceSourceConfig(
        name=name,
        url=url,
        channel="oversea",
        description="测试源",
        is_available=available,
    )


def make_server(
    endpoint: str = "https://dl.example/root/",
    base_url: str = "https://dl.example/root",
) -> ResourceServer:
    """构造一个资源服务器模型。"""
    return ResourceServer(
        name="srv",
        endpoint=endpoint,
        base_url=base_url,
        current_version="",
        latest_version="",
    )


def make_http_transport(
    sources: list[ResourceSourceConfig],
    response: _FakeHeadResponse,
) -> tuple[HttpIndexTransport, _FakeSession]:
    """构造注入了假会话的 HTTP 传输层。"""
    session = _FakeSession(response)
    transport = HttpIndexTransport(
        sources=sources,
        session_factory=lambda: session,
    )
    return transport, session


# --------------------------------------------------------------------------- #
# 纯函数
# --------------------------------------------------------------------------- #
@pytest.mark.unit
class TestEtagAndUrlHelpers:
    """ETag 判定与 URL 基名解析。"""

    @pytest.mark.parametrize(
        ("etag", "expected"),
        [
            ('"3af58ef90a035b275797507c1efecd05"', True),
            ("3af58ef90a035b275797507c1efecd05", True),
            ('"07814da3f6ce70ed2552697bda7ab6c8-7"', False),
            ('W/"3af58ef90a035b275797507c1efecd05"', False),
            ("", False),
            ("not-a-hash", False),
        ],
    )
    def test_is_full_md5_etag(self, etag: str, expected: bool) -> None:
        """只有「32 位十六进制且无 -N 后缀」的 ETag 才算整文件 MD5。"""
        assert is_full_md5_etag(etag) is expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ('"abc"', "abc"),
            ('  "abc"  ', "abc"),
            ("abc", "abc"),
            ("", ""),
        ],
    )
    def test_normalize_etag(self, raw: str, expected: str) -> None:
        """规范化应去掉首尾空白与双引号。"""
        assert normalize_etag(raw) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://host/dir/setup.exe?sig=abc", "setup.exe"),
            ("https://host/dir/", "dir"),
            ("https://host/", "download"),
            ("https://host", "download"),
            ("https://host/%E4%B8%AD%E6%96%87.exe", "中文.exe"),
        ],
    )
    def test_url_basename(self, url: str, expected: str) -> None:
        """基名应去掉查询串、做百分号解码，空路径回退为 download。"""
        assert url_basename(url) == expected


# --------------------------------------------------------------------------- #
# HttpIndexTransport
# --------------------------------------------------------------------------- #
@pytest.mark.unit
class TestHttpIndexTransport:
    """``HEAD`` 探测构造清单的行为。"""

    async def test_builds_manifest_with_md5_etag(self) -> None:
        """整文件 MD5 的 ETag 应直接写入 ``md5`` 与版本号。"""
        md5 = "3af58ef90a035b275797507c1efecd05"
        transport, session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(
                headers={
                    "Content-Length": "1234",
                    "ETag": f'"{md5}"',
                    "Last-Modified": "Wed, 21 Oct 2026 07:28:00 GMT",
                }
            ),
        )

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        assert manifest.version == md5
        assert manifest.total_size == 1234
        assert manifest.download_url == "https://dl.example/root"
        assert session.requested == ["https://dl.example/dir/setup.exe?sig=1"]
        assert len(manifest.files) == 1
        file_info = manifest.files[0]
        assert file_info.name == "setup.exe"
        assert file_info.path == "setup.exe"
        assert file_info.size == 1234
        assert file_info.md5 == md5
        assert file_info.version == md5
        assert file_info.last_modified.year == 2026

    async def test_sharded_etag_falls_back_to_last_modified(self) -> None:
        """带 ``-N`` 的分片 ETag 不是整文件 MD5，版本回落为修改时间。"""
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(
                headers={
                    "Content-Length": "2048",
                    "ETag": '"07814da3f6ce70ed2552697bda7ab6c8-7"',
                    "Last-Modified": "Wed, 21 Oct 2026 07:28:00 GMT",
                }
            ),
        )

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        file_info = manifest.files[0]
        assert file_info.md5 == ""
        assert file_info.version == "20261021072800"

    async def test_without_metadata_uses_source_name(self) -> None:
        """既无 MD5 ETag 也无 ``Last-Modified`` 时以资源源名称作版本。"""
        transport, _session = make_http_transport(
            [make_source(name="fallback_src")],
            _FakeHeadResponse(headers={"Content-Length": "10"}),
        )

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        assert manifest.files[0].version == "fallback_src"
        assert manifest.files[0].md5 == ""

    async def test_invalid_last_modified_is_ignored(self) -> None:
        """非法 ``Last-Modified`` 不应导致探测失败。"""
        md5 = "3af58ef90a035b275797507c1efecd05"
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(
                headers={
                    "Content-Length": "10",
                    "ETag": f'"{md5}"',
                    "Last-Modified": "not-a-date",
                }
            ),
        )

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        assert manifest.files[0].version == md5

    async def test_invalid_content_length_is_skipped(self) -> None:
        """无法解析的 ``Content-Length`` 视为源不可用。"""
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(headers={"Content-Length": "not-a-number"}),
        )

        assert await transport.fetch_manifest(make_server()) is None

    async def test_missing_content_length_is_skipped(self) -> None:
        """缺少 ``Content-Length`` 时无法构造清单。"""
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(headers={"ETag": '"3af58ef90a035b275797507c1efecd05"'}),
        )

        assert await transport.fetch_manifest(make_server()) is None

    async def test_non_200_is_skipped(self) -> None:
        """非 200 响应（如国服 403）应降级为不可用。"""
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(status=403, headers={"Content-Length": "1"}),
        )

        assert await transport.fetch_manifest(make_server()) is None

    async def test_network_exception_is_skipped(self) -> None:
        """网络异常不得向上抛，统一降级为 ``None``。"""
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(error=RuntimeError("boom")),
        )

        assert await transport.fetch_manifest(make_server()) is None

    async def test_unavailable_sources_are_filtered(self) -> None:
        """``is_available=False`` 的源不参与探测。"""
        transport, session = make_http_transport(
            [make_source(name="disabled", available=False)],
            _FakeHeadResponse(headers={"Content-Length": "1"}),
        )

        assert transport.sources == []
        assert await transport.fetch_manifest(make_server()) is None
        assert session.requested == []

    async def test_empty_sources_returns_none(self) -> None:
        """没有任何可用源时直接返回 ``None``，不打开会话。"""
        transport, session = make_http_transport(
            [], _FakeHeadResponse(headers={"Content-Length": "1"})
        )

        assert await transport.fetch_manifest(make_server()) is None
        assert session.requested == []

    async def test_download_url_falls_back_to_local(self) -> None:
        """服务器地址为空时下载基础 URL 回落为 ``local``。"""
        transport, _session = make_http_transport(
            [make_source()],
            _FakeHeadResponse(headers={"Content-Length": "1"}),
        )

        manifest = await transport.fetch_manifest(make_server(endpoint="", base_url=""))

        assert manifest is not None
        assert manifest.download_url == "local"


# --------------------------------------------------------------------------- #
# LocalIndexTransport
# --------------------------------------------------------------------------- #
def build_tree(root: Path) -> Path:
    """构造包含正常文件与应被忽略文件的目录树。"""
    game = root / "game"
    (game / "sub").mkdir(parents=True)
    (game / "a.bin").write_bytes(b"hello")
    (game / "sub" / "b.bin").write_bytes(b"world!")
    (game / "manifest.json").write_text("{}", encoding="utf-8")
    (game / "Thumbs.db").write_bytes(b"x")
    (game / "x.part").write_bytes(b"x")
    (game / "Y.TMP").write_bytes(b"x")
    return game


@pytest.mark.unit
class TestLocalIndexTransport:
    """本地目录扫描与清单落盘。"""

    async def test_scan_is_recursive_and_ignores_temp_files(
        self, tmp_path: Path
    ) -> None:
        """递归扫描应包含子目录文件，跳过临时文件与自身清单。"""
        game = build_tree(tmp_path)
        transport = LocalIndexTransport(directory=game)

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        assert [file_info.path for file_info in manifest.files] == [
            "a.bin",
            "sub/b.bin",
        ]
        assert manifest.total_size == len(b"hello") + len(b"world!")
        assert manifest.download_url == str(game)
        assert manifest.version.isdigit() and len(manifest.version) == 14
        first = manifest.files[0]
        assert first.name == "a.bin"
        assert first.size == 5
        assert first.md5 == hashlib.md5(b"hello").hexdigest()

    async def test_directory_property_is_exposed(self, tmp_path: Path) -> None:
        """``directory`` 属性应返回构造时传入的路径。"""
        transport = LocalIndexTransport(directory=tmp_path)
        assert transport.directory == tmp_path

    async def test_directory_resolved_from_server(self, tmp_path: Path) -> None:
        """未指定目录时从 ``server.base_url`` / ``endpoint`` 推导。"""
        game = build_tree(tmp_path)
        transport = LocalIndexTransport()

        manifest = await transport.fetch_manifest(
            make_server(endpoint=str(game), base_url="")
        )

        assert manifest is not None
        assert manifest.download_url == str(game)

    async def test_missing_directory_is_reported(self, tmp_path: Path) -> None:
        """目录无法确定时返回 ``None``。"""
        transport = LocalIndexTransport()

        manifest = await transport.fetch_manifest(make_server(endpoint="", base_url=""))

        assert manifest is None

    async def test_nonexistent_directory_returns_none(self, tmp_path: Path) -> None:
        """目录不存在时返回 ``None``。"""
        transport = LocalIndexTransport(directory=tmp_path / "missing")

        assert await transport.fetch_manifest(make_server()) is None

    async def test_directory_without_files_returns_none(self, tmp_path: Path) -> None:
        """只有被忽略文件时视为没有可索引内容。"""
        game = tmp_path / "game"
        game.mkdir()
        (game / "manifest.json").write_text("{}", encoding="utf-8")
        (game / "tmp.part").write_bytes(b"x")
        transport = LocalIndexTransport(directory=game)

        assert await transport.fetch_manifest(make_server()) is None

    async def test_manifest_is_written_atomically(self, tmp_path: Path) -> None:
        """指定 ``manifest_path`` 时应把清单 JSON 落盘。"""
        game = build_tree(tmp_path)
        target = tmp_path / "out" / "manifest.json"
        transport = LocalIndexTransport(directory=game, manifest_path=target)

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        assert target.is_file()
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["download_url"] == str(game)
        assert [item["path"] for item in payload["files"]] == ["a.bin", "sub/b.bin"]
        assert payload["files"][0]["md5"] == hashlib.md5(b"hello").hexdigest()
        assert payload["total_size"] == manifest.total_size

    def test_save_manifest_reports_failure(self, tmp_path: Path) -> None:
        """目标不可替换（这里是目录）时应返回 ``False`` 而不抛异常。"""
        manifest = ResourceManifest(
            version="1",
            files=[],
            total_size=0,
            download_url="local",
        )

        assert LocalIndexTransport.save_manifest(manifest, tmp_path) is False

    async def test_unreadable_file_is_skipped(self, tmp_path: Path) -> None:
        """单个文件读取失败只跳过该文件，不影响整份清单。"""
        game = tmp_path / "game"
        game.mkdir()
        (game / "ok.bin").write_bytes(b"ok")
        (game / "bad.bin").write_bytes(b"bad")

        class _BrokenValidator(Validator):
            """对 ``bad.bin`` 抛 ``OSError`` 的校验器。"""

            def hash_file(self, path: Path | str, algorithm: str = "md5") -> str:
                if Path(path).name == "bad.bin":
                    raise OSError("cannot read")
                return super().hash_file(path, algorithm)

        transport = LocalIndexTransport(directory=game, validator=_BrokenValidator())

        manifest = await transport.fetch_manifest(make_server())

        assert manifest is not None
        assert [file_info.path for file_info in manifest.files] == ["ok.bin"]
