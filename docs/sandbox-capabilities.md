# Windows 受限环境测试兼容性

本文说明项目为 Windows 受限执行环境提供的 pytest 兼容处理。该处理只影响测试进程，
不会进入生产计算路径；非 Windows 平台直接跳过。

## 问题表现

部分 Windows 受限环境会把 pytest 以显式 POSIX `mode=0o700` 创建的临时目录映射为
限制性 DACL。目录创建后可能无法枚举或清理，导致使用 `tmp_path` 或 `tmpdir` 的测试在
setup 或 teardown 阶段出现 `PermissionError (WinError 5)`。

该问题来自 Windows 目录权限映射与 pytest 临时目录实现的组合，不是业务代码、CLI
子进程或测试夹具内容导致的失败。普通 `mkdir()` 创建的目录不受影响。

## 仓库内处理

根目录 `conftest.py` 在 pytest 启动时执行两项保护：

1. 仅在 Windows 上包装 `os.mkdir` 和 `os.makedirs`，忽略没有 Windows 语义的 POSIX
   mode 参数，让测试临时目录继承默认 DACL。
2. 如果系统临时目录中既有的 pytest 根目录已经无法读取，则把
   `PYTEST_DEBUG_TEMPROOT` 指向工作区内已忽略的 `.pytest-temproot/`。

补丁在 `os.name != "nt"` 时立即返回，因此 Linux 和 macOS 不修改标准库函数或临时目录。
GitHub Actions 会在 Linux 的 Python 3.12 和 3.13 上运行全量测试，持续验证该 no-op
边界。

## 安全与作用域

- 包装只在 pytest 进程中安装，不影响安装后的 CLI 或库调用。
- Windows 测试不依赖 POSIX mode 位；忽略 mode 不改变项目声明的安全边界。
- `.pytest-temproot/` 属运行期产物，已由根 `.gitignore` 排除。
- 补丁不提升权限、不修改系统 ACL，也不调用平台管理工具。

## 验证

本地默认运行不需要额外环境变量或 `--basetemp`：

```text
python -m pytest -q
```

诊断时可显式指定工作区临时根：

```text
python -m pytest -q --basetemp=.pytest-temproot/manual
```

发布前必须同时满足 Windows 本地测试和 Linux CI。若未来 pytest 或 Python 修复该权限
映射，应先在两类平台删除补丁进行回归验证；只有全量测试继续通过，才能移除兼容层。
