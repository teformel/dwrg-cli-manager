---
name: vibe-coding-dwrg-cli
description: 第五人格命令行管理器的vibe coding规范，确保代码质量和一致性
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# Vibe Coding 规范 - 第五人格命令行管理器

## 项目理念
Vibe Coding 是一种注重代码可读性、可维护性和团队协作的编程规范。本规范基于 Python 社区最佳实践，结合现代 Python 开发工具链，打造高质量的项目代码。

## 核心原则

### 1. 类型安全
- 使用 Python 3.10+ 的类型注解
- 所有公共API必须有完整的类型提示
- 使用 `mypy` 进行静态类型检查

### 2. 代码风格
- 使用 `ruff` 进行代码格式化和 linting
- 遵循 PEP 8 规范，但允许 `ruff` 的自动优化
- 最大行长度 88 字符（ruff 默认）

### 3. 错误处理
- 使用具体的异常类型
- 提供有意义的错误信息
- 实现适当的错误恢复机制

### 4. 文档规范
- 所有公共模块、类、函数必须有文档字符串
- 使用 Google 风格的文档字符串
- 关键函数添加使用示例

## 详细规范

### 1. 项目结构规范

```python
# 包级目录结构必须清晰
src/
└── dwrg_manager/
    ├── __init__.py          # 包初始化，版本信息
    ├── main.py             # CLI入口点
    ├── config/             # 配置管理模块
    ├── accounts/           # 账号管理模块
    ├── servers/            # 渠道服管理模块
    ├── resources/          # 资源管理模块
    ├── launcher/           # 启动管理模块
    └── utils/              # 工具函数模块
```

### 2. 模块规范

```python
# __init__.py 规范
"""
第五人格命令行管理器

这是一个用于管理第五人格游戏多渠道服和多账号的命令行工具。
"""

__version__ = "1.0.0"
__author__ = "DWRG CLI Team"
__email__ = "contact@dwrg-cli.com"

# 导出公共API
from .main import app
from .config import ConfigManager
from .accounts import AccountManager
from .servers import ServerManager
```

### 3. 函数规范

```python
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

async def download_game_files(
    file_urls: List[str], 
    save_path: str, 
    max_workers: int = 4
) -> List[str]:
    """
    异步下载游戏文件
    
    Args:
        file_urls: 要下载的文件URL列表
        save_path: 文件保存路径
        max_workers: 最大并发下载数
        
    Returns:
        成功下载的文件路径列表
        
    Raises:
        DownloadError: 下载失败时抛出
        ValidationError: 参数验证失败时抛出
    """
    logger.info(f"开始下载 {len(file_urls)} 个文件")
    
    try:
        # 实现下载逻辑
        pass
    except Exception as e:
        logger.error(f"下载失败: {e}")
        raise DownloadError(f"下载文件失败: {e}")
```

### 4. 类规范

```python
from dataclasses import dataclass
from typing import Dict, Optional
from cryptography.fernet import Fernet

@dataclass
class Account:
    """游戏账号信息"""
    
    id: str                    # 账号唯一标识
    username: str              # 用户名
    server: str                # 所属渠道服
    encrypted_password: bytes   # 加密后的密码
    created_at: datetime       # 创建时间
    last_login: Optional[datetime] = None  # 最后登录时间
    
    def encrypt_password(self, password: str, key: bytes) -> None:
        """加密密码"""
        cipher = Fernet(key)
        self.encrypted_password = cipher.encrypt(password.encode())
    
    def decrypt_password(self, key: bytes) -> str:
        """解密密码"""
        cipher = Fernet(key)
        return cipher.decrypt(self.encrypted_password).decode()
```

### 5. 异步编程规范

```python
import asyncio
from typing import AsyncGenerator

async def process_accounts_batch(
    accounts: List[Account], 
    batch_size: int = 10
) -> AsyncGenerator[List[Account], None]:
    """
    批量处理账号
    
    Args:
        accounts: 账号列表
        batch_size: 批量大小
        
    Yields:
        每批次的账号列表
    """
    for i in range(0, len(accounts), batch_size):
        batch = accounts[i:i + batch_size]
        logger.info(f"处理批次 {i//batch_size + 1}: {len(batch)} 个账号")
        
        # 异步处理批次
        await asyncio.gather(
            *[process_single_account(account) for account in batch]
        )
        
        yield batch
```

### 6. 错误处理规范

```python
from typing import NoReturn

class DWRGError(Exception):
    """基础异常类"""
    pass

class AccountError(DWRGError):
    """账号相关异常"""
    pass

class ServerError(DWRGError):
    """渠道服相关异常"""
    pass

class ResourceError(DWRGError):
    """资源相关异常"""
    pass

def handle_critical_error(error: Exception) -> NoReturn:
    """
    处理严重错误
    
    Args:
        error: 异常对象
        
    Raises:
        SystemExit: 退出程序
    """
    logger.critical(f"严重错误: {error}")
    logger.debug("详细错误信息", exc_info=True)
    
    # 显示用户友好的错误信息
    print(f"错误: {get_user_friendly_error(error)}")
    
    # 退出程序
    raise SystemExit(1)
```

### 7. 日志规范

```python
from loguru import logger
import sys

# 配置日志
logger.remove()  # 移除默认处理器

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

logger.add(
    "logs/dwrg_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
    encoding="utf-8"
)

# 使用示例
logger.info("账号管理器初始化完成")
logger.warning("检测到异常登录尝试")
logger.error("文件下载失败", exc_info=True)
```

### 8. 配置管理规范

```python
from pydantic import BaseSettings, Field
from typing import List, Optional

class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    app_name: str = "DWRG CLI Manager"
    version: str = "1.0.0"
    debug: bool = False
    
    # 路径配置
    config_dir: str = Field(default="~/.dwrg-cli", env="DWRG_CONFIG_DIR")
    data_dir: str = Field(default="~/.dwrg-cli/data", env="DWRG_DATA_DIR")
    cache_dir: str = Field(default="~/.dwrg-cli/cache", env="DWRG_CACHE_DIR")
    
    # 网络配置
    max_concurrent_downloads: int = Field(default=4, ge=1, le=10)
    request_timeout: int = Field(default=30, ge=5, le=300)
    retry_attempts: int = Field(default=3, ge=0, le=5)
    
    # 账号配置
    default_server: Optional[str] = None
    auto_update: bool = True
    
    class Config:
        env_file = ".env"
        env_prefix = "DWRG_"
        
    @property
    def log_dir(self) -> str:
        """日志目录"""
        return f"{self.data_dir}/logs"
```

## 工具配置

### 1. pyproject.toml 配置

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dwrg-cli-manager"
version = "1.0.0"
description = "第五人格命令行管理器"
authors = [{name = "DWRG CLI Team", email = "contact@dwrg-cli.com"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.10"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "typer[all]>=0.9.0",
    "pydantic>=2.0.0",
    "loguru>=0.7.0",
    "cryptography>=41.0.0",
    "aiohttp>=3.8.0",
    "aiofiles>=23.0.0",
    "tqdm>=4.65.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "isort>=5.12.0",
]

[project.scripts]
dwrg-cli = "dwrg_manager.main:app"

[tool.ruff]
line-length = 88
target-version = "py310"
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "W191",  # indentation contains tabs
    "B904",  # Allow raising exceptions without from e, for HTTPException
]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--cov=dwrg_manager",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]
asyncio_mode = "auto"
```

### 2. 预提交钩子

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## 代码审查清单

### 1. 代码质量
- [ ] 所有函数都有完整的类型注解
- [ ] 所有公共API都有文档字符串
- [ ] 错误处理完善且用户友好
- [ ] 日志记录适当且有意义
- [ ] 代码符合项目规范

### 2. 性能考虑
- [ ] 异步操作使用适当的并发控制
- [ ] 文件操作使用异步API
- [ ] 内存使用合理，避免不必要的内存占用
- [ ] 网络请求有适当的超时和重试机制

### 3. 安全性
- [ ] 敏感信息加密存储
- [ ] 输入验证充分
- [ ] 异常信息不泄露敏感数据
- [ ] 依赖库版本安全

### 4. 可维护性
- [ ] 代码结构清晰，职责分明
- [ ] 模块间耦合度低
- [ ] 配置管理集中化
- [ ] 测试覆盖率达标