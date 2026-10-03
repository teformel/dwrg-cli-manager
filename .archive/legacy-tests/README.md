# 归档：重构前的遗留测试

这些文件是 Pydantic V1 时代（`field_validator` 未导入、`utils/crypto` 与 `security` 并存、
manager 层存在 `password_hash` NameError）写下的脚本式测试，属 `sys.path` hack 风格，
在重构后已全部失效（`TypeError: 'Config' object is not subscriptable` 等）。

保留仅为历史参照，**不参与 pytest 收集**（`testpaths = ["tests"]`）。
现行测试套件见仓库 `tests/`。
