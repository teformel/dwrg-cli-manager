# 第五人格命令行管理器

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/dwrg-team/dwrg-cli-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/dwrg-team/dwrg-cli-manager/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%2B-brightgreen.svg)](https://github.com/dwrg-team/dwrg-cli-manager/actions/workflows/ci.yml)

一个功能强大的第五人格游戏命令行管理工具，支持多渠道服管理和多账号管理。

## 🚀 特性

- 🎮 **多渠道服管理**: 支持官方服、B服等多种渠道服切换
- 👥 **多账号管理**: 支持多个游戏账号的创建、切换和管理
- 📦 **资源管理**: 自动下载和更新游戏资源
- 🔒 **安全可靠**: 加密存储账号信息，确保数据安全
- 🌍 **国际化支持**: 支持中文、英文等多种语言
- 🔌 **插件系统**: 可扩展的插件架构，支持第三方开发
- ⚡ **高性能**: 异步处理，快速响应
- 🎨 **用户友好**: 美观的命令行界面，清晰的操作提示

## 📦 安装

### 使用 pip 安装

```bash
pip install dwrg-cli-manager
```

### 使用源码安装

```bash
git clone https://github.com/dwrg-team/dwrg-cli-manager.git
cd dwrg-cli-manager
pip install -e .
```

### 使用 uv 安装（推荐）

```bash
uv add dwrg-cli-manager
```

## 🛠️ 使用

### 基础命令

```bash
# 显示版本信息
dwrg --version

# 显示帮助信息
dwrg --help

# 显示详细帮助
dwrg help <command>
```

### 账号管理

```bash
# 添加账号
dwrg account add --username <用户名> --password <密码> [--server <渠道服>]

# 列出所有账号
dwrg account list [--server <渠道服>] [--format <格式>]

# 切换当前账号
dwrg account switch <账号ID>

# 删除账号
dwrg account remove <账号ID>

# 显示账号状态
dwrg account status <账号ID>

# 账号登录
dwrg account login <账号ID>

# 账号登出
dwrg account logout
```

### 渠道服管理

```bash
# 列出所有渠道服
dwrg server list [--format <格式>]

# 显示当前渠道服
dwrg server current

# 检测渠道服状态
dwrg server detect

# 切换渠道服
dwrg server switch <渠道服名称> [--force]

# 显示渠道服信息
dwrg server show <渠道服名称>

# 设置默认渠道服
dwrg server set-default <渠道服名称>
```

### 资源管理

```bash
# 检查游戏文件完整性
dwrg resource check [--server <渠道服>]

# 更新游戏资源
dwrg resource update [--server <渠道服>] [--force]

# 清理缓存
dwrg resource clean [--all]

# 显示缓存信息
dwrg resource info [--server <渠道服>]

# 验证游戏文件
dwrg resource verify [--server <渠道服>]
```

### 启动管理

```bash
# 启动游戏
dwrg launch [--account <账号ID>] [--server <渠道服>] [--verbose]

# 启动诊断
dwrg diagnose [--output <文件>]

# 显示启动状态
dwrg status

# 停止游戏进程
dwrg stop [--force]
```

### 配置管理

```bash
# 显示配置
dwrg config show [--key <键>] [--format <格式>]

# 设置配置值
dwrg config set <键> <值>

# 删除配置项
dwrg config unset <键>

# 重置配置
dwrg config reset [--all]

# 导出配置
dwrg config export [--output <文件>] [--format <格式>]

# 导入配置
dwrg config import [--input <文件>] [--format <格式>]
```

## 📋 输出格式

### 默认格式（人类可读）

```bash
$ dwrg server list
官方服    active    1.0.0    CN
B服      active    1.0.0    CN
测试服   inactive  1.0.0    CN
```

### JSON 格式（机器可解析）

```bash
$ dwrg server list --format json
{
  "servers": [
    {
      "name": "官方服",
      "status": "active",
      "version": "1.0.0",
      "region": "CN"
    },
    {
      "name": "B服",
      "status": "active", 
      "version": "1.0.0",
      "region": "CN"
    }
  ]
}
```

### 表格格式（清晰易读）

```bash
$ dwrg account list --format table
+----------+-----------+---------+---------------------+
| 账号ID   | 用户名    | 渠道服  | 最后登录时间        |
+----------+-----------+---------+---------------------+
| acc123   | player1   | 官方服  | 2026-09-21 10:30:00 |
| acc456   | player2   | B服     | 2026-09-21 09:15:00 |
+----------+-----------+---------+---------------------+
```

## 🔧 配置

### 配置文件位置

- **全局配置**: `~/.config/dwrg/config`
- **项目配置**: `./.dwrg/config`
- **环境变量**: `DWRG_SERVER`, `DWRG_ACCOUNT`

### 配置示例

```yaml
# ~/.config/dwrg/config
server: official
account: acc123
auto_update: true
verbose: false
```

## 🌍 国际化

支持以下语言：
- 🇨🇳 简体中文 (zh-CN)
- 🇹🇼 繁体中文 (zh-TW)  
- 🇺🇸 英语 (en-US)
- 🇯🇵 日语 (ja-JP)
- 🇰🇷 韩语 (ko-KR)
- 🇫🇷 法语 (fr-FR)
- 🇩🇪 德语 (de-DE)
- 🇪🇸 西班牙语 (es-ES)
- 🇷🇺 俄语 (ru-RU)

```bash
# 设置语言
export DWRG_LANG=zh-CN
```

## 🔌 插件系统

### 安装插件

```bash
# 安装插件
dwrg plugin install /path/to/plugin.tar.gz

# 列出插件
dwrg plugin list

# 启用插件
dwrg plugin enable <插件名称>

# 禁用插件
dwrg plugin disable <插件名称>
```

### 开发插件

参考 [插件开发文档](docs/plugin-development.md)

## 🏗️ 项目结构

```
dwrg-cli-manager/
├── src/
│   └── dwrg_manager/
│       ├── __init__.py
│       ├── main.py                 # 主入口
│       ├── cli.py                  # CLI命令定义
│       ├── config/                 # 配置管理
│       ├── accounts/               # 账号管理
│       ├── servers/                # 渠道服管理
│       ├── resources/              # 资源管理
│       ├── launcher/               # 启动管理
│       ├── utils/                  # 工具函数
│       ├── plugins/                # 插件系统
│       ├── i18n/                   # 国际化
│       └── security/               # 安全模块
├── tests/                         # 测试文件
├── docs/                          # 文档
├── scripts/                       # 脚本
├── pyproject.toml                 # 项目配置
├── README.md                      # 项目说明
└── LICENSE                        # 许可证
```

## 🧪 开发

### 环境设置

```bash
# 克隆仓库
git clone https://github.com/dwrg-team/dwrg-cli-manager.git
cd dwrg-cli-manager

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_accounts.py

# 运行覆盖率测试
pytest --cov=src

# 运行性能测试
pytest tests/performance/
```

### 代码格式化

```bash
# 格式化代码
ruff check .
ruff format .

# 类型检查
mypy src/

# 安全检查
bandit -r src/
safety check
```

## 🤝 贡献

欢迎贡献代码！请阅读 [贡献指南](CONTRIBUTING.md) 了解详情。

### 开发流程

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

感谢所有贡献者和支持者！

## 📞 支持

- 📧 邮箱: team@dwrg.com
- 💬 讨论: [GitHub Discussions](https://github.com/dwrg-team/dwrg-cli-manager/discussions)
- 🐛 问题报告: [GitHub Issues](https://github.com/dwrg-team/dwrg-cli-manager/issues)

## 🌟 Star History

如果这个项目对你有帮助，请给我们一个 star ⭐

[![Star History Chart](https://api.star-history.com/svg?repos=dwrg-team/dwrg-cli-manager&type=Date)](https://star-history.com/#dwrg-team/dwrg-cli-manager&Date)