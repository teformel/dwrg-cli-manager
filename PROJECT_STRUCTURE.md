# 项目结构说明

## 📁 目录结构

```
dwrg-cli-manager/
├── src/
│   └── dwrg_manager/
│       ├── __init__.py                 # 包初始化文件
│       ├── main.py                     # 主入口文件
│       ├── cli.py                      # CLI命令定义
│       ├── accounts/                   # 账号管理模块
│       │   ├── __init__.py
│       │   ├── models.py               # 账号数据模型
│       │   └── manager.py              # 账号管理器
│       ├── servers/                    # 渠道服管理模块
│       │   ├── __init__.py
│       │   ├── models.py               # 渠道服数据模型
│       │   └── manager.py              # 渠道服管理器
│       ├── resources/                   # 资源管理模块
│       │   ├── __init__.py
│       │   ├── models.py               # 资源数据模型
│       │   └── manager.py              # 资源管理器
│       ├── launcher/                   # 启动管理模块
│       │   ├── __init__.py
│       │   ├── models.py               # 启动数据模型
│       │   └── manager.py              # 启动管理器
│       ├── config/                     # 配置管理模块
│       │   ├── __init__.py
│       │   ├── models.py               # 配置数据模型
│       │   └── manager.py              # 配置管理器
│       ├── utils/                      # 工具模块
│       │   ├── __init__.py
│       │   ├── logger.py               # 日志工具
│       │   ├── version.py              # 版本信息
│       │   └── config.py               # 配置工具
│       ├── plugins/                    # 插件系统模块
│       │   ├── __init__.py
│       │   ├── base.py                 # 插件基类
│       │   ├── manager.py              # 插件管理器
│       │   └── models.py               # 插件数据模型
│       ├── i18n/                       # 国际化模块
│       │   ├── __init__.py
│       │   ├── translator.py           # 翻译器
│       │   └── datetime_utils.py       # 日期时间工具
│       └── security/                   # 安全模块
│           ├── __init__.py
│           ├── crypto.py               # 加密工具
│           └── validation.py           # 验证工具
├── tests/                             # 测试目录
│   ├── __init__.py
│   ├── test_main.py                   # 主模块测试
│   ├── test_accounts.py               # 账号管理测试
│   ├── test_servers.py                # 渠道服管理测试
│   ├── test_resources.py              # 资源管理测试
│   ├── test_launcher.py               # 启动管理测试
│   ├── test_config.py                 # 配置管理测试
│   ├── test_plugins.py                # 插件系统测试
│   ├── test_i18n.py                  # 国际化测试
│   ├── test_security.py               # 安全模块测试
│   ├── test_utils.py                  # 工具模块测试
│   ├── integration/                   # 集成测试
│   │   ├── __init__.py
│   │   ├── test_account_switch.py     # 账号切换集成测试
│   │   ├── test_server_switch.py      # 渠道服切换集成测试
│   │   └── test_game_launch.py       # 游戏启动集成测试
│   └── performance/                  # 性能测试
│       ├── __init__.py
│       ├── test_account_performance.py
│       ├── test_server_performance.py
│       └── test_resource_performance.py
├── docs/                              # 文档目录
│   ├── user-guide.md                  # 用户指南
│   ├── developer-guide.md             # 开发者指南
│   ├── api-reference.md               # API参考
│   ├── plugin-development.md          # 插件开发指南
│   ├── configuration.md               # 配置说明
│   ├── troubleshooting.md            # 故障排除
│   └── examples/                     # 示例代码
│       ├── basic_usage.py             # 基础使用示例
│       ├── account_management.py      # 账号管理示例
│       ├── server_management.py       # 渠道服管理示例
│       ├── resource_management.py     # 资源管理示例
│       └── plugin_example.py          # 插件开发示例
├── scripts/                          # 脚本目录
│   ├── build.sh                      # 构建脚本
│   ├── test.sh                       # 测试脚本
│   ├── deploy.sh                     # 部署脚本
│   ├── format.sh                     # 代码格式化脚本
│   └── release.sh                    # 发布脚本
├── pyproject.toml                    # 项目配置文件
├── README.md                         # 项目说明
├── LICENSE                           # 许可证
├── CONTRIBUTING.md                   # 贡献指南
├── .gitignore                        # Git忽略文件
├── PROJECT_STRUCTURE.md              # 项目结构说明
└── MEMORY.md                         # 项目记忆文档
```

## 🏗️ 核心模块说明

### 1. 主入口模块 (`main.py`)
- 负责应用程序的入口点
- 设置日志系统
- 初始化CLI应用

### 2. CLI命令模块 (`cli.py`)
- 定义所有CLI命令
- 处理用户输入和输出
- 调用相应的管理器

### 3. 账号管理模块 (`accounts/`)
- **models.py**: 账号数据模型，定义账号结构
- **manager.py**: 账号管理器，处理账号的CRUD操作

### 4. 渠道服管理模块 (`servers/`)
- **models.py**: 渠道服数据模型，定义渠道服结构
- **manager.py**: 渠道服管理器，处理渠道服的CRUD操作

### 5. 资源管理模块 (`resources/`)
- **models.py**: 资源数据模型，定义资源结构
- **manager.py**: 资源管理器，处理资源下载、更新、验证

### 6. 启动管理模块 (`launcher/`)
- **models.py**: 启动数据模型，定义启动配置
- **manager.py**: 启动管理器，处理游戏启动、停止

### 7. 配置管理模块 (`config/`)
- **models.py**: 配置数据模型，定义配置结构
- **manager.py**: 配置管理器，处理配置的读取、写入

### 8. 工具模块 (`utils/`)
- **logger.py**: 日志工具，提供日志记录功能
- **version.py**: 版本信息，提供版本获取功能
- **config.py**: 配置工具，提供配置加载功能

### 9. 插件系统模块 (`plugins/`)
- **base.py**: 插件基类，定义插件接口
- **manager.py**: 插件管理器，处理插件加载、卸载
- **models.py**: 插件数据模型，定义插件结构

### 10. 国际化模块 (`i18n/`)
- **translator.py**: 翻译器，提供多语言支持
- **datetime_utils.py**: 日期时间工具，提供本地化日期时间处理

### 11. 安全模块 (`security/`)
- **crypto.py**: 加密工具，提供数据加密功能
- **validation.py**: 验证工具，提供输入验证功能

## 🧪 测试结构

### 1. 单元测试 (`tests/`)
- 每个模块都有对应的测试文件
- 测试单个函数和类的功能
- 使用 pytest 框架

### 2. 集成测试 (`tests/integration/`)
- 测试多个模块之间的交互
- 测试完整的用户流程
- 模拟真实使用场景

### 3. 性能测试 (`tests/performance/`)
- 测试系统性能
- 测试并发处理能力
- 测试内存使用情况

## 📚 文档结构

### 1. 用户文档 (`docs/`)
- **user-guide.md**: 用户指南，介绍如何使用工具
- **troubleshooting.md**: 故障排除，解决常见问题
- **configuration.md**: 配置说明，介绍配置选项

### 2. 开发文档 (`docs/`)
- **developer-guide.md**: 开发者指南，介绍如何参与开发
- **api-reference.md**: API参考，详细的API文档
- **plugin-development.md**: 插件开发指南，介绍如何开发插件

### 3. 示例代码 (`docs/examples/`)
- 提供各种使用场景的示例代码
- 帮助用户快速上手

## 🔧 脚本说明

### 1. 构建脚本 (`scripts/`)
- **build.sh**: 构建项目，生成分发包
- **test.sh**: 运行测试，检查代码质量
- **deploy.sh**: 部署项目，发布到生产环境

### 2. 代码质量脚本 (`scripts/`)
- **format.sh**: 格式化代码，统一代码风格
- **release.sh**: 发布项目，创建新版本

## 📋 配置文件

### 1. 项目配置 (`pyproject.toml`)
- 定义项目依赖
- 配置构建选项
- 设置代码质量工具

### 2. Git配置 (`.gitignore`)
- 定义Git忽略规则
- 排除不需要版本控制的文件

## 🎯 设计原则

### 1. 模块化设计
- 每个模块都有明确的职责
- 模块之间松耦合
- 易于测试和维护

### 2. 可扩展性
- 支持插件系统
- 支持多种渠道服
- 支持多种账号类型

### 3. 用户友好
- 提供清晰的命令行界面
- 提供详细的错误信息
- 提供丰富的输出格式

### 4. 安全可靠
- 加密存储敏感信息
- 验证用户输入
- 提供错误恢复机制

这个项目结构确保了代码的可维护性、可扩展性和可测试性，为项目的长期发展奠定了坚实的基础。