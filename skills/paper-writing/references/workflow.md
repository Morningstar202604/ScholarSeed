# 论文生产流水线（workflow）

> 目标：把「定目标期刊 → 定词数 → 分章写 → 逐章核文献 → 成稿校验 → 投稿清单」串成一条固定流水线，杜绝"定稿后发现期刊不匹配整篇重写"的返工。本指南与 `SKILL.md` 各阶段一一对应，写作全程按此推进。

## 流水线总览

| 步骤 | 动作 | 调用的 paper-tools | 对应 SKILL.md 阶段 | 产出物 / 门禁 |
|------|------|--------------------|--------------------|---------------|
| 0 | 定目标期刊 | `journal_matcher`（内置库无覆盖时 `journal_search_openalex` 实时搜刊） | 阶段 0 需求澄清 + 阶段 1 选题 | 《候选期刊 TOP3 + 五维评估》 |
| 1 | 定词数 | `render_template(journal=...)` | 阶段 0 / 阶段 7 排版 | 全篇 + 分章词数规划 |
| 2 | 分章写 | `word_count`（进度校验）+ `word_budget`（对照期刊分章目标） | 阶段 4 分章写作 | 逐章落盘的成稿 |
| 3 | 逐章核文献 | `literature_checklist` + `format_citation`（生成规范条目）+ `citation_verify` + `verify_references` | 阶段 6 引用核验 | 《文献核验清单》+ DOI 三重核对 + 批量核验无 C 级 |
| 4 | 成稿校验 | `proofread` + `audit_paper`（AI 画像/章节完整性/统计诚信）+ `check_abstract` + `check_title` | 阶段 8 质量自检 | 校对报告 ERROR 清零 + 自检表（claim-evidence/10 问/Red-team） |
| 5 | 投稿清单 | `submission_checklist` | paper-publish 全部 | 投稿前检查清单 |

学位论文等多文件工程：以 `audit_project(project_dir=...)` 替代单文件校验入口，其余步骤不变。

**关键约束：步骤 0、1 必须在动笔前完成并确认，之后不得中途更换目标期刊或词数基准。** 若中途确需变更，必须回到步骤 0 重新评估并书面记录影响面，禁止"先写再看投哪"。

## 步骤 0：定目标期刊（动笔前）

- 用 `journal_matcher(topic=..., paper_type=...)` 按主题与体裁（conceptual/empirical/review）获取候选期刊与匹配度。
- 对 TOP3 逐一做五维评估（主题契合 / 期刊层次 / 读者群 / 周期成本 / 录用可行性），依据 `../paper-publish/references/journal-matching.md`。
- 锁定**唯一优先期刊**，记录其《作者指南》关键约束：字数上限、结构要求、引文格式、是否收 APC、预印本政策。
- 门禁：未锁定目标期刊前，禁止进入步骤 2 动笔。

## 步骤 1：定词数（动笔前）

- 用 `render_template(genre=..., journal="top_conceptual"|"top_empirical"|"general")` 获取目标篇幅规划（全篇 + 分章词数）。
- **词数口径（全局统一）**：一切词数报告均指**正文词数，不含参考文献、不含图表占位**。统计方法：将全文截取到 `## References` 或 `## 参考文献` 之前，再交给 `word_count` 统计；报告中必须标注"不含参考文献"。
- 门禁：全篇词数目标与各章词数目标确认后，写入成稿头部备注，之后按此基准写。

## 步骤 2：分章写（阶段 4）

- 按大纲逐章写、逐章落盘，避免上下文漂移；每章写完用 `word_count` 对照该章词数目标校验进度，落后/超额即调整详略。
- 写作要求与"教授改写 → 审稿人批注"视角自查，遵循 `SKILL.md` 阶段 4 与 `../paper-writing/references/pitfalls-and-landmines.md`。
- 含公式推导的章节同步遵循 `../paper-writing/references/equations-symbols.md`：先定义后使用、一符一义、编号纪律——符号漂移与公式错误在成稿期返工成本最高，随章写随核。

## 步骤 3：逐章核文献（阶段 6）

- 参考文献段落地后立即调用 `literature_checklist(markdown=全文)` 生成逐条核验清单，不得留到投稿前。
- **条目生成**：有 DOI 的条目用 `format_citation(doi=..., style=目标格式)` 直接产出规范引用（真实 Crossref 元数据），避免手打漂移；未核验通过（C 级）时工具拒绝产出，正是防幻觉门禁的一部分。
- 用 `verify_references(markdown=全文)` 做批量真实性核验（Crossref 实时，DOI 优先/标题回退）：报告 A/B/C 统计，**C 级（含未来年份、未命中）必须补来源或删除，禁止以当前形态进入文献表**。
- 对清单中每条含 DOI 的文献执行 **DOI 三重核对**（详见 `citation-guide.md`）：
  1. **可解析**：DOI 能解析打开到目标页面；
  2. **卷期页码匹配**：与 Crossref 元数据一致（警惕张冠李戴）；
  3. **作者年份匹配**：作者与年份对应正确（警惕同名多篇、预印本/书章节混淆）。
- 分级写入核验结果：A=直接命中完整出处；B=真实存在但细节待核实；C=无证据须补来源。**B、C 级禁止直接进文献表，必须核实到 A 级。**
- 门禁：`verify_references` 报告无 C 级且所有引用条目标记 A 级并一一对应后，方可进入步骤 4。

## 步骤 4：成稿校验（阶段 8）

- `proofread(markdown=全文)`：一键运行全部规则检查器（文风 AI 词/口语化/超长段句 + 中英标点混用 + 图表编号与引用对应 + 缩写定义一致性 + 句子重复 + 数字一致性 + 断言对冲），输出 ERROR/WARNING/INFO 汇总报告。
- `audit_paper(markdown=全文, genre=..., journal=...)`：一键全量审计——在 proofread 之上叠加 **AI 痕迹画像**（0-100 相似度分）、**章节完整性**（按体裁查必备章节与关键词行）、**统计诚信红线**、**词数预算对照**，输出启发式总分留档。
- 摘要专项：`check_abstract(markdown=全文)` 查结构化四要素（目的/方法/结果/结论）覆盖、篇幅带、实证含量化数字；标题专项：`check_title(markdown=全文)` 查长度带与空泛措辞。二者是审稿人第一眼，投稿前必过。
- **门禁分级处理**：ERROR 项（图表幽灵引用、未来年份、格式混用等）必须清零；WARNING 项逐条复核后修复或在自检表说明保留理由。**清零的正道是修复内容，严禁通过删除证据段落/整节裁剪来"消灭"报错绕过门禁**——确需删减结构时回到步骤 1 重新评估词数与大纲。
- 需要单项复查时调用对应检查器：`check_style` / `check_punctuation` / `check_figures_tables` / `check_terms` / `check_duplicates` / `check_references_format` / `check_numbers` / `check_hedging` / `check_stats` / `check_ai_signature`；章节完整性单独用 `check_sections(markdown=全文, genre=体裁)` 复核。
- **跨范式稿件先读 `../paper-writing/references/discipline-matrix.md`**：质性/人文稿件按矩阵裁剪统计类与 AI 画像门禁（裁剪项写入自检表），不得机械套用定量口径。
- `check_structure(markdown=全文)`：标题层级连续无跳级。
- `word_count(截取到 References 前的正文)` 或 `word_budget(markdown=全文, journal=...)`：对照步骤 1 的基准确认达标，报告注明"不含参考文献"。
- 执行 `SKILL.md` 阶段 8 全套自检：claim-evidence 对齐、审稿人 10 问、Red-team 压力测试、学术不端红线自查。
- 门禁：proofread 无 ERROR 且自检表无 BLOCKER 项后，方可进入步骤 5。

## 步骤 5：投稿清单（交付）

- 用 `submission_checklist(journal=目标期刊, topic=主题)` 生成投稿前检查清单，逐项勾选。
- 需要投稿信时依据 `../paper-publish/references/cover-letter.md` 生成 Cover Letter。
- 交付物：成稿（含词数口径备注）+ 文献核验清单 + 自检表 + 投稿清单。

## 冲突处理

- 步骤 2 写作中发现篇幅、结构或论点与目标期刊冲突 → 回到步骤 0/1 复核，书面记录变更，禁止静默改口径。
- 文献核验发现引用错误 → 立即修正文献表与正文引用，不遗留到投稿前。

## 门禁证据链（约束 Agent 与自证）

- 每个带"门禁"二字的步骤，其机器输出**原文**（`verify_references` 报告、`proofread` 报告、`audit_paper` 总分与分级、自检表）必须作为交付物随稿提交——口头声称"已通过、无 ERROR"而附不出报告原文，视同未通过。
- 最终答复末尾附**门禁摘要**：各门禁一行结论（工具名 + 关键数字，如 "verify_references: A=12 B=0 C=0"）。
- 工具不可达降级：MCP Server 未加载或外部 API 失败时，按对应 references 手工协议执行，交付物中如实标注"该项未经程序化核验"，禁止假装已机检；恢复可达后补跑。
