# ScholarSeed 门禁塔架构（Gate Tower Architecture）

> 版本：v0.7.0 · 日期：2026-09-05 · 地位：**全部检查器与工具的归位图纸**
> 原则重申：核心永远零依赖（stdlib-only）、启发式永远是提示而非判决、每道门禁输出随稿留档。

---

## 一、为什么需要这张图纸

ScholarSeed 的工具在 v0.x 快速迭代中按"实测暴露缺陷 → 补一个检查器"逐个长出，每个工具
出生时都有充分依据，但 41 个工具彼时是**清单而非体系**：菜单式分组无法回答"新想法该不该
进来、进到哪、证据等级是什么、能不能拦门禁"。本文档把"生成与验证分离"的底层哲学向下
延伸三层，形成一座可推导、可归位、可拒绝的**门禁塔**——此后任何新工具必须先在塔中
找到唯一归属，答不出归属的就不准入。

## 二、推导链：从第一性原理到九层塔

一篇论文能交付，本质是**审稿人与编辑部能信任它的主张（claims）**。信任是分层成立的：

> 主张可信任 ⇐ 主张引用的东西**存在** ⇐ 存在的东西**支撑该主张** ⇐ 稿件**内部自洽**
> ⇐ 方法**交代严谨** ⇐ 格式**符合出口规范** ⇐ 表达**清晰得体**
> ——而这一切成立的前提是：稿件有**投稿资格**，且文件本身**完整可解析**。

沿这条推导链自底向上展开，得到九层塔 + 两个纵向支柱：

```
                          ┌─────────────────────────────┐
                          │   V 裁决引擎（纵向聚合）       │
                          │  gate_suite / audit / delta  │
   S 源与脚手架面 ⇄  ┌─────┴─────────────────────────────┴──────┐
   （写作侧对应物）   │  L6 表达   写得润吗？（永不门禁）              │
                     │  L5 规范   符合出口规矩吗？（可配置门禁）        │
                     │  L4 方法   方法交代严谨吗？（可配置门禁）        │
                     │  L3 一致   稿件跟自己打架吗？（硬门禁）         │
                     │  L2 契约   引的东西支撑你的话吗？（准门禁）      │
                     │  L1 存在   引的东西存在吗？（硬门禁，联网）      │
                     │  L0 底座   文件完整可解析吗？（硬门禁）         │
                     │  P  前提   稿件有投稿资格吗？（硬门禁）         │
                     └──────────────────────────────────────────┘
                          A 取证支柱（客观痕迹，独立附件，不进质量分）
```

**证据等级随层升高而递减**：P/L0/L1/L3 是可机械验证的事实（外部 API 事实、文件事实、
内部矛盾事实），L2 是"事实+启发"，L4/L5 是社区约定，L6 是统计启发。**门禁资格跟着证据
等级走**——这正是"hints-not-verdicts"立场的结构化表达：不是某些工具碰巧能拦门禁，而是
证据等级决定了谁能拦。

## 三、九层塔逐层定义

### P 合法前提层 —— "这稿子有资格投吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 伦理审批/知情同意、利益冲突披露、AI 使用披露（AIGC 合规）、数据可用性声明是否在场 |
| 证据等级 | 声明**存在性**（工具查"写了没有"；真实性归人） |
| 门禁资格 | 硬门禁（缺声明即挡：涉人类受试者而无伦理声明 = 桌拒级） |
| 现有工具 | `submission_checklist`（生成侧） |
| 工具 | **`check_ethics_statements`** |
| 诚实边界 | 工具只验声明在场且非空，不判断声明真伪 |

### L0 文件底座层 —— "文件本身完整可解析吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 编码损坏（乱码/U+FFFD/CID 残留）、控制字符、未完成痕迹、结构可解析性 |
| 证据等级 | 文件事实 |
| 门禁资格 | 硬门禁——底座坏了，上面所有层的行号证据都不可信 |
| 现有工具 | `check_structure`、`check_placeholders`、`audit_project`（合并）、`word_count` |
| 新工具 | **`check_encoding`** |
| 说明 | `PaperIR`（scripts/paper_ir.py）是本层的代码化地基：文档只解析一次成结构化模型（标题/摘要/章节树/句子流/围栏/文献段），共享行号辅助函数随迁于此 |

### L1 存在层 —— "引的东西存在吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 被引文献/链接/期刊是否真实存在；被引文献是否已被**撤稿** |
| 证据等级 | 外部 API 事实（Crossref/S2/OpenAlex，磁盘缓存） |
| 门禁资格 | 硬门禁（X 级"无法核验"永不触发） |
| 现有工具 | `citation_verify`、`verify_references`、`format_citation`、`check_links`（live） |
| 新工具 | **`check_retraction`**（Crossref update-to/relation + 标题特征） |
| 诚实边界 | 仅 DOI/标题级核验；基础设施失败一律 X 式降级，不计入失败 |

### L2 契合层 —— "引的东西支撑你的话吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 引文与主张的词汇契合度；预印本是否已有正式发表版 |
| 证据等级 | API 事实 + 词汇启发（半步事实） |
| 门禁资格 | 准门禁（warning 级，需人工复核，不默认拦门禁） |
| 现有工具 | `citation_verify` 的字段交叉核对（作者/年份） |
| 新工具 | **`check_claim_citation_fit`**、**`check_version_mismatch`** |
| 诚实边界 | "源文是否真支持该主张"的语义级判断需要 NLP 模型推理，划为**明确不做**（确定性工具定位）；本层只做词汇级契合提示 |

### L3 一致层 —— "稿件跟自己打架吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 正文↔文献表、图表↔题注、数字口径、术语变体、章节结构、**一符一义**、**摘要承诺↔正文兑现** |
| 证据等级 | 内部矛盾事实（纯离线可复现） |
| 门禁资格 | 硬门禁 |
| 现有工具 | `check_intext_citations`、`check_figures_tables`、`check_numbers`、`check_terms`、`check_duplicates`、`check_sections`、`check_references_completeness` |
| 新工具 | **`check_symbol_consistency`**、**`check_abstract_promises`** |

### L4 方法层 —— "研究方法交代严谨吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 统计方法**声明完备性**：正态性检验、多重比较校正、效能/样本量论证、随机盲法、缺失数据交代、文献新鲜度 |
| 证据等级 | 声明完备性（触发条件可检、声明在场可检） |
| 门禁资格 | 可配置门禁（warning 级） |
| 现有工具 | `check_stats`（报告格式红线）、`check_references_recency` |
| 新工具 | **`check_rigor_declarations`** |
| 诚实边界 | 工具查"声明了没有"，不判"方法选对了没有"——方法选择正确性归人工与领域规范 |

### L5 规范层 —— "符合出口的规矩吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | 参考文献格式、标点、标题/摘要/关键词规范、篇幅预算、**盲审匿名化**、**计量单位写法** |
| 证据等级 | 社区/期刊约定（随 genre/journal 变化） |
| 门禁资格 | 可配置门禁 |
| 现有工具 | `check_references_format`、`check_punctuation`、`check_title`、`check_abstract`、`word_budget` |
| 新工具 | **`check_anonymization`**（含 LaTeX/YAML 元数据泄漏；需显式 blind=true）、**`check_units`** |

### L6 表达层 —— "写得润吗"

| 项 | 内容 |
|---|---|
| 回答的问题 | AI 腔画像、模糊归因、口语化、绝对化与对冲、断言强度 |
| 证据等级 | 统计启发 |
| 门禁资格 | **永不门禁**（只提示） |
| 现有工具 | `check_style`、`check_hedging`、`check_ai_signature`、`check_vague_attribution` |
| 未来扩展 | 可读性画像独立输出（polish 与 ai-likeness 双轴解耦，见 ROADMAP Phase 1.1） |

### A 取证支柱（平行于塔，独立附件）

| 项 | 内容 |
|---|---|
| 回答的问题 | 文本被什么工具处理过（客观痕迹），不判断是否 AI 所写 |
| 现有工具 | `check_tamper_traces`、`check_self_plagiarism` |
| 新工具 | （盲审元数据泄漏并入 `check_anonymization`，避免近重复工具） |
| 门禁资格 | 独立附件报告，不进质量分 |

### V 裁决引擎（纵向聚合）与 S 源/脚手架面

- **V**：`gate_suite`（组合门禁）、`proofread`（校对报告）、`audit_paper`（全量审计）、
  `audit_delta`（修复增量）、`next_actions`（计划路由）、`audit_pdf`/`audit_project`（载体变体）。
  本版将 6 道新离线门禁纳入 `gate_suite` 注册表（19 → 25 道）；三入口合并为单一裁决函数
  属后续重构（见"演进路线"）。
- **S**：写作侧对应物与实时源。`render_template`/`generate_outline`/`word_budget`/`journal_matcher`/
  `literature_checklist`/`lit_search`/`journal_search_openalex`/`citation_verify`/`format_citation`/
  `submission_checklist`。**写作沿塔下行**（先定规范骨架，再填存在的内容），**审计沿塔上行**
  （先验最接近"造假"的底层，越往上越是提示）——同一座塔管写与验两头，这是体系连贯性的来源。

## 四、新工具准入测试（Admission Test，写进贡献纪律）

任何新工具提案必须能完整回答以下四问，答不出任何一问即拒绝：

1. **归属**：你站在塔的哪一层？（P/L0–L6/A；答不出 → 不准入）
2. **失败类型**：你检出的是什么性质的失败？（造假/幻觉/内部矛盾/声明缺失/违规约定/风格弱点/处理痕迹）
3. **证据等级**：你的结论是外部 API 事实、内部事实、约定比对，还是统计启发？
4. **门禁资格**：按证据等级，你是 error（拦）、warning（提示）、还是永不进质量分？

反例示范：'"AI 含量 %"判决器'——无归属层、证据等级是概率猜测、按项目哲学科学上不可辩护 →
三问皆败，拒绝（与 CAPABILITY-ASSESSMENT.md 的既有决策一致）。

## 五、全部工具归位表（v0.7.0，51 工具 + 25 离线门禁）

| 层 | 工具 | 新增 |
|---|---|---|
| P | submission_checklist、**check_ethics_statements** | ★ |
| L0 | check_structure、check_placeholders、word_count、**check_encoding**、PaperIR（内部模块） | ★ |
| L1 | citation_verify、verify_references、format_citation、check_links、**check_retraction** | ★ |
| L2 | （citation_verify 字段核对）、**check_claim_citation_fit**、**check_version_mismatch** | ★ |
| L3 | check_intext_citations、check_figures_tables、check_numbers、check_terms、check_duplicates、check_sections、check_references_completeness、**check_symbol_consistency**、**check_abstract_promises** | ★ |
| L4 | check_stats、check_references_recency、**check_rigor_declarations** | ★ |
| L5 | check_references_format、check_punctuation、check_title、check_abstract、word_budget、**check_anonymization**、**check_units** | ★ |
| L6 | check_style、check_hedging、check_ai_signature、check_vague_attribution | |
| A | check_tamper_traces、check_self_plagiarism | |
| V | gate_suite、proofread、audit_paper、audit_delta、next_actions、audit_pdf、audit_project | |
| S | render_template、generate_outline、literature_checklist、journal_matcher、lit_search、journal_search_openalex、submission_checklist（兼 P） | |

gate_suite 离线门禁注册表（25 道）：structure、style、punctuation、figures、terms、duplicates、
intext、references_format、references_completeness、references_recency、placeholders、links、
vague_attribution、numbers、stats、hedging、sections、abstract、title、
**encoding、ethics、symbol、abstract_promises、rigor、units**（★新增 6 道）。
联网核验类（verify_references / check_retraction / check_claim_citation_fit /
check_version_mismatch）与需显式参数的（check_anonymization）不进默认套件，单独调用。

## 六、诚实边界（本架构明确不做的事）

1. 语义级"源文是否支持主张"（需模型推理）——L2 只做词汇级契合提示；
2. 数据本身真伪、实验可复现性、图像篡改取证——文本工具能力之外，L4 只查声明完备性；
3. 任何"AI 含量 %"单一判决——哲学红线，三问皆败（见准入测试反例）；
4. 外部全网查重、爬取知网等侵权数据源——见 SECURITY.md 边界声明。

## 七、演进路线（与 ROADMAP.md 衔接）

1. ~~图纸~~（本文档，v0.7.0）；
2. ~~PaperIR 地基~~（v0.7.0：行号辅助函数集中迁移 + 文档模型，新工具优先接入）；
3. 存量 41 检查器逐步迁移到 PaperIR（行为不变，PATCH 级分批走，237+ 测试全绿为验收线）；
4. 三复合入口（proofread/audit_paper/gate_suite）收敛为单一分层裁决函数（MINOR，
   旧名留兼容别名，报告改为"塔分层体检表 + 按主张聚合证据链"）；
5. audit_paper 启发式总分改为"从分层结果推导 + 公开权重"或移除（消除与反黑箱哲学的自相矛盾）。
