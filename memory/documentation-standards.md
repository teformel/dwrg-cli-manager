---
name: documentation-standards-dwrg
description: 第五人格命令行管理器的文档标准和规范
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# 文档标准和规范 - 第五人格命令行管理器

## 文档理念

基于Vibe Coding理念，我们采用全面且一致的文档策略，确保代码、API和用户文档的完整性和易读性。文档不仅是代码的补充，更是项目的重要组成部分。

## 文档架构

### 1. 文档目录结构

```
docs/
├── README.md                 # 项目概述
├── CHANGELOG.md             # 更新日志
├── CONTRIBUTING.md          # 贡献指南
├── CODE_OF_CONDUCT.md       # 行为准则
├── ARCHITECTURE.md          # 架构设计
├── API.md                   # API文档
├── USER_GUIDE/              # 用户指南
│   ├── installation.md
│   ├── configuration.md
│   ├── account_management.md
│   ├── server_management.md
│   ├── resource_management.md
│   └ troubleshooting.md
├── DEVELOPER_GUIDE/         # 开发者指南
│   ├── development_setup.md
│   ├── coding_standards.md
│   ├── testing_guide.md
│   ├── contribution_workflow.md
│   └── release_process.md
├── EXAMPLES/                # 示例代码
│   ├── basic_usage.py
│   ├── account_management.py
│   ├── server_switching.py
│   ├── batch_operations.py
│   └── custom_plugins.py
├── REFERENCE/               # 参考资料
│   ├── command_reference.md
│   ├── configuration_reference.md
│   ├── api_reference.md
│   └── file_formats.md
└── assets/                 # 文档资源
    ├── images/
    ├── diagrams/
    └── templates/
```

### 2. 文档类型说明

| 文档类型 | 目标读者 | 用途 | 更新频率 |
|---------|---------|------|----------|
| README.md | 所有人 | 项目概述和快速开始 | 版本发布 |
| USER_GUIDE | 终端用户 | 如何使用工具 | 功能更新 |
| DEVELOPER_GUIDE | 开发者 | 如何参与开发 | 代码变更 |
| API.md | 开发者 | API参考文档 | API变更 |
| REFERENCE | 高级用户 | 详细参考资料 | 功能更新 |
| EXAMPLES | 所有人 | 使用示例 | 功能更新 |

## 文档编写规范

### 1. Markdown规范

```markdown
# 一级标题（用于文档标题）

## 二级标题（用于主要章节）

### 三级标题（用于子章节）

#### 四级标题（用于小节）

# 语法规则

- 使用标准的Markdown语法
- 代码块指定语言：```python
- 表格使用标准Markdown表格语法
- 链接使用描述性文本

## 文档结构模板

# 文档标题

## 概述
简要说明文档的目的和内容。

## 前置条件
列出使用本文档内容的前提条件。

## 主要内容
详细说明相关内容。

## 示例
提供具体的使用示例。

## 相关文档
列出相关的参考文档。

## 常见问题
回答常见问题。
```

### 2. 代码示例规范

```markdown
## 基本用法

```python
# 好的代码示例
from dwrg_manager import AccountManager, ServerManager

# 初始化管理器
account_manager = AccountManager()
server_manager = ServerManager()

# 创建账号
account = account_manager.create_account(
    username="test_user",
    server="official",
    password="secure_password"
)
print(f"账号创建成功: {account.username}")
```

## 错误处理示例

```python
# 好的错误处理示例
from dwrg_manager.accounts import AccountError
from dwrg_manager.utils.logger import logger

try:
    account = account_manager.create_account(
        username="test_user",
        server="official",
        password="password"
    )
    logger.info(f"账号创建成功: {account.username}")
except AccountError as e:
    logger.error(f"账号创建失败: {e}")
    print(f"错误: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
    print(f"发生未知错误，请查看日志")
```

## 最佳实践示例

```python
# 好的最佳实践示例
import asyncio
from dwrg_manager.resources import ResourceManager
from dwrg_manager.utils.logger import logger

async def update_game_resources():
    """更新游戏资源的最佳实践示例"""
    try:
        # 1. 初始化资源管理器
        resource_manager = ResourceManager()
        
        # 2. 检查资源状态
        status = await resource_manager.check_resource_status()
        logger.info(f"当前资源状态: {status}")
        
        # 3. 执行更新
        if status.needs_update:
            logger.info("开始更新资源...")
            result = await resource_manager.update_resources()
            
            if result.success:
                logger.info("资源更新成功")
                return True
            else:
                logger.error(f"资源更新失败: {result.error}")
                return False
        else:
            logger.info("资源已是最新版本")
            return True
            
    except Exception as e:
        logger.error(f"资源更新过程中发生错误: {e}")
        return False
```
```

### 3. API文档规范

```markdown
# API文档

## AccountManager

### create_account

创建新的游戏账号。

**语法:**
```python
async def create_account(
    username: str,
    server: str,
    password: str,
    metadata: Optional[Dict] = None
) -> Account
```

**参数:**
- `username` (str): 用户名，长度3-20字符
- `server` (str): 渠道服名称，必须是已知的渠道服
- `password` (str): 密码，长度8-32字符
- `metadata` (Dict, 可选): 额外的账号元数据

**返回值:**
- `Account`: 创建的账号对象

**异常:**
- `AccountError`: 当账号创建失败时抛出
- `ValidationError`: 当参数验证失败时抛出

**示例:**
```python
try:
    account = await account_manager.create_account(
        username="test_user",
        server="official",
        password="secure_password"
    )
    print(f"账号创建成功: {account.id}")
except AccountError as e:
    print(f"账号创建失败: {e}")
```

### switch_account

切换当前活动账号。

**语法:**
```python
async def switch_account(self, account_id: str) -> bool
```

**参数:**
- `account_id` (str): 要切换的账号ID

**返回值:**
- `bool`: 切换成功返回True，失败返回False

**示例:**
```python
success = await account_manager.switch_account("acc_12345")
if success:
    print("账号切换成功")
else:
    print("账号切换失败")
```
```

## 用户文档规范

### 1. 安装指南

```markdown
# 安装指南

## 系统要求

- Python 3.10 或更高版本
- Windows 10/11, macOS 10.15+, 或 Ubuntu 18.04+
- 至少 100MB 可用磁盘空间
- 网络连接用于下载游戏资源

## 安装方法

### 使用pip安装（推荐）

```bash
# 安装最新版本
pip install dwrg-cli-manager

# 安装特定版本
pip install dwrg-cli-manager==1.0.0
```

### 使用源码安装

```bash
# 克隆仓库
git clone https://github.com/your-org/dwrg-cli-manager.git
cd dwrg-cli-manager

# 安装依赖
uv sync

# 安装到系统
pip install -e .
```

### 验证安装

```bash
# 检查版本
dwrg --version

# 查看帮助
dwrg --help
```

## 配置环境

### 初始配置

首次运行时，dwrg会自动创建配置文件：

```bash
# 运行配置向导
dwrg config init
```

### 配置文件位置

- **Windows**: `%USERPROFILE%\.dwrg-cli\config.json`
- **macOS**: `~/.dwrg-cli/config.json`
- **Linux**: `~/.dwrg-cli/config.json`
```

### 2. 用户手册

```markdown
# 用户手册

## 账号管理

### 添加账号

```bash
# 添加官方服账号
dwrg account add --username your_username --server official --password your_password

# 添加B服账号
dwrg account add --username your_username --server bserver --password your_password
```

### 管理账号

```bash
# 列出所有账号
dwrg account list

# 列出特定服务器的账号
dwrg account list --server official

# 切换账号
dwrg account switch --id acc_12345

# 删除账号
dwrg account remove --id acc_12345
```

## 渠道服管理

### 查看可用渠道服

```bash
# 列出所有可用渠道服
dwrg server list

# 查看当前渠道服
dwrg server current
```

### 切换渠道服

```bash
# 切换到官方服
dwrg server switch --server official

# 切换到B服
dwrg server switch --server bserver

# 强制切换（跳过确认）
dwrg server switch --server bserver --force
```

## 资源管理

### 检查资源状态

```bash
# 检查游戏文件完整性
dwrg resource check

# 查看资源详细信息
dwrg resource info
```

### 更新游戏

```bash
# 更新游戏到最新版本
dwrg resource update

# 更新特定渠道服的游戏
dwrg resource update --server official

# 清理缓存
dwrg resource clean
```

## 启动游戏

### 基本启动

```bash
# 使用当前账号启动
dwrg launch

# 使用指定账号启动
dwrg launch --account acc_12345

# 使用指定渠道服启动
dwrg launch --server official

# 同时指定账号和渠道服
dwrg launch --account acc_12345 --server official
```

### 高级启动选项

```bash
# 启动前检查
dwrg launch --check

# 启动诊断模式
dwrg launch --diagnose

# 启动时跳过更新检查
dwrg launch --skip-update-check
```

## 故障排除

### 常见问题

#### 问题1: 账号登录失败

```bash
# 检查账号状态
dwrg account status --id acc_12345

# 重新登录账号
dwrg account login --id acc_12345
```

#### 问题2: 游戏文件损坏

```bash
# 检查文件完整性
dwrg resource check

# 修复游戏文件
dwrg resource repair
```

#### 问题3: 渠道服切换失败

```bash
# 检查渠道服状态
dwrg server info --server official

# 重新切换渠道服
dwrg server switch --server official --force
```

### 获取帮助

```bash
# 查看命令帮助
dwrg help <command>

# 查看详细文档
dwrg help --all

# 联系支持
dwrg support
```
```

## 开发者文档规范

### 1. 开发环境设置

```markdown
# 开发环境设置

## 前置条件

- Python 3.10+
- Git
- UV (Python包管理器)
- Poetry (可选)

## 克隆和设置

```bash
# 克隆仓库
git clone https://github.com/your-org/dwrg-cli-manager.git
cd dwrg-cli-manager

# 使用UV设置开发环境
uv sync --dev

# 或者使用Poetry
poetry install

# 激活虚拟环境
# UV: uv venv
# Poetry: poetry shell
```

## 代码质量检查

```bash
# 运行代码格式化
uv run ruff check .
uv run ruff format .

# 运行类型检查
uv run mypy .

# 运行安全检查
uv run bandit -r src/

# 运行测试
uv run pytest

# 运行所有检查
uv run pre-commit run --all-files
```

## 开发工作流

### 功能开发

1. 创建功能分支
```bash
git checkout -b feature/account-management
```

2. 编写代码和测试
3. 运行测试套件
4. 提交更改
```bash
git add .
git commit -m "feat: add account management functionality"
```

5. 推送分支
```bash
git push origin feature/account-management
```

6. 创建Pull Request

### 代码审查

- 所有代码必须经过同行审查
- 确保所有测试通过
- 检查代码符合项目规范
- 验证文档更新
```

### 2. 架构文档

```markdown
# 架构设计

## 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    CLI Interface                     │
├─────────────────────────────────────────────────────┤
│  Command Parser  │  Config Manager  │  Logger       │
├─────────────────────────────────────────────────────┤
│                    Core Services                     │
├─────────────────────────────────────────────────────┤
│ Account Manager │ Server Manager │ Resource Manager │
├─────────────────────────────────────────────────────┤
│                    Infrastructure                    │
├─────────────────────────────────────────────────────┤
│   Crypto Utils   │   File System   │   HTTP Client  │
└─────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. CLI Interface (CLI接口层)

**职责:**
- 解析命令行参数
- 提供用户交互界面
- 处理错误和帮助信息

**主要类:**
- `App`: 主应用类
- `Command`: 命令基类
- `Option`: 选项基类

**示例:**
```python
# src/dwrg_manager/main.py
from typer import Typer
from dwrg_manager.commands import AccountCommand, ServerCommand

app = Typer()
app.add_typer(AccountCommand.app, name="account")
app.add_typer(ServerCommand.app, name="server")

if __name__ == "__main__":
    app()
```

#### 2. Core Services (核心服务层)

**职责:**
- 提供核心业务逻辑
- 管理应用状态
- 协调各个组件

**主要类:**
- `AccountManager`: 账号管理
- `ServerManager`: 渠道服管理
- `ResourceManager`: 资源管理
- `LauncherManager`: 启动管理

**示例:**
```python
# src/dwrg_manager/accounts/manager.py
from typing import List, Optional
from dwrg_manager.accounts.models import Account
from dwrg_manager.accounts.storage import AccountStorage
from dwrg_manager.utils.crypto import CryptoManager

class AccountManager:
    def __init__(self, config: Config):
        self.config = config
        self.storage = AccountStorage(config.data_dir)
        self.crypto = CryptoManager(config.encryption_key)
    
    async def create_account(self, username: str, server: str, password: str) -> Account:
        # 业务逻辑实现
        pass
    
    async def list_accounts(self, server: Optional[str] = None) -> List[Account]:
        # 业务逻辑实现
        pass
```

#### 3. Infrastructure (基础设施层)

**职责:**
- 提供底层技术支持
- 处理系统交互
- 提供通用工具

**主要组件:**
- `CryptoUtils`: 加密工具
- `FileSystem`: 文件系统操作
- `HTTPClient`: HTTP客户端
- `Logger`: 日志系统

## 数据流

### 账号创建流程

```
用户输入 → CLI解析 → 参数验证 → AccountManager → 
加密处理 → 存储到文件 → 返回结果
```

### 渠道服切换流程

```
用户输入 → CLI解析 → ServerManager → 
检测当前服 → 备份当前文件 → 切换文件 → 验证结果
```

## 设计模式

### 1. 工厂模式

用于创建不同类型的对象。

```python
# src/dwrg_manager/factories.py
from typing import Type, Dict
from dwrg_manager.accounts import Account
from dwrg_manager.servers import Server

class Factory:
    _creators: Dict[str, Type] = {}
    
    @classmethod
    def register(cls, name: str, creator: Type):
        cls._creators[name] = creator
    
    @classmethod
    def create(cls, name: str, **kwargs):
        creator = cls._creators.get(name)
        if not creator:
            raise ValueError(f"Unknown creator: {name}")
        return creator(**kwargs)
```

### 2. 策略模式

用于实现不同的算法。

```python
# src/dwrg_manager/resources/strategies.py
from abc import ABC, abstractmethod
from dwrg_manager.resources.models import ResourceStatus

class UpdateStrategy(ABC):
    @abstractmethod
    async def update(self, resources: List[Resource]) -> ResourceStatus:
        pass

class FullUpdateStrategy(UpdateStrategy):
    async def update(self, resources: List[Resource]) -> ResourceStatus:
        # 实现全量更新逻辑
        pass

class IncrementalUpdateStrategy(UpdateStrategy):
    async def update(self, resources: List[Resource]) -> ResourceStatus:
        # 实现增量更新逻辑
        pass
```

### 3. 观察者模式

用于事件通知。

```python
# src/dwrg_manager/observer.py
from typing import List, Callable
from abc import ABC, abstractmethod

class Observer(ABC):
    @abstractmethod
    def update(self, event: str, data: dict):
        pass

class Observable:
    def __init__(self):
        self._observers: List[Observer] = []
    
    def attach(self, observer: Observer):
        self._observers.append(observer)
    
    def detach(self, observer: Observer):
        self._observers.remove(observer)
    
    def notify(self, event: str, data: dict):
        for observer in self._observers:
            observer.update(event, data)
```

## 扩展性设计

### 1. 插件系统

```python
# src/dwrg_manager/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class Plugin(ABC):
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    def execute(self, command: str, args: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        pass
```

### 2. 配置系统

```python
# src/dwrg_manager/config/manager.py
from pydantic import BaseSettings
from typing import Optional

class Config(BaseSettings):
    app_name: str = "DWRG CLI Manager"
    version: str = "1.0.0"
    debug: bool = False
    
    # 路径配置
    config_dir: str = "~/.dwrg-cli"
    data_dir: str = "~/.dwrg-cli/data"
    cache_dir: str = "~/.dwrg-cli/cache"
    
    # 网络配置
    max_concurrent_downloads: int = 4
    request_timeout: int = 30
    
    class Config:
        env_prefix = "DWRG_"
```
```

## 文档维护

### 1. 文档更新检查

```bash
# 运行文档检查
uv run python scripts/check_docs.py

# 生成API文档
uv run python scripts/generate_api_docs.py

# 检查文档链接
uv run python scripts/check_links.py
```

### 2. 自动化文档生成

```python
# scripts/generate_api_docs.py
"""
自动生成API文档
"""
import inspect
from pathlib import Path
from dwrg_manager.accounts import AccountManager
from dwrg_manager.servers import ServerManager

def generate_api_docs():
    """生成API文档"""
    docs_dir = Path("docs/API.md")
    
    with open(docs_dir, 'w', encoding='utf-8') as f:
        f.write("# API文档\n\n")
        
        # 生成AccountManager文档
        f.write("## AccountManager\n\n")
        for name, method in inspect.getmembers(AccountManager, inspect.isfunction):
            if not name.startswith('_'):
                f.write(f"### {name}\n\n")
                f.write(f"```python\n{inspect.getsource(method)}\n```\n\n")
        
        # 生成ServerManager文档
        f.write("## ServerManager\n\n")
        for name, method in inspect.getmembers(ServerManager, inspect.isfunction):
            if not name.startswith('_'):
                f.write(f"### {name}\n\n")
                f.write(f"```python\n{inspect.getsource(method)}\n```\n\n")
```

### 3. 文档版本控制

```markdown
# 文档版本控制

## 版本历史

| 版本 | 日期 | 更新内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-09-21 | 初始版本 | AI Assistant |
| 1.1.0 | 2026-09-22 | 添加账号管理功能 | AI Assistant |
| 1.2.0 | 2026-09-23 | 添加渠道服管理 | AI Assistant |

## 文档更新流程

1. 修改相应文档
2. 更新版本历史
3. 提交更改
4. 创建Pull Request
5. 合并到主分支
```

这个文档标准提供了完整的文档编写规范和模板，确保项目文档的一致性和完整性。