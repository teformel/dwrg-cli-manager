# 贡献指南

感谢你对第五人格命令行管理器的关注！我们欢迎各种形式的贡献。

## 📋 贡献方式

### 1. 报告问题
- 使用 [GitHub Issues](https://github.com/dwrg-team/dwrg-cli-manager/issues) 报告 bug
- 提供详细的复现步骤和预期行为
- 包含环境信息（操作系统、Python版本等）

### 2. 功能请求
- 在 Issues 中提出新功能建议
- 详细描述功能需求和使用场景
- 讨论实现方案

### 3. 代码贡献
- Fork 项目
- 创建功能分支
- 提交更改
- 创建 Pull Request

## 🚀 开发环境设置

### 1. 克隆项目
```bash
git clone https://github.com/dwrg-team/dwrg-cli-manager.git
cd dwrg-cli-manager
```

### 2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. 安装开发依赖
```bash
pip install -e ".[dev]"
pre-commit install
```

## 📝 代码规范

### 1. Python 代码风格
- 遵循 PEP 8 规范
- 使用 ruff 进行代码检查和格式化
- 使用 mypy 进行类型检查

### 2. 命名约定
- 函数名使用小写字母和下划线
- 类名使用 PascalCase
- 常量使用大写字母和下划线

### 3. 文档字符串
- 使用 Google 风格的文档字符串
- 为所有公共函数和类添加文档
- 包含参数和返回值说明

### 4. 类型注解
- 为所有函数参数和返回值添加类型注解
- 使用 `typing` 模块中的类型

## 🧪 测试

### 1. 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_accounts.py

# 运行覆盖率测试
pytest --cov=src

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 2. 测试规范
- 为每个模块创建对应的测试文件
- 测试覆盖率要求达到 90% 以上
- 包含单元测试和集成测试

## 📋 Pull Request 流程

### 1. 创建 PR 前检查
- 所有测试通过
- 代码通过 ruff 检查
- 代码通过 mypy 检查
- 代码通过 bandit 安全检查

### 2. PR 模板
```markdown
## 变更描述
简要描述这次 PR 的内容

## 变更类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 重构
- [ ] 性能优化

## 测试清单
- [ ] 功能测试通过
- [ ] 兼容性测试通过
- [ ] 性能测试通过

## 相关 Issue
Closes #123
```

### 3. PR 审查流程
- 自动化检查通过
- 至少一名维护者审查
- 所有评论已解决
- CI 检查通过

## 📚 文档贡献

### 1. 文档类型
- 用户文档：README.md、docs/user-guide.md
- 开发文档：docs/development.md、docs/api.md
- 代码注释：模块、类、函数的文档字符串

### 2. 文档规范
- 使用 Markdown 格式
- 包含清晰的示例
- 保持文档更新

## 🤝 社区准则

### 1. 行为准则
- 尊重所有贡献者
- 保持专业和友善
- 专注于技术讨论

### 2. 沟通渠道
- GitHub Issues：用于 bug 报告和功能请求
- GitHub Discussions：用于一般讨论
- 邮件：team@dwrg.com

## 🎯 贡献者认可

### 1. 贡献者列表
- 在 CONTRIBUTORS.md 中记录所有贡献者
- 在版本发布时特别感谢贡献者

### 2. 贡献者等级
- 🌟 新贡献者：首次贡献
- 🔧 积极贡献者：多次提交
- 🏆 核心贡献者：重要功能贡献

## 📞 获取帮助

如果需要帮助，请：
1. 查看 [文档](https://dwrg-cli-manager.readthedocs.io)
2. 搜索 [Issues](https://github.com/dwrg-team/dwrg-cli-manager/issues)
3. 创建新的 Issue
4. 加入 [讨论](https://github.com/dwrg-team/dwrg-cli-manager/discussions)

感谢你的贡献！🎉