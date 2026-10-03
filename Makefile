# 第五人格多渠道服 / 多账号命令行管理器 —— 常用开发任务
#
# 用法：make <目标>；不带参数运行 `make` 会打印帮助。
#
# 适用平台：Linux / WSL / macOS / Git Bash。
# Windows 原生 PowerShell 环境请改用 scripts/setup.ps1，
# 并直接执行等价的 `python -m <工具>` 命令。
#
# 可用变量覆盖：PYTHON=python3.12 make check

PYTHON   ?= python
SRC_DIR  ?= src
TEST_DIR ?= tests
DIST_DIR ?= dist
COV_DIR  ?= htmlcov

.DEFAULT_GOAL := help

.PHONY: help install install-dev fmt fmt-check lint type test test-unit test-integration cov check build clean docs-serve docs-build

## help: 显示本帮助（默认目标）
help:
	@printf '%s\n' "可用目标："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@printf '\n%s\n' "变量覆盖示例：make check PYTHON=python3.12"

## install: 安装运行依赖（不含 dev 依赖）
install:
	$(PYTHON) -m pip install .

## install-dev: 以可编辑模式安装项目，并带上 dev 额外依赖
install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

## fmt: 自动格式化源码并应用安全的 lint 修复
fmt:
	$(PYTHON) -m ruff format $(SRC_DIR)
	$(PYTHON) -m ruff check --fix $(SRC_DIR)

## fmt-check: 仅检查格式，不修改任何文件
fmt-check:
	$(PYTHON) -m ruff format --check $(SRC_DIR)

## lint: 运行 ruff 静态检查
lint:
	$(PYTHON) -m ruff check $(SRC_DIR)

## type: 运行 mypy 类型检查
type:
	$(PYTHON) -m mypy $(SRC_DIR)

## test: 运行全部测试（覆盖率参数已在 pyproject 的 addopts 中配置）
test:
	$(PYTHON) -m pytest

## test-unit: 只运行标记为 unit 的测试
test-unit:
	$(PYTHON) -m pytest -m unit

## test-integration: 只运行标记为 integration 的测试
test-integration:
	$(PYTHON) -m pytest -m integration

## cov: 运行测试并输出覆盖率摘要与 HTML 报告
cov:
	$(PYTHON) -m pytest --cov=$(SRC_DIR) --cov-report=term-missing --cov-report=html
	@printf 'HTML 覆盖率报告：%s/index.html\n' "$(COV_DIR)"

## check: 本地质量门禁：格式检查 + lint + 类型检查 + 测试
check: fmt-check lint type test
	@printf '%s\n' "全部检查通过 ✅"

## build: 清理后构建 sdist 与 wheel 到 dist/
build: clean
	$(PYTHON) -m build
	@ls -l $(DIST_DIR)

## clean: 清理构建产物与各类缓存
clean:
	rm -rf $(DIST_DIR) build
	rm -rf $(SRC_DIR)/*.egg-info *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf $(COV_DIR) coverage.xml .coverage
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +

## docs-serve: 本地预览文档（默认 http://127.0.0.1:8000）
docs-serve:
	$(PYTHON) -m mkdocs serve

## docs-build: 构建静态文档到 site/
docs-build:
	$(PYTHON) -m mkdocs build --strict
