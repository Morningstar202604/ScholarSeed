---
name: paper-writing
description: 论文写作流水线编排技能：把用户的论文需求按阶段推进为结构完整、论证扎实、格式合规的成稿，每个阶段强制调用确定性工具门禁（引用核验、统计红线、结构校验），门禁输出随稿留档构成交付证据链，不通过不得进入下一阶段。覆盖选题论证、文献调研、大纲、分章写作、图表制作、语言润色、引用核验、排版、质量自检的端到端流程。
---

<!--
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_f7a5b3959ba611f1a98a525400f8a581
    ReservedCode1: R+WBmXs+qCsmcj+MCr6UM3J82hqswwYi+5DN2K7VGrVwaQCddLpL56FtYvtVYDtMvTSOMqWtRn21ICqwWrMmEkTBFK9lw8yRHNq6F5WZn7VRygI1IIauz0YeM3q49a7QTXAnZArZFMTq7ERaTp3bZBd/MvMjgzp91GjLba14Ne2PPxuXnKK2dzVEeUc=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_f7a5b3959ba611f1a98a525400f8a581
    ReservedCode2: R+WBmXs+qCsmcj+MCr6UM3J82hqswwYi+5DN2K7VGrVwaQCddLpL56FtYvtVYDtMvTSOMqWtRn21ICqwWrMmEkTBFK9lw8yRHNq6F5WZn7VRygI1IIauz0YeM3q49a7QTXAnZArZFMTq7ERaTp3bZBd/MvMjgzp91GjLba14Ne2PPxuXnKK2dzVEeUc=
-->

# paper-writing：论文写作流水线

## 目标

把用户的论文需求按流水线阶段推进为一篇结构完整、论证扎实、格式合规的成稿。分工原则：**大模型负责写作，确定性工具负责放行**——所有阶段按门禁顺序推进，只有关键决策（题目方向、篇幅、目标期刊/平台）回问用户；每道门禁的机器输出随稿留档，构成交付证据链。

## 输入

- 主题 / 方向 / 一句话需求
- （可选）目标期刊或平台、篇幅要求、语言（默认中文）、截止时间、参考资料

## 贯穿性参考（教授级知识库，各阶段按需调用）

以下 references 是"只有教授/编辑/过来人才知道"的知识，所有阶段写作与判断都必须自觉引用：

- `references/pitfalls-and-landmines.md`：论文写作 18 大坑 + 审稿人隐性雷区 + 编辑视角十五误区。选题/标题/摘要/引文/降重/数据/英文写作各环节对照避坑。
- `references/exemplar-papers.md`：神稿与范文库。范式结构对照（IMRaD + 学科差异）、范文获取渠道、拆解模仿四法、学生版 vs 教授版 vs 审稿人批注的"角色模拟神稿"。
- `references/contingency-plans.md`：启动前建议、写作节奏、中途中断续写、验证失败/实验失败的 Plan A-E、阴性结果期刊、拒稿改投策略。
- `references/workflow.md`：**论文生产流水线**——「定目标期刊 → 定词数 → 分章写 → 逐章核文献 → 成稿校验 → 投稿清单」六步流程、每步调用的 paper-tools、产出物与门禁。本技能执行流程即此流水线的展开。
- `references/thinking-protocol.md`：**思维协议**（集成 superpowers brainstorming 三路径）。阶段 0-1 动笔前必读：先分类（Spike/Bounded/Architectural）、逐问澄清、先设计后动笔、给方案带取舍。防止在错误方向上写完大纲。
- `references/top-conference-writing.md`：**顶会顶刊写作哲学**（集成 ARS）。叙事三支柱、Gopen & Swan 句子清晰七原则、引文绝不幻觉、审稿人实际阅读行为、写作时间分配。面向 NeurIPS/ICML/ACL 及 Nature 系期刊。
- `references/plain-writing.md`：**朴素写作 25 条**（集成 plain-writing skill）。去 AI 味的终极正反例清单：简单词、无空强调、无破折号、无 AI 高频词。与 `ai-cleanup.md` 互补：ai-cleanup 抓"AI 味特征"，本文件给"朴素写法标准"。
- `references/statistical-analysis.md`：**统计方法与报告红线**（集成 K-Dense statistical-analysis + nature-statistics）。检验选择、假设前置检查、效应量+CI、power、多重比较校正、n 与重复报告、报告模板。
- `references/equations-symbols.md`：**公式与符号规范**。编号与引用纪律、变量斜体/算子正体/单位正体字体表、一符一义红线、LaTeX amsmath 要点、交付前符号自查单。含公式推导的论文必读。
- `references/discipline-matrix.md`：**学科适配矩阵**。动笔前先判定学科范式（定量 IMRaD / 质性社科 / 人文学科）：逐维度标注 32 个工具适用/空转/误报高危，引文格式主流映射（MLA/Chicago 手工路径）、质性研究质量标准替换、文科 AI 检测误报处理协议。跨范式使用前必读。
- `references/qualitative-rigor.md`：**质性研究严谨性对照**。抽样透明度、数据收集可审计、编码留痕、Lincoln & Guba 四判准、reflexivity、常见拒稿质疑预答辩清单——质性稿件的"统计红线"等价物。

**总则**：写作质量以"教授标准"为准绳——每写完一段，切换"教授改写 → 审稿人批注"视角自查；凡实验/验证结果不理想，一律走 contingency 应变，严禁编造数据或硬凑阳性结果。

## 执行流程

严格按阶段推进，每阶段完成并自检后才能进入下一阶段。禁止跳步，禁止把未验证的推测写成事实。

**流水线总则（必须遵守 `references/workflow.md`）**：动笔前先完成"定目标期刊（步骤 0）→ 定词数（步骤 1）"两步并确认；写作中按"分章写 → 逐章核文献 → 成稿校验 → 投稿清单"推进。目标期刊与词数基准一经确认，全程不得中途更换；确需变更必须回到 workflow 步骤 0 重新评估并记录影响面。

### 阶段 0：需求澄清（≤1 次提问）

归一化用户意图为五要素：**主题、体裁（综述/实证/技术/学位章节/自媒体）、受众、篇幅、目标出口（期刊/平台）**。缺少的用合理默认值补齐（默认综述、中文、5000-8000 字、Markdown），只把真正影响方向的歧义回问用户一次，之后不再中断。

阶段 0 内必须敲定两件前置事：**① 目标期刊/出口**——用 `journal_matcher` 推荐候选并锁定唯一优先目标（参考 workflow 步骤 0）；**② 词数基准**——用 `render_template(journal=...)` 获取全篇与分章词数规划，按"不含参考文献"口径写入成稿头部备注（参考 workflow 步骤 1）。未敲定前禁止进入阶段 4 动笔。

### 阶段 1：选题论证

- 先执行 `references/thinking-protocol.md` 的思维协议：把选题任务分类（Spike/Bounded/Architectural），一次只问一个影响方向的问题，先设计后动笔，动笔前让用户对研究定位点头。
- 先执行 `references/contingency-plans.md` 的"启动前建议"：可行性验证（文献/数据/时间三查）、对接目标期刊近 3 年偏好、小切口原则。
- 给出 1-3 个候选题目，每个附带：研究问题、可行性、创新点/切入点、目标出口匹配度。
- 对照 `references/pitfalls-and-landmines.md` 避坑：选题不过宽过窄、标题无"浅析/浅谈"弱前缀、无冗余"研究/分析"。
- 参考 `references/exemplar-papers.md` 的"范式结构对照"确认目标体裁结构。
- 用户选定或默认取第 1 个后，写下一段 100 字以内的"研究定位"，作为全篇纲领。

### 阶段 2：文献调研

- 优先使用 `literature-search` 技能（本插件独立技能）：按其检索协议建检索式、多库检索、引文追踪、PRISMA 式筛选、引文验证与他引审计，产出可复现、引用零幻觉的文献清单。
- **真实搜库必须调用 paper-tools 的 `lit_search` 工具**（Semantic Scholar API）：主题检索返回标题/作者/年份/被引/DOI，作为多库交叉验证的一手来源之一；内置期刊库覆盖不足时用 `journal_search_openalex` 实时搜刊。
- 渠道与检索策略遵循 `literature-search/references/research-sources.md`：按主题选主渠道（Google Scholar/PubMed/arXiv/Semantic Scholar/CNKI 等）、主题词+自由词组合、布尔逻辑、引文追踪（前向/后向）、时间窗口。
- 产出《文献清单》：每条含 作者-年份-标题-来源-核心观点-与本主题的关系；记录检索式与检索时间，保证可复现。
- **溯源铁律**：所有事实性陈述必须在写作时标注出处；检索不到的必须注明"未找到直接文献"，严禁编造 DOI、作者或引用。所有链接/DOI 必须实际可访问。
- 对重点候选文献用 `paper-card` 技能精读生成证据卡片，供综述综合与批判性分析使用。
- 至少覆盖：背景、现状、关键争议、研究缺口，为 Introduction 和 Related Work 备料。

### 阶段 3：大纲

- 依据 `references/paper-structure.md` 的章节模板生成完整大纲：一级标题 + 每节 2-4 个要点 + 目标字数占比；可先用 `generate_outline(topic=..., genre=...)` 生成结构骨架再按选题论证裁剪。
- 大纲需自检：逻辑链完整（背景→问题→方法→结果→结论）、无遗漏、篇幅分配合理。

### 阶段 4：分章写作

- 按大纲逐节写作，一节一节来，每节落盘后再写下一节，避免上下文漂移。
- 写作要求：
  - 论点先行，段首句是结论句，段内用证据支撑；
  - 引用统一占位为 `[作者, 年份]`，成稿阶段统一转参考文献表；
  - 每个论断可溯源；推测与观点必须显式标注"（作者观点）"；
  - 禁止堆砌空话，禁止自我重复，禁止"总而言之"式凑字数。
- 中途可用 paper-tools 的 `word_count` 校验篇幅进度。**词数口径统一**：统计指正文词数、不含参考文献；将全文截取到 `## References` / `## 参考文献` 之前再统计，报告标注"不含参考文献"（参考 workflow 步骤 1）。
- 写作时对照 `references/exemplar-papers.md` 的神稿示范：每完成一段，以"教授改写版"为标准升级表达，并以"审稿人批注"视角自查（示范 D 的红线批注逐条对照）。
- 对照 `references/top-conference-writing.md` 的顶会哲学：动笔前先写下"一句贡献句"（叙事三支柱）；按 Gopen & Swan 句子清晰七原则控制句子；摘要与 Intro 是审稿人 100%/高比例阅读区，必须精雕；不给证据的 claim 一律删。
- 涉及数据分析与统计的部分，对照 `references/statistical-analysis.md`：检验选择、假设前置检查、效应量+CI、power、多重比较校正、n 报告，方法章节写明统计细节。
- 对照 `references/pitfalls-and-landmines.md` 的"结构与逻辑的坑"逐项规避：段落无过渡、方法/结果重复、讨论只罗列、结果夹带主观解读、讨论夸大结论。
- 若写作过程中发现实验/数据/验证结果不符合预期，按 `references/contingency-plans.md` 的 Plan A-E 决策并如实执行，绝不编造数据或硬凑阳性结果。

### 阶段 5：语言润色与朴素化改写

- 按 `references/ai-cleanup.md` 的 AI 写作痕迹清单逐条扫描：夸大重要性、空洞抬大词、模糊来源、销售腔、AI 高频词（delve/pivotal/深入探讨 等）、强行三连、被动语态堆叠、em dash 滥用、填充词、名物化堆积。先重写再对照核查。
- **机器先扫、人工再判**：用 `check_style(markdown=全文)` 定位 AI 高频词/口语化/超长段句（含行号），用 `check_ai_signature(markdown=全文)` 获取统计画像（句长突发性/TTR/模板短语密度 → 0-100 分）。改写目标是把模板腔换成朴素学术表达——这是**写作质量改进**，依据是 plain-writing 标准，不是规避任何检测；分数只代表"待复核密度"，不构成判决。
- 按 `references/plain-writing.md` 的朴素写作 25 条逐条对照：简单词、无空强调、无破折号/弯引号、无 AI 高频词、无类比、无"不仅是 X 更是 Y"、无模糊指示代词、无"数要点"开场。命中处给出 Before → After。
- 按 `references/writing-standards.md` 执行五道顺序审查：清冗余 → 语态与动词活力 → 句子结构 → 关键词一致性 → 数值与引文完整性；随后过机械门禁与语义门禁。
- 口语化表达转书面学术语；长难句拆分；术语全文统一。
- **铁律**：朴素化只改表达，绝不改事实、删数据、弱化结论。
- 输出润色记录：改动点清单（可选）。

### 阶段 6：引用与参考文献核验

- 按 `references/citation-guide.md` 选定的引文格式（默认 GB/T 7714，可切 APA/MLA/IEEE）生成参考文献表。**有 DOI 的条目优先调用 `format_citation(doi=..., style=...)` 直接生成规范条目**（真实 Crossref 元数据，支持 APA 7/GB-T 7714/IEEE/MLA 9/Chicago/BibTeX），杜绝手打格式漂移与字段编造。
- 核验：正文引用的每一条都在文献表中，文献表每一条都被正文引用，无孤立条目；可用 `check_intext_citations` 做双向机检（数字式/作者-年份式均支持）。
- 无法核实真实出处的占位条目必须标记为"待用户提供原始出处"，严禁伪造。
- 用 `literature_checklist` 生成逐条核验清单并逐条落实；对含 DOI 的条目执行 **DOI 三重核对**（① 可解析 ② 卷期页码与 Crossref 一致 ③ 作者年份匹配，警惕同名多篇/预印本混淆），全部 A 级后才进入下一阶段（参考 workflow 步骤 3 与 `references/citation-guide.md`）。
- 每条待核验文献优先调用 paper-tools 的 `citation_verify` 工具（真实调 Crossref API）：有 DOI 按 DOI 核验，无 DOI 按标题核验；工具返回的元数据（卷期页码/作者/年份）与文献表逐项比对，不一致即降级为 B 级并标记待核实。
- **批量门禁**：全表完成后调用 `verify_references(markdown=全文)` 出 A/B/C 统计——C 级必须补来源或删除，禁止带 C 级进入下一阶段（workflow 步骤 3 门禁）。

### 阶段 7：图表制作与格式排版

- 按 `references/figures-tables.md` 制作与校验图表：
  - 图：一图一主题、坐标轴含单位、误差线与显著性标注、分辨率 ≥300dpi、色盲友好配色、正文按出现顺序引用；
  - 表：三线表、表头自明含单位、显著性脚注、表中数据与正文严格一致；
  - 每张图/表配完整 caption（结论 + 数据说明 + 缩写/图例）。
- 用 paper-tools 的 `render_template` 生成目标出口的模板文件：
  - 期刊投稿 → LaTeX（IEEE/Elsevier 模板结构）或 Word 结构稿；
  - 公众号/知乎 → 带标题层级、摘要、引用块的 Markdown；
  - 学位论文 → 按 `references/thesis-guide.md` 执行开题 → 写作 → 查重 → 盲审 → 答辩全流程，并用 `render_template(genre="thesis")` 生成章节骨架；分章文件交付前用 `audit_project(project_dir=...)` 做跨章合并审计。
- 标题层级、图表编号、公式、参考文献格式按模板规范。

### 阶段 8：质量自检（交付前必做）

- **确定性审计先行**：先跑机器审计再人工复核——
  - `proofread(markdown=全文)`：结构/文风/标点/图表/术语/重复/正文引用核对/数字一致性/断言对冲（实证体裁含统计诚信），ERROR 项必须清零；
  - `audit_paper(markdown=全文, genre=..., journal=...)`：一键全量（另含 AI 痕迹画像 + 章节完整性 + 统计红线 + 词数预算对照），输出启发式总分供交付前留档；
  - 摘要专项 `check_abstract`、标题专项 `check_title`：四要素覆盖与空泛措辞在投稿前必查。
- 对照 `references/writing-checklist.md` 与 `references/self-review.md` 逐项过一遍，输出自检表：
  - 结构完整性、逻辑一致性、证据充分性、引用合规性、语言质量、篇幅达标、格式合规；
  - **claim-evidence 对齐**：全文每个可证伪论断找到直接证据，标记 Over-claim / Under-support / Orphan 三类问题并修复；
  - **审稿人 10 问**：模拟外审通读全文；
  - **Red-team**：主动寻找最弱攻击点至少 3 个并书面回答。
  - 对照 `references/pitfalls-and-landmines.md` 的"审稿人隐性雷区"（一稿多投/重复发表/署名/利益冲突/AI 披露/数据造假）与"编辑视角十五误区"逐条核对，任何命中先解决再交付。
- 统计严谨性按 `references/statistical-analysis.md` 红线复核（机检入口：`check_stats`）：n 与重复、效应量、多重比较校正、异常值处理、不把不显著当等价。
- 学位论文等多文件工程改用 `audit_project(project_dir=...)`：按章合并后跨章节查缩写一致、整句自我重复与引用对应——单章通过不代表工程级一致。
- **自查重**：涉及自己既往稿件复用时调用 `check_self_plagiarism(markdown=全文, corpus_dir=历史稿目录)` 做 n-gram 重叠检测（学位论文章节复用/系列论文模板句场景），命中项人工判断改写或引用。
- **残留取证**：交付前调用 `check_tamper_traces(markdown=全文)` 确认正文无零宽字符/同形字/异常空白等残留（多轮复制粘贴与格式转换可能引入），命中项先清洗再交付。
- **智能体迭代回路**：多轮修改场景下用 `gate_suite(markdown=全文)` 一次取回全部离线门禁的 pass 判定与 blocking 清单，修复后用 `audit_delta(before=旧版, after=新版)` 验证净改善（新引入问题多于修复则回退），循环至 `pass=true` 且 `errorsAfter=0`；高频复检用 `audit_paper(brief=true)` 省上下文。整条流水线的顺序计划可用 `next_actions(goal=submission|thesis|polish)` 直接获取。
- **残留取证**：交付前调用 `check_tamper_traces(markdown=全文)` 确认正文无零宽字符/同形字/异常空白等残留（多轮复制粘贴与格式转换可能引入），命中项先清洗再交付。
- 深度自检可用 `paper-review` 技能（本插件独立技能）的 12 轴技术关注清单做同行评审演练；重点文献的结论边界与批判性分析参考 `paper-card` 技能产出的证据卡片。
- 未达标项必须在本阶段修复，修复后再输出最终稿。

## 交付物

1. 成稿文件（Markdown 为主，可附 LaTeX/Word 版本）；
2. 《文献清单》；
3. 自检表（达标项/未达标项及修复记录）。

## 关键铁律

- 不编造文献、数据、DOI、实验结果；无法验证的标注"待核实"。
- 不在未确认的情况下宣称论文"已发表""已被接收"。
- 涉及需要外部账号/凭据的操作（投稿、发布），指引用户完成，不伪造完成状态。
- **门禁证据链**：每个门禁的机器输出原文（verify_references 报告 / proofread 报告 / audit_paper 总分 / 自检表）必须作为交付物随稿提交；最终答复附关键门禁结果摘要——禁止口头声称"已通过"而不附产物。
- **工具不可达诚实降级**：paper-tools MCP 工具不可用或外部 API 失败时，改按对应 references 的手工协议执行，并在交付物中如实标注"该项未经程序化核验"；严禁假装已机检。
