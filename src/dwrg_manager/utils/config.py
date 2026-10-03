"""
配置工具
"""

import os
from pathlib import Path
from typing import Any


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """加载配置文件"""
    if not config_path:
        # 默认配置路径
        home_dir = Path.home()
        config_dir = home_dir / ".config" / "dwrg"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = str(config_dir / "config.yaml")

    if os.path.exists(config_path):
        import yaml
        with open(config_path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    return {}
