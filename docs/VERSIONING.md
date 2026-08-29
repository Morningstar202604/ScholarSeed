# ScholarSeed 版本管理规范

> 生效版本：1.29.0 · 本文档定义版本号的判定规则、单一来源与发布纪律。

## 1. 语义化版本（SemVer）判定规则

格式 `MAJOR.MINOR.PATCH`（如 `1.29.0`）：

| 位 | 递增条件 | 示例 |
|---|---|---|
| **MAJOR** | 破坏性变更：删除/重命名工具、工具输入输出 schema 不兼容、MCP 协议行为变化、最低 Python 版本提升 | `2.0.0`：移除 `audit_pdf` 或改 `verify_references` 返回结构 |
| **MINOR** | 向后兼容的新功能：新增工具/检查器/skill、已有工具新增可选参数、新增数据文件 | `1.29.0`：新增 `check_tamper_traces` |
| **PATCH** | 缺陷修复与纯重构：行为修复、性能优化、代码去重、文档勘误；不新增能力 | `1.28.2`：统一词统计辅助函数 |

判定口诀：**用户能感知到新能力 → MINOR；用户需要改自己的调用方式 → MAJOR；只是修好或变快 → PATCH**。

启发式检查器的阈值调整按影响面分级：
- 仅影响新样本的告警密度、不改变既有测试契约 → PATCH；
- 改变评分权重/档位边界（须附真实语料回归数据，见 CORPUS-BENCHMARK.md 军规）→ MINOR。

## 2. 版本号单一来源

**`plugin.json` 的 `version` 字段是唯一版本声明处。**

- `scripts/paper_tools.py` 通过 `_load_version()` 动态读取，禁止硬编码字面量（`validate_plugin.py` 以 AST 强制检查）；
- CLI `version` 子命令、MCP `initialize` 响应均派生自该字段；
- 发版时只改 `plugin.json` + 本仓库 CHANGELOG，其余位置自动跟随。

## 3. 发布纪律（每次发版必做）

```bash
python scripts/validate_plugin.py         # 插件规范校验（含版本来源检查）
python -m unittest discover -s tests      # 全量单测
python benchmarks/adversarial_suite.py    # 对抗回归（v1.29.0 起）
ruff check .                              # Lint
python scripts/release_gate.py            # 发布门禁 = 校验 + 测试
```

全部通过后：

1. 更新 `CHANGELOG.md`（Keep a Changelog 格式，日期用发布当日）；
2. 提交信息格式：`release: vX.Y.Z <一句话主题>` 或沿用 feat/fix/refactor 前缀；
3. 打标签：`git tag -a vX.Y.Z -m "..."` 并推送标签——标签是可追溯发布的锚点；
4. CI 绿灯为发布完成的最终判据（Python 3.9–3.13 矩阵）。

## 4. 分支与提交约定

- `main` 为唯一主线，保持随时可发布（CI 必须绿）；
- 功能开发开分支/PR，合并前全量测试通过；
- 提交信息前缀：`feat:` 新功能 / `fix:` 缺陷 / `refactor:` 重构 / `docs:` 文档 / `test:` 测试 / `chore:` 杂项；
- 一个 MINOR 版本可以包含多个 feat + fix，CHANGELOG 中合并为一个条目分 Added/Fixed/Changed/Docs 小节记录。
