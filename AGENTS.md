# AGENTS.md — AI 协作操作纪律

> 本文件面向在本仓库工作的 **AI 编码代理**（Codex / Cursor / Claude / ZCode 等会自动读取 AGENTS.md 的工具）。
> 每条规则都对应一次真实发生的报错或险情（2026-09-05 v0.7.0 开发会话复盘），照做可避免绝大多数失败。
> 人类贡献者请读 [CONTRIBUTING.md](CONTRIBUTING.md)；两者冲突时以本文件的**操作层**规则为准。

## Working rules (English, TL;DR)

- **Never** patch files with heredoc-embedded Python `str.replace()` scripts. Use a real file-edit tool (atomic, shows original text, fails without writing). If a multi-step script is unavoidable, write it to a `.py` file with the edit tool first, `python -m py_compile` it, run it, delete it.
- Never pass files through `/tmp` between Git Bash and Windows Python — Windows Python resolves `/tmp` to `C:\tmp`. Use a workspace-relative `_scratch/` directory and delete it afterwards.
- Call the GitHub API from Python `urllib`, **not** `curl` (curl's TLS to api.github.com is broken on some dev machines: exit 35 / HTTP 000, while git and urllib work). Never print the token.
- `main` is branch-protected and squash-only: feature branch → push → open PR → wait for CI (release-gate × Python 3.9–3.13) all green → `PUT /pulls/{n}/merge {merge_method:"squash"}` → delete remote branch → `git checkout main && git pull`.
- Before every commit run `git status --short`; partial commits (e.g. `ruff --fix` applied but half-committed) leave HEAD red and CI will fail.
- In test fixtures, build backslash paths with `chr(92)`, never by hand-escaping `C:\\Users` — escaping layers are uncontrollable.
- Self-test generated helper scripts with minimal inputs before long runs.
- When adding tools, update every count hotspot listed below; the acceptance line is `validate_plugin.py` (0 failures 0 warnings) + `verify_claims.py`.

## 详细规则（中文）

### 1. 改文件只用编辑工具，禁止 heredoc 字符串替换补丁（最高频报错源）

`python - <<'EOF'` + `str.replace()` 的补丁要穿过多层转义（工具调用 JSON → shell → Python 字面量 → 目标文件），`\n` 可能被写成真实换行、`\\` 层数错乱、`assert old in t` 匹配失败，甚至损坏文件。**正确做法**：Edit/Write 类文件编辑工具；确需脚本时先落盘 `_scratch/*.py`，`python -m py_compile` 自检后运行，用完删除。

### 2. 临时文件路径纪律

Windows Python 不认识 Git Bash 的 `/tmp`（按 `C:\tmp` 解析 → FileNotFoundError）。跨 shell/Python 传递文件一律放 `_scratch/`（仓库内、gitignore 外手动管理）或显式 Windows 绝对路径，用完即删、不进 git。

### 3. GitHub API 用 Python urllib

部分开发机 curl 对 api.github.com 报 SSL 错误（exit 35 / HTTP 000），而 `git push/pull` 与 Python `urllib.request` 均正常。token 从 `git remote get-url origin` 解析，**任何输出中都不得出现 token**。

### 4. main 受分支保护

直推 `git push origin main` 必被 `protected branch hook declined` 拒绝。唯一路径：feature 分支 → 推送 → PR → CI（Python 3.9–3.13 矩阵）全绿 → API squash 合并 → 删远端分支 → 本地 `git pull`。PR 若报 "required status checks are failing"，先确认分支上**最新一次推送**的 CI 结果，旧 SHA 的红不算数，但也别忽略它（多半是漏提交了 lint 修复）。

### 5. 提交完整性

每次提交前 `git status --short` 确认工作区干净或剩余项与本次提交无关。lint/格式化改动与触发它的提交同进同出，或紧随其后补 `style:` 提交——推送前必须完成。

### 6. 测试样例中的反斜杠

手写 `C:\\Users` 经多层转义后层数不可控。用 `"C:" + chr(92) + "Users"` 构造，或用编辑工具直接写入 raw 字符串并立即跑测试验证。

### 7. 临时脚本自检

生成的辅助脚本（API 轮询等）先跑最小入参验证，或内置 try/except 打印结构化错误；不要盲跑长任务。

### 8. 新增/修改工具时的计数清单（本仓库特有，漏一处就不一致）

1. `scripts/paper_tools.py`：函数实现 + `TOOLS` 注册 + `_TOOL_DESC_EN` + `_TOOL_DESC_JA` + `_call_tool` 分发 + （离线确定性检查器）`_GATE_REGISTRY`
2. `scripts/cli.py`：`CHECKERS` 表（及所需 argparse 参数）
3. `tests/test_paper_tools.py`：`TestProtocolHandshake.test_tools_list` 工具名集合
4. `tests/test_descriptions_lexicon.py`：`test_tools_list_names_unchanged` 等工具名集合
5. `README.md` 与 `README.zh-CN.md`：对应分组工具表 + 全文工具计数（"41 tools" 这类数字逐处替换）
6. `CHANGELOG.md`（minor 必须 Added 段）+ `plugin.json`（版本单一来源）+ `plugin.json` description 中的计数
7. `scripts/verify_claims.py`：文档引用扫描的正则名单
8. `docs/ARCHITECTURE.md`：门禁塔归位表 + gate_suite 门禁计数（先数 `_GATE_REGISTRY` 实际条数再写）
9. `skills/paper-writing/SKILL.md`：按阶段接线（合适才接，不硬塞）

**验收线（发布门禁，缺一不可）**：

```bash
python scripts/validate_plugin.py        # 0 失败 0 警告
python -m unittest discover -s tests     # 全绿
python -m ruff check scripts tests benchmarks
python benchmarks/adversarial_suite.py   # 对抗回归
python scripts/verify_claims.py          # 全部通过
python scripts/release_gate.py           # 最终门禁
```
