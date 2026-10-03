"""
性能冒烟测试

度量两件对 CLI 体验最关键的指标：包导入（启动）耗时，以及在大量渠道服
配置下的 ``list_servers`` 查询耗时。阈值取得较宽松，仅用于捕获数量级回退，
默认被 ``slow`` 标记，可用 ``-m "not slow"`` 跳过。
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import dwrg_manager
from dwrg_manager.config import ConfigManager

#: 导入 ``dwrg_manager.cli``（连带 typer / rich / pydantic 等）允许的最长耗时（秒）
MAX_IMPORT_SECONDS = 8.0

#: 列出 500 个渠道服允许的最长耗时（秒）
MAX_LIST_SECONDS = 3.0

#: 性能测试中构造的渠道服数量
SERVER_COUNT = 500


def _src_dir() -> Path:
    """返回 ``dwrg_manager`` 所在包目录的父目录（即 ``src``）。

    Returns:
        ``src`` 目录路径。
    """
    return Path(dwrg_manager.__file__).resolve().parent.parent


@pytest.mark.performance
@pytest.mark.slow
def test_import_cli_module_stays_within_budget() -> None:
    """子进程中导入 ``dwrg_manager.cli`` 的耗时应在预算之内。"""
    code = (
        "import time;"
        "start = time.perf_counter();"
        "import dwrg_manager.cli;"  # noqa: F401
        "print(time.perf_counter() - start)"
    )
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(_src_dir()) + os.pathsep + existing

    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    duration = float(completed.stdout.strip().splitlines()[-1])
    assert duration < MAX_IMPORT_SECONDS


@pytest.mark.performance
@pytest.mark.slow
def test_list_servers_scales_to_many_entries(tmp_path: Path) -> None:
    """拥有 500 个渠道服时列表查询应保持快速且完整。"""
    manager = ConfigManager(tmp_path / "perf.yaml", autosave=False)
    for index in range(SERVER_COUNT):
        manager.add_server(f"srv-{index:04d}")
    manager.save_config()

    start = time.perf_counter()
    servers = manager.list_servers()
    elapsed = time.perf_counter() - start

    assert len(servers) == SERVER_COUNT + 3  # 默认 3 个内置渠道服
    assert elapsed < MAX_LIST_SECONDS
