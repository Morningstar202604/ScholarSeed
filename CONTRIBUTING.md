---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_f68fea7c9ba611f1a98a525400f8a581
    ReservedCode1: UO/5F5rQVTDzc4z18iMiHd0o7bBpl0l8xhj77uQLOyRTZlrRrxxWQqQm0LnZEgcrhlvnho5T0sJ/K8sDOilI5tIC1M72YmhGYaoMvUdFcq9emxJQlz95VQYXwW9v4quffWUypBZVSPXrDoQZkBqZ2J+/CThV5Qfqg0/Ify4nLkpzL/e25d8mWIiCE0Y=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_f68fea7c9ba611f1a98a525400f8a581
    ReservedCode2: UO/5F5rQVTDzc4z18iMiHd0o7bBpl0l8xhj77uQLOyRTZlrRrxxWQqQm0LnZEgcrhlvnho5T0sJ/K8sDOilI5tIC1M72YmhGYaoMvUdFcq9emxJQlz95VQYXwW9v4quffWUypBZVSPXrDoQZkBqZ2J+/CThV5Qfqg0/Ify4nLkpzL/e25d8mWIiCE0Y=
---

> **AI 代理（Codex / Cursor / Claude / ZCode 等）请先读 [AGENTS.md](AGENTS.md)**——本仓库的操作纪律（禁用 heredoc 补丁、路径/网络/分支保护约定）与新增工具的计数清单，每条都对应一次真实报错。

## Working rules

* Dependency updates: search the whole repository for every occurrence of a dependency (build files, lockfiles, CI workflows, docs) before bumping. A partial bump — declaration updated but lockfile or a pinned action left behind — is the most common cause of "works locally, CI fails". Keep lockfiles in the same commit as the declaration. Move version-coupled toolchain upgrades together in one commit.
* Refactoring: pull latest main first, work on a fresh branch, keep commits atomic with messages that state the why, and always run the full check suite before pushing (for this repo: `python scripts/validate_plugin.py`, `python -m unittest discover -s tests`, and `ruff check scripts tests`). A branch left behind main cannot be merged under the repository's branch protection.
* Merge conflicts: resolve conflicts in the working tree against the latest main; never force-push shared branches; never resolve a conflict by blindly taking either side — re-read both sides and keep both changes when they are both valid.
* Versioning: releases follow X.Y.Z starting at 0.0.0. Last digit = fixes, middle digit = feature work, first digit stays 0 until a stable release is declared. Bump the version in code, CHANGELOG.md and the tag in the same change.

# 贡献指南

感谢你愿意为 ScholarSeed 贡献代码。请先阅读以下约定，保持项目一致性。

## 开发环境

- 插件本体是纯目录结构，无需构建。
- MCP Server 使用 Python 3.9+，仅标准库，无第三方依赖。
- 校验与测试：`python scripts/validate_plugin.py`、`python -m unittest discover -s tests`。

## 目录约定

```
ScholarSeed/
├── plugin.json            # Agent Plugins 1.0 清单（$schema + name 必填）
├── mcp.json               # MCP Server 配置
├── skills/                # 每个子目录一个技能，含 SKILL.md
│   └── <skill>/
│       ├── SKILL.md       # frontmatter(name/description) + 流程指令
│       └── references/    # 该技能的参考文档
├── scripts/               # MCP Server 与校验工具
└── tests/                 # 单元测试
```

## 修改规范

- **SKILL.md**：frontmatter 必须含 `name` 与 `description`；正文按"目标 → 输入 → 执行流程 → 交付物 → 铁律"组织。
- **scripts/**：仅使用 Python 标准库；新增工具时同步在 `tools/list` 与 `tests/` 注册。
- **plugin.json / mcp.json**：新增顶层字段前确认符合 Agent Plugins 1.0 规范，`$schema` 版本与 mcp.json 一致。
- 所有技能指令不得引入需要伪造凭据或虚假完成状态的内容（见各 SKILL.md 铁律）。

## 提交规范

- 提交信息使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：`feat:` / `fix:` / `docs:` / `test:` / `chore:`。
- 一次提交只做一件事，使用 `git add <具体文件>`，禁止 `git add -A`。
- 提交前运行校验与测试，确保通过。

## 静态检查

- 运行时零依赖（纯标准库）；开发期静态检查用 [ruff](https://docs.astral.sh/ruff/)（配置见 `ruff.toml`）：
  ```bash
  pip install ruff
  ruff check scripts tests
  ```
- CI 在 lint job 中强制执行；本地建议提交前跑一遍。

## 版本号规范（严格 SemVer）

| 变更内容 | 版本动作 |
|----------|----------|
| 仅 Fixed / Chore（无任何新功能） | Z+1（patch） |
| 新增工具 / 技能 / 功能（有 Added 段） | Y+1、Z 归零（minor） |
| 更名、移除工具、数据格式破坏性变更 | X+1（major） |
| 纯工程化（CI/lint/docs） | 不单独发版，随下次产品变更捎带 |

- \alidate_plugin\ 会机械检查：最新条目若无 Added 段却提升了次版本号 → FAIL。
- 一天多次合并时，请在最后一次合并时统一升版一次，避免碎片化小版本。

## Pull Request 流程

1. Fork 本仓库，创建功能分支（如 `feat/xxx`）。
2. 修改后补齐对应测试。
3. 提交 PR，描述改动动机与影响。
4. 维护者 review 通过后合入 main。

## 协议

贡献即表示你同意你的贡献以项目 LICENSE（PolyForm Noncommercial 1.0.0）授权发布。
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
