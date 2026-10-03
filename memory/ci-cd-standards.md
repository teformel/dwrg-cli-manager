---
name: ci-cd-standards-dwrg
description: 第五人格命令行管理器的CI/CD流程和标准
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# CI/CD标准和规范 - 第五人格命令行管理器

## CI/CD理念

基于Vibe Coding理念，我们采用现代化的CI/CD流程，确保代码质量、自动化测试、持续集成和快速部署。使用GitHub Actions作为CI/CD平台，实现从代码提交到发布的全自动化流程。

## CI/CD架构

### 1. 工作流目录结构

```
.github/
├── workflows/
│   ├── ci.yml                 # 持续集成工作流
│   ├── tests.yml              # 测试工作流
│   ├── security.yml           # 安全扫描工作流
│   ├── release.yml            # 发布工作流
│   └── update-dependencies.yml # 依赖更新工作流
├── dependabot.yml             # 依赖自动更新配置
└── ISSUE_TEMPLATE/            # 问题模板
    ├── bug_report.yml
    └── feature_request.yml
```

### 2. 持续集成工作流

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality-check:
    name: 代码质量检查
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 代码格式检查
      run: |
        uv run ruff check .
        uv run ruff format --check .
        
    - name: 类型检查
      run: |
        uv run mypy .
        
    - name: 安全扫描
      run: |
        uv run bandit -r src/
        
    - name: 依赖安全检查
      run: |
        uv run safety check
        
  tests:
    name: 测试
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.10', '3.11', '3.12']
        
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 运行测试
      run: |
        uv run pytest --cov=dwrg_manager --cov-report=xml --cov-report=term-missing
        
    - name: 上传覆盖率报告
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        
  build:
    name: 构建分发包
    needs: [quality-check, tests]
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装构建依赖
      run: |
        python -m pip install --upgrade pip
        pip install build twine
        
    - name: 构建分发包
      run: |
        python -m build
        
    - name: 检查分发包
      run: |
        python -m twine check dist/*
        
    - name: 上传构建产物
      uses: actions/upload-artifact@v3
      with:
        name: dist-packages
        path: dist/
```

### 3. 测试工作流

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
    paths-ignore:
      - 'docs/**'
      - 'README.md'
  pull_request:
    branches: [ main ]

jobs:
  unit-tests:
    name: 单元测试
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 运行单元测试
      run: |
        uv run pytest tests/unit/ -v --cov=dwrg_manager.unit
        
  integration-tests:
    name: 集成测试
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 运行集成测试
      run: |
        uv run pytest tests/integration/ -v --cov=dwrg_manager.integration
        
  performance-tests:
    name: 性能测试
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 运行性能测试
      run: |
        uv run pytest tests/performance/ -v --cov=dwrg_manager.performance
        
  e2e-tests:
    name: 端到端测试
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 运行端到端测试
      run: |
        uv run pytest tests/e2e/ -v --cov=dwrg_manager.e2e
```

### 4. 安全扫描工作流

```yaml
# .github/workflows/security.yml
name: Security

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * 1'  # 每周一凌晨2点

jobs:
  security-scan:
    name: 安全扫描
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装安全工具
      run: |
        python -m pip install --upgrade pip
        pip install bandit safety semgrep
      
    - name: 运行Bandit静态分析
      run: |
        bandit -r src/ -f json -o bandit-report.json
        bandit -r src/ -f text
      
    - name: 运行Safety依赖检查
      run: |
        safety check --json --output safety-report.json
        safety check
      
    - name: 运行Semgrep漏洞扫描
      run: |
        semgrep --config=auto --json --output=semgrep-report.json src/
        semgrep --config=auto src/
      
    - name: 上传安全报告
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: |
          bandit-report.json
          safety-report.json
          semgrep-report.json
          
    - name: 创建安全问题
      if: always()
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          const path = 'bandit-report.json';
          if (fs.existsSync(path)) {
            const report = JSON.parse(fs.readFileSync(path, 'utf8'));
            if (report.results && report.results.length > 0) {
              report.results.forEach(issue => {
                github.rest.issues.create({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  title: `Security issue: ${issue.test_id}`,
                  body: `**Type:** ${issue.issue_severity}\n**Location:** ${issue.filename}:${issue.line_number}\n**Confidence:** ${issue.confidence}\n\n**Code:**\n\`\`\`\n${issue.code}\n\`\`\`\n\n**Description:** ${issue.issue_text}`,
                  labels: ['security', 'bandit'],
                  assignees: ['security-team']
                });
              });
            }
          }
```

### 5. 发布工作流

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    name: 发布
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装发布依赖
      run: |
        python -m pip install --upgrade pip
        pip install build twine
        
    - name: 构建分发包
      run: |
        python -m build
        
    - name: 检查分发包
      run: |
        python -m twine check dist/*
        
    - name: 创建GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/*
        draft: false
        prerelease: false
        generate_release_notes: true
        
    - name: 发布到PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: |
        python -m twine upload dist/*
        
    - name: 创建Release Issue
      uses: actions/github-script@v6
      with:
        script: |
          github.rest.issues.create({
            owner: context.repo.owner,
            repo: context.repo.repo,
            title: 'Release Notes',
            body: '## Release Notes\n\nPlease update the release notes for this version.',
            labels: ['release', 'documentation']
          });
```

## 依赖管理

### 1. 依赖更新工作流

```yaml
# .github/workflows/update-dependencies.yml
name: Update Dependencies

on:
  schedule:
    - cron: '0 3 * * 1'  # 每周一凌晨3点
  workflow_dispatch:

jobs:
  update-dependencies:
    name: 更新依赖
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖更新工具
      run: |
        python -m pip install --upgrade pip
        pip install uv pip-tools
        
    - name: 更新依赖
      run: |
        uv sync --upgrade
        
    - name: 生成锁定文件
      run: |
        uv pip compile pyproject.toml -o requirements.txt
        
    - name: 提交更新
      uses: stefanzweifel/git-auto-commit-action@v4
      with:
        commit_message: 'chore: update dependencies'
        file_pattern: 'pyproject.toml requirements.txt'
```

### 2. Dependabot配置

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "03:00"
    open-pull-requests-limit: 10
    reviewers:
      - "maintainers"
    assignees:
      - "maintainers"
    commit-message:
      prefix: "deps"
      include: "scope"
    
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
    reviewers:
      - "maintainers"
    assignees:
      - "maintainers"
```

## 代码质量门禁

### 1. 质量检查配置

```yaml
# .github/workflows/quality-gate.yml
name: Quality Gate

on:
  pull_request:
    branches: [ main ]

jobs:
  quality-gate:
    name: 质量门禁
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 检查测试覆盖率
      run: |
        coverage=$(uv run pytest --cov=dwrg_manager --cov-report=term-missing | grep -o 'total.*%' | awk '{print $2}')
        if (( $(echo "$coverage < 90" | bc -l) )); then
          echo "测试覆盖率不足: $coverage%"
          exit 1
        fi
        echo "测试覆盖率达标: $coverage%"
        
    - name: 检查代码质量
      run: |
        # 运行代码质量检查
        uv run ruff check .
        uv run ruff format --check .
        uv run mypy .
        
        # 检查代码复杂度
        uv run radon cc src/ -nb -a
        uv run radon mi src/ -nb
        
    - name: 检查安全漏洞
      run: |
        uv run bandit -r src/ -f json -o bandit-report.json
        if [ -f bandit-report.json ]; then
          issues=$(jq '.results | length' bandit-report.json)
          if [ "$issues" -gt 0 ]; then
            echo "发现 $issues 个安全问题"
            exit 1
          fi
        fi
        
    - name: 检查依赖安全性
      run: |
        uv run safety check --json --output safety-report.json
        if [ -f safety-report.json ]; then
          vulns=$(jq '.vulnerabilities | length' safety-report.json)
          if [ "$vulns" -gt 0 ]; then
            echo "发现 $vulns 个依赖漏洞"
            exit 1
          fi
        fi
```

## 环境管理

### 1. 环境变量管理

```yaml
# .github/envs.yml
environments:
  development:
    name: Development
    url: https://dev.dwrg-cli.com
    variables:
      DEBUG: "true"
      LOG_LEVEL: "DEBUG"
      DATABASE_URL: "sqlite:///dev.db"
      
  staging:
    name: Staging
    url: https://staging.dwrg-cli.com
    variables:
      DEBUG: "false"
      LOG_LEVEL: "INFO"
      DATABASE_URL: "postgresql://user:pass@staging-db:5432/dwrg"
      
  production:
    name: Production
    url: https://dwrg-cli.com
    variables:
      DEBUG: "false"
      LOG_LEVEL: "INFO"
      DATABASE_URL: "postgresql://user:pass@prod-db:5432/dwrg"
```

### 2. 密钥管理

```yaml
# .github/secrets.yml
secrets:
  PYPI_API_TOKEN:
    description: PyPI API token for publishing packages
    required: true
    
  AWS_ACCESS_KEY_ID:
    description: AWS access key for S3 storage
    required: false
    
  AWS_SECRET_ACCESS_KEY:
    description: AWS secret key for S3 storage
    required: false
    
  DATABASE_URL:
    description: Database connection URL
    required: false
    
  ENCRYPTION_KEY:
    description: Master encryption key for sensitive data
    required: true
```

## 监控和日志

### 1. 构建监控

```yaml
# .github/workflows/monitoring.yml
name: Monitoring

on:
  workflow_run:
    workflows: ["CI", "Release"]
    types: [completed]

jobs:
  monitor-build:
    name: 监控构建状态
    runs-on: ubuntu-latest
    
    steps:
    - name: 检查构建状态
      uses: actions/github-script@v6
      with:
        script: |
          const { owner, repo } = context.repo;
          const workflowRun = await github.rest.actions.getWorkflowRun({
            owner,
            repo,
            run_id: context.workflow_run.id
          });
          
          const conclusion = workflowRun.data.conclusion;
          
          if (conclusion === 'failure') {
            await github.rest.issues.create({
              owner,
              repo,
              title: 'Build Failed',
              body: `The workflow ${workflowRun.data.name} failed.`,
              labels: ['alert', 'build'],
              assignees: ['maintainers']
            });
          }
          
          console.log(`Build conclusion: ${conclusion}`);
```

### 2. 性能监控

```yaml
# .github/workflows/performance-monitoring.yml
name: Performance Monitoring

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  performance-benchmark:
    name: 性能基准测试
    runs-on: ubuntu-latest
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      
    - name: 设置Python环境
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install uv
        uv sync
        
    - name: 运行性能基准测试
      run: |
        uv run pytest tests/performance/benchmark.py --benchmark-only
        
    - name: 上传性能报告
      uses: actions/upload-artifact@v3
      with:
        name: performance-report
        path: benchmark-report.json
        
    - name: 比较性能
      uses: benchmark-action/github-action-benchmark@v1
      with:
        name: Performance Benchmark
        tool: 'pytest-benchmark'
        output-file-path: benchmark-report.json
        # 自动创建问题
        auto-create-issue: true
        # 性能退化阈值
        alert-threshold: '5%'
```

## 部署策略

### 1. 蓝绿部署

```yaml
# .github/workflows/blue-green-deploy.yml
name: Blue-Green Deployment

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    name: 蓝绿部署
    runs-on: ubuntu-latest
    
    steps:
    - name: 部署到绿色环境
      run: |
        echo "部署到绿色环境..."
        # 部署逻辑
        
    - name: 运行健康检查
      run: |
        echo "运行健康检查..."
        # 健康检查逻辑
        
    - name: 切换流量
      run: |
        echo "切换流量到绿色环境..."
        # 流量切换逻辑
        
    - name: 回滚绿色环境
      if: failure()
      run: |
        echo "回滚到蓝色环境..."
        # 回滚逻辑
```

### 2. 金丝雀发布

```yaml
# .github/workflows/canary-deploy.yml
name: Canary Deployment

on:
  push:
    tags: ['v*']

jobs:
  canary-deploy:
    name: 金丝雀发布
    runs-on: ubuntu-latest
    
    steps:
    - name: 部署金丝雀版本
      run: |
        echo "部署金丝雀版本到 10% 流量..."
        # 部署逻辑
        
    - name: 监控金丝雀版本
      run: |
        echo "监控金丝雀版本性能..."
        # 监控逻辑
        
    - name: 扩展金丝雀版本
      if: success()
      run: |
        echo "扩展金丝雀版本到 50% 流量..."
        # 扩展逻辑
        
    - name: 全面部署
      if: success()
      run: |
        echo "全面部署到 100% 流量..."
        # 全面部署逻辑
```

这个CI/CD标准文档提供了完整的持续集成和持续部署流程，确保项目的自动化构建、测试、发布和监控。