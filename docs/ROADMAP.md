# ScholarSeed 开发路线图

> 依据：[EXPERT-PANEL-REVIEW.md](EXPERT-PANEL-REVIEW.md) 专家评审团共识。
> 2026-08-30：仓库以"论文交付质检引擎与写作流水线"定位重置为 v0.1.0，本路线图条目在新版本线下继续有效。
> 原则：**核心永远零依赖（stdlib-only）、启发式永远是提示而非判决、每个版本可独立发布。**
> 状态标记：`[ ]` 未开始 · `[~]` 进行中 · `[x]` 完成

---

## Phase 0 — 工程健康与分发地基（v1.29，目标 2–3 周）

> 目标：让任何人 30 秒内用上 ScholarSeed。

### 0.1 包化重构 `[ ]`
- [ ] 新建 `pyproject.toml`：包名 `scholarseed`，`requires-python >=3.9`，无运行时依赖
- [ ] 将 `paper_tools.py` 拆分为包结构（行为不变，174 测试全绿为验收线）：
  ```
  src/scholarseed/
    checkers/     # style / punctuation / numbers / stats / ai_signature ...
    sources/      # crossref.py / semantic_scholar.py / openalex.py（HTTP 隔离）
    citation/     # 格式化 APA/GB-T/IEEE/MLA/Chicago/BibTeX
    report/       # 报告渲染、评分、分级
    server.py     # MCP stdio 入口（薄壳）
    cli.py        # CLI 入口（薄壳）
  ```
- [ ] `scripts/paper_tools.py` 保留为兼容垫片（向后兼容旧 mcp.json）
- [ ] 测试同步拆分到 `tests/checkers/...`；HTTP 层加录制回放夹具（离线 CI）

### 0.2 发布渠道 `[ ]`
- [ ] 发 PyPI：`pip install scholarseed` 后 `scholarsead version` 可用
  （CLI 名以实际核名为准，如被占用改 `scholarseed-audit`）
- [ ] README 安装区改为三条路径：pip → 插件目录拖放 → Smithery
- [ ] 可选 extras 占位：`scholarseed[pdf]`、`scholarseed[docx]`（Phase 2 实装解析器）

### 0.3 文档站 `[ ]`
- [ ] MkDocs Material（或 GitHub/GitCode Pages 纯静态），内容从 docs/ 迁移
- [ ] 四类 Persona Quick Path 各一页：研究生 / 导师 / 期刊编辑 / 实验室 CI
- [ ] 隐私披露上首页显著位：标题会发送至 Crossref/Semantic Scholar/OpenAlex；提供离线模式说明

**验收标准**：PyPI 可安装且 3.9/3.13 双版本冒烟通过；`release_gate.py` 全绿；文档站上线并链接进两个 README。

---

## Phase 1 — 信任资产补全（v1.30，目标 4–6 周）

> 目标：把"可信"从口号变成公开可验证的数据。

### 1.1 AI 阳性对照基准 `[ ]`（评审团最高优先级项）
- [ ] 构建受控生成集：主流 LLM × 5 体裁（实证/综述/技术/学位论文章节/人文）× 3 强度（普通生成/精调模仿人类/对抗规避），50–100 篇
- [ ] 与现有 70 篇人类语料合并为双组对照，跑出 **检出率 / 误报率 / ROC 曲线**
- [ ] 结果如实写入 CORPUS-BENCHMARK.md——数字不理想也公开发布，测量本身即差异化
- [ ] 分数双轴化：`polish`（打磨度）与 `ai-likeness`（AI 相似度）解耦输出，消除"粗糙≈可疑"混淆

### 1.2 中文核验能力 `[ ]`
- [ ] OpenAlex 中文期刊覆盖评估报告（先测后做）
- [ ] GB/T 7714 条目对中文文献（无 DOI 场景）的诚实降级标注策略
- [ ] 明确不做：爬取知网等侵权方案（写进 SECURITY.md 边界声明）

### 1.3 人文社科校准启动 `[ ]`
- [ ] 发布语料征集说明（志愿者提供已发表人文论文 LaTeX/Markdown，仅保留聚合统计）
- [ ] humanities 模式在拿到 ≥30 篇语料前保持"未经定量校准"显式标注

**验收标准**：基准报告含正负样本双向数据；`check_ai_signature` 输出新双轴 schema 并更新全部下游工具/测试。

---

## Phase 2 — 增长杠杆（v1.31 – v2.0，目标 6–10 周）

> 目标：借 agent 生态与 CI 文化铺开分发。

### 2.1 官方 GitHub Action `[ ]`（ROI 最高单项）
```yaml
- uses: scholarseed/gate-action@v1
  with:
    fail-on: C          # 引文核验门禁
    files: paper.md
```
- [ ] 复合 action：装包 → 跑 `verify-refs --fail-on` + `audit-paper --min-score` → PR 评论报告
- [ ] 提供 3 个模板仓库（LaTeX 论文 / Markdown 学位论文 / 综述）

### 2.2 注册表与扩展 `[ ]`
- [ ] 提交 MCP 官方 Registry；打磨 Smithery 上架页（演示 GIF + 配置示例）
- [ ] Web Playground：Pyodide 在浏览器运行核心检查器（纯静态托管，零服务器成本；联网核验类工具在 demo 中禁用并标注）
- [ ] VS Code 扩展 v0：保存 .md/.tex 时侧边栏跑 proofread（包一层 CLI 即可）

### 2.3 内容与社群 `[ ]`
- [ ] 论文季内容日历：知乎/B站/小红书各 6 篇（"导师如何发现 AI 代写""引文幻觉翻车案例"角度）
- [ ] 征集 10 个实验室在真实仓库启用 CI 门禁，做成案例页

**验收标准**：Action 市场 上架且有非本人仓库的真实运行记录；Playground 上线；≥3 个外部案例。

---

## Phase 3 — 商业试点（v2.x，12 个月视角）

> 目标：在已验证的增长曲线上叠加收入，不动社区层免费承诺。

- [ ] Team 层 SaaS MVP：批量审计任务队列 + 聚合报告仪表盘 + 课题组席位（技术栈建议：FastAPI + SQLite→PG + 前端任意；部署国内云）
- [ ] Institution 层试点：找 1 家期刊编辑部做预审工作流 POC（慢周期，提前接触）
- [ ] 治理准备：CLA/DCO 政策、商标注册（名称+logo）、贡献者指南升级（拆包后贡献门槛大幅下降）
- [ ] 出海叙事包：英文官网 + "deterministic academic integrity for the AI era" 一页纸

---

## 度量看板（每季度复盘）

| 指标 | 现状 | Phase 1 目标 | Phase 2 目标 |
|---|---|---|---|
| pip 月安装量 | —（未发） | 500 | 3,000 |
| CI 门禁周运行次数 | — | 100 | 1,000 |
| 周核验引文数（缓存命中统计） | 无埋点 | 加匿名计数 | 50,000 |
| AI 阳性基准 | 未建立 | 公开报告 | 对抗子集迭代 |
| 外部贡献者 PR 数 | ≈0 | 3 | 10 |
| 机构/期刊试点 | 0 | 接触名单 | 1 家 POC |

---

## 立即行动清单（本周即可开工）

1. 建 `pyproject.toml` + 包骨架，开始拆 `paper_tools.py`（Phase 0.1）——**一切的地基**
2. 写 AI 阳性对照集生成脚本原型（Phase 1.1 先行研究）
3. PyPI 核名与账号准备
4. README 增加 Persona Quick Path 三行入口（半天工作量，立刻改善转化）

## 风险登记

| 风险 | 缓解 |
|---|---|
| 拆包引入回归 | 174 测试为硬验收线 + 兼容垫片 + 单独 PR 小步走 |
| AI 检出率数字难看 | 主动诚实发布，定位"待复核密度提示"；竞品无人敢公开此数 |
| S2/Crossref 条款或限流变化 | sources 层适配器隔离；多源冗余；离线模式保底 |
| "AI 分数"被滥用作处罚依据 | 使用条款显式禁止 + 报告水印免责声明 |
| Agent Plugins 规范尚年轻 | CLI/CI 作为独立于规范的稳定面持续投入 |
