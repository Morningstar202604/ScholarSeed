<div align="center">

<img src="docs/assets/logo.svg" width="116" alt="ScholarSeed——从书本中发芽的种子与验证对勾"/>

# ScholarSeed

**论文交付质检引擎与写作流水线**——基于 [Agent Plugins 1.0](https://agents.md/blog/2025-12-16-plugins/) 规范构建的确定性 [MCP 服务器](https://modelcontextprotocol.io) + CLI + 技能包：**每条引用对实时数据库核验、每条统计红线强制执行、每道门禁输出随稿留档**，把草稿变成"能交出去"的论文。

[![CI](https://github.com/Morningstar202604/ScholarSeed/actions/workflows/ci.yml/badge.svg)](https://github.com/Morningstar202604/ScholarSeed/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/tag/Morningstar202604/ScholarSeed?label=release&sort=semver)](https://github.com/Morningstar202604/ScholarSeed/releases)
[![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-purple.svg)](LICENSE)
![Spec](https://img.shields.io/badge/spec-Agent%20Plugins%201.0-8A2BE2.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**51 个确定性 MCP 工具 · 5 项流水线技能 · 70 篇 × 9 学科真实论文校准 · 零依赖（纯标准库）**

与 [AgentSeed](https://github.com/Morningstar202604/AgentSeed)（代码防幻觉）组成矩阵：AgentSeed 保证代码不撒谎，ScholarSeed 保证论文能交付——**随便用哪个 AI 写初稿，提交前必须过一道能自证清白的门。**

> 🇬🇧 English documentation: [README.md](README.md)

</div>

---

## 目录

- [为什么需要 ScholarSeed](#为什么需要-scholarseed)
- [工作原理](#工作原理)
- [写作流水线](#写作流水线)
- [写作自检，不是判决机器](#写作自检不是判决机器)
- [快速体验](#快速体验)
- [场景：该跑哪个？](#场景该跑哪个)
- [核心能力](#核心能力)
- [五项技能](#五项技能)
- [MCP 工具](#mcp-工具)
- [语料基准](#语料基准)
- [安装](#安装)
- [CLI（无需智能体）](#cli无需智能体)
- [文档索引](#文档索引)
- [FAQ](#faq)
- [兼容客户端 · 范围与局限 · 开发 · 安全](#兼容客户端)

## 为什么需要 ScholarSeed

学术写作的瓶颈已经变了：**写初稿不再是问题**——任何大模型几分钟就能给出可用初稿；**"交得出去"才是问题**——编造的参考文献直接触发桌拒，`p=0.000` 和缺效应量会招来审稿人火力，图表编号断层和引用格式混用显得不严谨，越来越多高校和期刊还在加 AIGC 合规门槛。

ScholarSeed 就是围绕这个不对称构建的：

| | 通用 AI 写作助手 | ScholarSeed |
|---|---|---|
| 为你做什么 | 生成正文（质量随模型浮动） | **判定正文能不能交付**——规则可复现，每条发现带行号证据 |
| 引用真实性 | 取决于模型的记忆 | **实时核验 Crossref / Semantic Scholar / OpenAlex，A/B/C 分级，可作 CI 硬门禁** |
| 统计报告 | 模型猜 | **红线机检**：每个 p 值旁应有检验名、`p=0.000` 必须改写、显著结论需效应量+CI、样本分桶加和一致性 |
| 可复现性 | 随模型静默漂移 | **同输入 → 同报告**，永远 |
| 运行位置 | 云端应用 | 任何能跑 Python 3.9+ 的地方：笔记本、实验室服务器、CI 管道、物理隔离机 |
| 依赖 | 专有服务 | 零（纯标准库） |

**一句话定位**：ScholarSeed 是学术写作的 Ruff/ESLint——横在"初稿写完了"和"论文能提交了"之间的**带证据链的门禁层**。

## 工作原理

一台引擎，两个入口：

```
                       ┌─────────────────────────────────────────┐
   论文（.md / .tex /   │              确定性引擎                  │
   尽力而为的 .pdf）     │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
   ┌────────────┐      │  │ 引文核验  │ │ 全文门禁  │ │ 报告输出  │ │
   │  MCP 服务器 ├─────┼─▶│ Crossref │ │ 文风·数字 │ │ 0-100 分  │ │
   │ (51 个工具)  │JSON │  │ S2/OpenAlex│ │ 统计·图表 │ │ +A/B/C   │ │
   └────────────┘      │  └────┬─────┘ └──────────┘ └──────────┘ │
   ┌────────────┐      │       │ 磁盘缓存                          │
   │    CLI     ├──────┼───────┘ 默认 24h（可调）                  │
   │ (人类/CI)   │      │  退出码 0 通过 · 1 门禁未过 · 2 输入错误  │
   └────────────┘      └─────────────────────────────────────────┘
```

1. **同一引擎，两处入口**。`scripts/paper_tools.py` 通过 Model Context Protocol 暴露 51 个工具（Cursor/Claude/Codex 等任何 MCP 客户端可用）；`scripts/cli.py` 为人类和 CI 脚本驱动完全相同的函数。两处行为零漂移。
2. **确定性规则，不靠感觉**。每道门禁都是可复现规则：同输入必得同结果，每条发现带可手工验证的行号。
3. **真实数据源 + 缓存**。`citation_verify` / `verify_references` / `lit_search` / `journal_search_openalex` 实时调用真实 API（Crossref、Semantic Scholar、OpenAlex），经磁盘缓存（默认 TTL 24h，`SCHOLARSEED_CACHE_TTL` 可调，`0` 关闭）。
4. **诚实降级**。无法可靠检查的项目（如 CID 编码的中文 PDF）会在报告中明确标注跳过，绝不硬猜。
5. **门禁就绪**。退出码 + `--fail-on` 阈值，任何检查都能当 CI 或智能体工作流里的硬门禁。
6. **插件形态**。遵循 Agent Plugins 1.0：把目录拖进客户端插件目录即自动发现技能与 MCP 服务器；`validate_plugin.py` 强制规范一致与版本单源。

## 写作流水线

五个技能把 51 个工具串成一条流水线（选题 → 文献 → 大纲 → 分章写作 → 引文核验 → 润色 → 投稿前评审 → 发表）。大模型负责写正文；技能在每一步强制调用工具门禁，不通过不得进入下一阶段：

| 流水线阶段 | 门禁工具 | 通过条件 |
|---|---|---|
| 文献调研 | `verify_references` | C 级（无法确认）条目必须补来源或删除 |
| 大纲与写作 | `render_template` / `word_count` / `word_budget` | 体裁结构齐全，分章词数达标 |
| 引文 | `format_citation` + `citation_verify` | 条目**只能**从已核验的 Crossref 元数据生成 |
| 润色 | `check_style` + `check_ai_signature` | 模板腔逐处重写为朴素学术表达 |
| 交付 | `proofread` / `audit_paper` | **ERROR 必须清零** |
| 诚信 | `check_stats` / `check_numbers` | 统计红线与分桶加和全部通过 |

每道门禁的机器输出原文件随稿提交作为证据——**禁止口头声称"已通过"而不附报告**。

## 写作自检，不是判决机器

两件 instruments 只服务于**打磨你自己的稿子**，都不自称法官：

- **`check_ai_signature` —— 文风自检（启发式提示）**。0-100 分刻画正文与典型 LLM 行文的相似度：句长突发性（CV）、MATTR 词汇丰富度、51 条模板短语（*underscores the importance、multifaceted nature…*，依据 Liang et al. 2024）、转折词开头、em-dash 密度。每条命中带行号；不足 8 句直接返回"样本过短"，绝不硬给分。用途是把模板腔段落改写成朴素文风——**是写作质量工具，不是检测器**。
- **`check_tamper_traces` —— 残留取证（客观事实）**。检测正文在工具处理与复制粘贴链路中可能沾染的不可见字符：零宽/不可见字符（U+200B/200C/200D/2060/FEFF、软连字符）、混入拉丁单词的西里尔/希腊同形字（`аpproach`；正常俄文/希腊文段落自动豁免）、行内异常空白串（RAID 基准攻击签名，Dugan et al., ACL 2024）。发现痕迹只说明文本被非常规工具处理过——**不证明谁写的**。

我们拒绝输出单一"AI 率 XX%"判决——那个数字在科学上站不住（Stanford 实测七个检测器对非英语母语写作者误报率 61.3%，Liang et al., *Patterns* 2023；Weber-Wulff et al. 2023 多机构测试无一工具准确率超 80%）。对刻意规避文体的检出率同样**未测、不宣称**——实测数据见 [docs/CAPABILITY-ASSESSMENT.md](docs/CAPABILITY-ASSESSMENT.md)。

> 完整方法论与行业全景：[docs/AI-DETECTION-LANDSCAPE.md](docs/AI-DETECTION-LANDSCAPE.md)

## 快速体验

把稿子交给 `audit_paper`，几秒拿到全量体检报告：

```markdown
# 论文全量审计报告（audit_paper）

审计总分：**85 / 100**

ERROR 0 · WARNING 5 · INFO 3　|　AI 相似度 41/100（中档）　|　体裁 [empirical]

- [WARNING] 'p=0.000' 应写作 p<0.001
- [WARNING] 文献 [2] 未在正文中被引用
- [WARNING] 分桶加和 180 + 200 = 380，超出总样本口径 300
- [INFO] 绝对化表述 '显然'——确认有直接证据支撑
```

引文门禁，实时调 Crossref API：

```
$ python scripts/cli.py citation 10.1038/nature14539
grade=A  "Deep learning"（Nature, 2015）        ← 真实论文，字段匹配
$ python scripts/cli.py citation 10.1234/fake.journal.2026
grade=C  HTTP 404: Not Found                    ← 编造的 DOI 被拦下
```

## 场景：该跑哪个？

**研究生交学位论文**
```bash
python scripts/cli.py project ./thesis-chapters     # 合并分章、跨章审计
python scripts/cli.py verify-refs thesis.md --fail-on C   # 不留一条未核验引用
python scripts/cli.py proofread thesis.md           # 全文门禁扫描
```

**准备期刊投稿**
```bash
python scripts/cli.py audit-paper paper.md --genre empirical --journal top_empirical
python scripts/cli.py format-citation 10.1038/nature14539 --style gbt   # 只从已核验元数据生成条目
python scripts/cli.py check abstract paper.md        # 摘要四要素覆盖
```

**课题组/CI 交付门禁**
```yaml
- name: Citation gate
  run: python scripts/cli.py verify-refs paper.md --fail-on B   # 退出码 1 卡住 PR
```

**润色 AI 辅助的初稿**
```bash
python scripts/cli.py check style draft.md          # 定位模板腔，逐处手改
python scripts/cli.py check tamper draft.md         # 确认无不可见字符残留
```

端到端流水线（选题 → 投稿）：使用内置技能 `literature-search` → `paper-writing` → `paper-review` → `paper-publish`，每步调用 MCP 工具过门禁。

## 核心能力

- **引文存在性核验**（`citation_verify`）：实时 Crossref 查询，DOI 精确匹配优先、标题相似度阈值防误配，提供作者/年份时做字段级交叉验证，A/B/C 分级与文献清单口径一致。
- **批量文献门禁**（`verify_references`）：逐条 DOI 优先、标题回退；Markdown 汇总报告含 A/B/C 统计。交付/投稿前的强制门禁。
- **真实文献检索**（`lit_search`）：Semantic Scholar API，限流自动退避重试；可选 `SEMANTIC_SCHOLAR_API_KEY` 提升配额。
- **期刊实时检索**（`journal_search_openalex`）：OpenAlex API 全学科期刊检索——刊名、出版商、发文量、被引、h 指数、ISSN、OA 状态。
- **内置期刊匹配**（`journal_matcher`）：精选 20 本期刊库（管理/信息系统/AI/医学/伦理），存于可编辑的 `data/journals.json`。
- **确定性写作工具**：模板渲染带篇幅规划、词数统计、标题结构校验、大纲生成、文献与投稿清单。
- **技能知识库**：把工具串成流水线并强制门禁的五项技能。

## 五项技能

| 技能 | 职责 |
|------|------|
| `paper-writing` | **流水线编排器**：选题 → 文献 → 大纲 → 分章写作 → 图表 → 引文核验 → 润色 → 自检，每阶段强制工具门禁，交付附证据链 |
| `literature-search` | 多库检索策略、PRISMA 式筛选、引文交叉验证、引文膨胀审计 |
| `paper-review` | 投稿前评审：挑剔审稿人 + 文字编辑双视角、claim-evidence 对齐、审稿人 10 问、Red-team 压测、BLOCKER/WARNING/OK 报告 |
| `paper-card` | 深读单篇文献，产出 16 节结构化证据卡（问题 → 方法 → 证据链 → 结论边界 → 批判） |
| `paper-publish` | 平台适配与投稿全流程：元信息、投稿信、伦理合规、修回处理 |

## MCP 工具

**实时核验与检索**

| 工具 | 说明 |
|------|------|
| `citation_verify` | Crossref 存在性核验：DOI 精确匹配或标题检索（相似度阈值防误配）；字段交叉验证；A/B/C 分级 |
| `verify_references` | **批量文献核验**：逐条 DOI 优先 + 标题回退；Markdown 汇总报告含 A/B/C 统计。交付/投稿前强制门禁 |
| `check_retraction` | **撤稿筛查（联网）**：逐条查被引文献撤稿状态（Crossref update-to / relation 记录与撤稿声明标题）——引用撤稿成果为 error；网络失败按 X 级纪律永不触发门禁 |
| `check_claim_citation_fit` | **引证契合（联网）**：强主张句与所引文献标题/摘要的词汇重叠率比对，过低提示人工复核（warning，非判决） |
| `check_version_mismatch` | **预印本-正式版错配（联网）**：arXiv 引用条目按标题在 Crossref 检索正式发表版，命中即提示更新引用（warning） |
| `format_citation` | **引用条目格式化**：经 Crossref 核验后输出 APA 7 / GB-T 7714 / IEEE / MLA 9 / Chicago / BibTeX 条目；未核验不出条目（防幻觉门禁） |
| `lit_search` | Semantic Scholar 论文检索：标题/作者/年份/摘要/被引/DOI |
| `journal_search_openalex` | OpenAlex 全学科期刊实时检索 |
| `literature_checklist` | 逐条文献核验清单（A/B/C 分级、DOI 状态） |
| `journal_matcher` | 按主题关键词与论文类型的期刊启发式推荐 |

**全文门禁**

| 工具 | 说明 |
|------|------|
| `check_encoding` | **编码健康（文件底座）**：U+FFFD 替换符与 (cid:N) PDF 提取残留（error，文本不可读）、UTF-8 被 Latin-1 误读的乱码特征、异常控制字符、文中部 BOM |
| `check_ethics_statements` | **合法前提声明**：伦理/知情同意、利益冲突、AI 使用披露（AIGC 合规）、数据可用性声明的存在性；涉人研究缺伦理声明为 error |
| `check_symbol_consistency` | **一符一义**：从定义句建符号→含义映射，同一符号两种含义=error，同一含义多符号=warning（希腊字符与 LaTeX 宏名归一化互认） |
| `check_abstract_promises` | **摘要承诺兑现**：摘要提出的方法/框架（we propose / 本研究提出）须在正文再出现，零词元命中才告警（宽松阈值防误报） |
| `check_rigor_declarations` | **方法严谨声明完备性**（实证/学位体裁）：正态性、多重比较校正、效能/样本量、随机盲法、缺失数据——触发场景下核对声明在场 |
| `check_anonymization` | **盲审匿名化**（需 `blind=true`）：致谢/基金、自引指涉、LaTeX uthor 与 frontmatter 身份字段（error）、本机路径（info）；'已隐去'标注行豁免 |
| `check_units` | **计量单位写法一致性**：同族单位混用（ml/mL、ug/µg、℃/°C），µ 的两码位与 u 代写归同族，数字-单位空格风格（warning） |
| `check_style` | 文风门禁：AI 高频词、口语化、填充短语、夸大表述、超长段句（含行号） |
| `check_punctuation` | 标点：中英文半全角混用（忽略代码块） |
| `check_figures_tables` | 图表完整性：编号断层、题注 ↔ 正文引用失配 |
| `check_terms` | 术语：未定义缩写、定义未使用、变体不一致；常用缩写豁免 |
| `check_duplicates` | 重复：归一化后完全相同的句子多次出现 |
| `check_references_format` | 参考文献格式：重复条目、未来年份（幻觉信号）、APA/GB-T/IEEE 混用 |
| `check_intext_citations` | **正文引用 ↔ 文献表双向核对**：数字式 [1]/[2,5]/[3-7]（幽灵引用/孤立条目/重号）、作者-年份式匹配、风格混用告警 |
| `check_sections` | 体裁感知的必备章节完整性 + 关键词行 |
| `check_numbers` | **数字一致性引擎**：同关键词样本口径矛盾、互斥分桶加和越界（"其中…另外…"）、百分比加和越界、占比>100%——经典造假信号 |
| `check_hedging` | 分章节断言强度画像：绝对化表述 vs 对冲；密集无对冲章节标警 |
| `check_stats` | **统计报告红线**：每个 p 值附近应有检验名、越界与 p=0.000 改写、显著结论需效应量+CI |
| `check_abstract` | **摘要四要素**：目的/方法/结果/结论覆盖、篇幅区间、实证论文量化数字 |
| `check_title` | **标题质量**：长度区间、空泛措辞、全大写惯例、问句与副标题提示 |
| `check_structure` | 标题层级连续性校验（忽略围栏代码块） |
| `word_count` | 剥离 Markdown 后的中文字符/英文单词/代码块统计；正文口径（不含参考文献） |

**自检 instruments**

| 工具 | 说明 |
|------|------|
| `check_ai_signature` | **AI 腔文风自检**：句长突发性、MATTR 词汇丰富度、51 条模板短语密度、转折开头、em-dash 密度 → 0-100 分 + 逐条证据（启发式提示，过短拒评） |
| `check_tamper_traces` | **防篡改痕迹取证**：零宽/不可见字符、拉丁单词内的西里尔/希腊同形字（正常俄/希段落自动豁免）、行内异常空白——客观处理残留证据，绝不做文风判决 |
| `check_self_plagiarism` | **跨文档自我重复**：对历史稿件目录（.md/.txt/.tex）做 n-gram 重叠检测——学位论文章节复用、系列论文模板句场景。合法复用也会命中，需人工判断 |

**复合审计与脚手架**

| 工具 | 说明 |
|------|------|
| `proofread` | **复合门禁入口**：全部检查器 + 结构校验，一份 ERROR/WARNING/INFO 报告（`format=json` 出结构化结果） |
| `audit_paper` | **一键全量审计**：全部检查器 + 文风自检 + 残留取证 + 章节完整性 + 统计红线 + 可选词数预算 → 启发式总分（0-100）；`brief=true` 返回仅含 ERROR 的紧凑判定，适配智能体循环 |
| `audit_project` | **多文件学位论文审计**：自然序合并分章 → 分章词数表 + 合并后全门禁（跨章缩写、整句自重复、引文交叉核对） |
| `audit_pdf` | **PDF 投稿审计（尽力而为）**：纯标准库文本抽取 + 文风/重复/对冲/数字/统计子集；不可靠检查项如实标注跳过 |
| `render_template` | 按体裁的 Markdown 模板（综述/实证/技术/学位/思辨），可选期刊篇幅规划 |
| `generate_outline` | 按体裁生成结构化大纲 |
| `word_budget` | 分章词数对照期刊篇幅目标（与 render_template 同源） |
| `submission_checklist` | 投稿前清单（期刊匹配、ICMJE 署名、投稿信、伦理与 AI 披露） |
| `next_actions` | **智能体计划路由**：按目标（submission/thesis/polish）返回有序 JSON 行动计划——每步含 工具/参数模板/通过条件，智能体按步推进流水线 |
| `gate_suite` | **组合门禁套件**：一次调用运行全部（或选定）离线确定性检查器，统一 JSON 判定（pass=ERROR 为零）+ blocking 清单——智能体"修复→重跑"循环的原语 |
| `audit_delta` | **修复增量对比**：修改前后两版跑同一门禁束，报告 已修复/新引入/仍存在 与净改善判定 |
| `check_references_completeness` | **文献完整性**：逐条查缺年份/缺来源/缺卷期页、中文条目缺 GB/T 7714 类型标识、DOI 语法异常（注册符长度/含空格/标点截断） |
| `check_references_recency` | **文献时效性**：中位文献年龄与过时占比，全部或七成以上早于 10 年即提示综述陈旧 |
| `check_placeholders` | **未完成痕迹**：TODO / FIXME / ??? / [citation needed] / 待补充——交付前必须清零 |
| `check_links` | **链接可信**：离线查占位域名（example.com/localhost）、非法 TLD、无主机名；`live=true` 逐个 HEAD 验活（404/410 死链） |
| `check_vague_attribution` | **模糊归因**：句子向不具名的"研究表明/experts say/人们普遍认为"借权威却同句无任何引注——AI 文本"光润但空洞"的核心特征；同句有引注即豁免 |

LaTeX 支持：word_count / check_structure / proofread / audit_paper 接受 `source_format=latex`——剥离命令/数学/注释并还原章节结构。

所有外部 API 调用经磁盘缓存（默认 TTL 24h，`SCHOLARSEED_CACHE_TTL` 可调，`0` 关闭）。

## 语料基准

门禁阈值经 **70 篇 × 9 学科 arXiv 真实论文**校准：70/70 全部落入文风自检低档（人类语料零误报），审计分中位 82、分布健康。如实说明：**这是仅有负样本的基准**——对 AI 代写正样本的检出率尚未测量（已列入路线图，见 [docs/ROADMAP.md](docs/ROADMAP.md)）。详见 [docs/CORPUS-BENCHMARK.md](docs/CORPUS-BENCHMARK.md)。

## 安装

1. 把本目录拖进客户端的插件目录。
2. 重启客户端；`skills/` 下的技能与 `mcp.json` 里的 MCP 服务器自动发现。
3. 验证：`python scripts/validate_plugin.py` 输出 `PASS`。

无需 pip、无需虚拟环境、无编译扩展——能跑 `python` 就能跑 ScholarSeed。

### 仓库

| 平台 | 地址 | 说明 |
|------|------|------|
| GitHub | <https://github.com/Morningstar202604/ScholarSeed> | 主线开发；在此提 Issue/PR |

## CLI（无需智能体）

与 MCP 服务器同一引擎，供人类与 CI 管道使用：

```bash
python scripts/cli.py version
python scripts/cli.py proofread paper.md --genre empirical
python scripts/cli.py verify-refs paper.md --fail-on C   # CI 门禁：存在未核验引用则退出码 1
python scripts/cli.py citation 10.1038/nature14539 --style gbt
python scripts/cli.py check abstract paper.md            # 单项门禁：style/numbers/stats/tamper/…
python scripts/cli.py project ./thesis-chapters          # 多文件学位论文审计
```

退出码：`0` 通过 · `1` 门禁未过（`--fail-on`）· `2` 输入错误。零依赖。

## 文档索引

| 文档 | 内容 |
|------|------|
| [CORPUS-BENCHMARK](docs/CORPUS-BENCHMARK.md) | 70 篇真实论文的阈值校准；防过拟合规则 |
| [CAPABILITY-ASSESSMENT](docs/CAPABILITY-ASSESSMENT.md) | 实测能力、对抗探针、升级路径 |
| [AI-DETECTION-LANDSCAPE](docs/AI-DETECTION-LANDSCAPE.md) | 学术界与产业界检测全景；什么能信、什么不能信 |
| [VERSIONING](docs/VERSIONING.md) | SemVer 规范、版本单源、发布纪律 |
| [SECURITY](SECURITY.md) | 威胁模型、凭据策略 |
| [CHANGELOG](CHANGELOG.md) | 重要变更记录 |

## FAQ

**这是 AI 写作助手吗？**
它是围绕 AI 辅助写作的**质量门禁层**。内置技能把任何大模型编排进写作流水线；ScholarSeed 自己的 51 个工具从不生成正文——只做核验、门禁与证据留档。

**它是 GPTZero 那样的 AI 检测器吗？**
不是。它提供**文风自检**（润色自己的稿子）与**残留取证**（客观的处理痕迹）。拒绝输出单一"AI 率"判决——那个数字科学上站不住，且对规避文体的检出率未测（见[为什么需要 ScholarSeed](#为什么需要-scholarseed)）。

**能证明一条文献不存在吗？**
它实时对 Crossref/Semantic Scholar 核验存在性并给 A/B/C 分级。C 级 = "无法确认"，这正是应当在解决前拦下投稿的信号。

**会把我的论文传到别处吗？**
核验时只有文献标题/DOI 会发往公开学术 API，且经本地磁盘缓存。全文检查完全离线。

**支持什么语言？**
中英双语一等公民（词典全覆盖）；LaTeX 与 Markdown 是一等输入格式；PDF 抽取尽力而为。

**为什么零依赖？**
让它跑在任何有 Python 的机器上——实验室服务器、学生笔记本、物理隔离的评审环境、CI 容器——没有会坏的东西，需要审计的也只有我们的代码。

**怎么相信启发式不是拍脑袋调的？**
阈值只能伴随语料级回归重跑才能调整（CORPUS-BENCHMARK.md 的防过拟合规则），由 306 个单元测试和 CI（Python 3.9–3.13）发布门禁强制执行。

## 兼容客户端

支持 Agent Plugins 1.0 规范的客户端均可使用：ChatGPT、Codex、Cursor、GitHub Copilot、Kiro、VS Code 等。

### 范围与局限

- **输入格式**：Markdown / LaTeX 源码是一等输入；PDF 抽取尽力而为，不支持 CID 编码的中文 PDF——中文论文请提供 Markdown/LaTeX 源。
- **结论性质**：全文门禁是确定性启发式——供人工复核的提示，不是判决。引文工具（`citation_verify`/`verify_references`）返回真实 API 结果，可直接作为交付门禁。
- **文风自检的检出力**：统计画像能抓典型 LLM 行文；刻意规避的文本可以过关——低分只代表"没发现明显模板腔"，不是"人写"的证明。
- **不代投稿**：不对接期刊投稿系统；投稿由作者本人执行。

## 开发

```bash
python scripts/validate_plugin.py        # 插件规范校验
python -m unittest discover -s tests -v  # 单元测试（306）
python benchmarks/adversarial_suite.py   # 对抗回归（RAID 风格攻击）
python scripts/release_gate.py           # 发布门禁（校验 + 测试）
```

CI 经 GitHub Actions 在 Python 3.9–3.13 上跑发布门禁（push 与 PR 都跑，GitHub 为唯一平台——一条流水线，无平台特有副本可漂移）。

## 安全

不内置任何凭据。真实投稿需要你自己的平台账号/API key。Agent Plugins 1.0 未定义权限模型或沙箱——安装第三方插件前请先审查。见 [SECURITY.md](SECURITY.md)。

## 许可证

[PolyForm Noncommercial 1.0.0](LICENSE) © 2026 ScholarSeed contributors——学习、研究与个人使用免费；商用需向维护者另行获取授权。

## 支持

如果 ScholarSeed 帮你省下了查文献、校对稿子的时间，点一下下面的按钮，让更多研究者看到它：

<div align="center">

[![Star ScholarSeed](https://img.shields.io/badge/%E2%AD%90_%E7%82%B9%E4%B8%AA_Star-FBBA00?style=for-the-badge)](https://github.com/Morningstar202604/ScholarSeed/stargazers)
[![提交问题](https://img.shields.io/badge/%F0%9F%90%9B_%E6%8F%90%E4%BA%A4%E9%97%AE%E9%A2%98-2EA043?style=for-the-badge)](https://github.com/Morningstar202604/ScholarSeed/issues)
[![参与贡献](https://img.shields.io/badge/%F0%9F%8D%B4_%E5%8F%82%E4%B8%8E%E8%B4%A1%E7%8C%AE-0969DA?style=for-the-badge)](CONTRIBUTING.md)

[![Star History Chart](https://api.star-history.com/svg?repos=Morningstar202604/ScholarSeed&type=Date)](https://star-history.com/#Morningstar202604/ScholarSeed&Date)

</div>

## 内容声明（AIGC）

<details>
<summary>生成内容标识信息（点击展开）</summary>

```yaml
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_35986ede9be611f1a98a525400f8a581
    ReservedCode1: S1LeLyLaqHjXW/Jto+Um5gSrm3eXn8FMGlaq12Cbveim2zG0Q/Uvyl/OvmV/WLqMfb6dM/OFJIOd3GA93NU+lD0jVBAoDBq4l6FJFrYmb8zUD4DiXyS2oZvKF+zVV34SEmfWF0ch0xYe1FWL04tbF2PEmANJfMpN5yej2VA8WM5/M6p/IlVfX+gfC9Q=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_35986ede9be611f1a98a525400f8a581
    ReservedCode2: S1LeLyLaqHjXW/Jto+Um5gSrm3eXn8FMGlaq12Cbveim2zG0Q/Uvyl/OvmV/WLqMfb6dM/OFJIOd3GA93NU+lD0jVBAoDBq4l6FJFrYmb8zUD4DiXyS2oZvKF+zVV34SEmfWF0ch0xYe1FWL04tbF2PEmANJfMpN5yej2VA8WM5/M6p/IlVfX+gfC9Q=
```

</details>
