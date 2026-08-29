---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_fa3d7c1e9ba611f1a98a525400f8a582
    ReservedCode1: placeholderbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_fa3d7c1e9ba611f1a98a525400f8a582
    ReservedCode2: placeholderbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
---

# 神稿与范文库：范式结构、范文渠道、角色模拟写作示范

> 用途：写作前选范例、写作中对照范式、写作后"角色扮演"自查。
> 核心观点：好论文不是按技巧编出来的，但新手必须先"拆解模仿"高质量范式，
> 再逐步形成自己的表达。直接抄袭是学术不端，拆解模仿是正当学习方法。

## 一、范式结构对照（先定范式，再动笔）

### 1. 通用 IMRaD（理工/医学/部分社科）

| 模块 | 核心要求 |
|------|----------|
| 标题 | 研究对象 + 方法 + 核心结论；中文 20-25 字，英文 10-15 词 |
| 摘要 | 四要素：目的/方法/关键结果(带数据)/结论意义 |
| 关键词 | 3-5 个学科通用术语 |
| 引言 | 四段式：大领域现状与重要性 → 已有研究梳理与不足 → 本研究 gap 与创新 → 本文内容与方法 |
| 方法 | 按"可重复"标准写全：样本/试剂/仪器型号/流程/统计 |
| 结果 | 先文字后图表；图表自明；只陈述事实不解读 |
| 讨论 | 三部分：核心发现 → 与已有研究对比+机制+创新 → 局限与展望 |
| 结论 | 1-2 段，总结+价值，不重复摘要与讨论 |
| 参考文献 | 格式统一；近 5 年≥50%（综述近 3 年≥60%）；避免过度自引 |

### 2. 学科差异

| 学科 | 特殊要求 |
|------|----------|
| 理工科(CS/物理/化学) | 方法分小节+代码/数据集链接；结果含消融实验(ablation)、对比实验证明优越性；讨论点明创新性与适用场景 |
| 医学 | 方法必须交代伦理审批与知情同意；结果符合医学统计规范(样本量/p值/置信区间)；讨论对比临床指南、说明推广价值 |
| 人文社科 | 引言可更长，梳理理论脉络；质性研究写清访谈对象/资料收集/编码过程，量化研究写清数据来源/计量模型/内生性处理；结论可延伸政策建议 |
| 综述 | 不是文献堆砌，要有"述评"；梳理发展脉络+指出不足+未来方向；近 3 年文献≥60%；结构可主题式或时间线式 |

## 二、高质量范文获取渠道

1. **目标期刊近 1-2 年文章**：最贴合期刊偏好，模仿最不易错（期刊官网）。
2. **导师/同门已发表论文**：方向一致、结构风格最贴合领域（尤其投中目标期刊的那篇）。
3. **本校本专业优秀学位论文**：结构完整，适合学习整体逻辑（高校学位论文库）。
4. **学术写作指南书籍**：如《Writing Science: How to Write Papers That Get Cited and Proposals That Get Funded》《科技论文写作指南》，内含高质量范文与讲解。
5. **预印本平台**：arXiv、bioRxiv、ChinaXiv 看最新前沿写法。

## 三、范文拆解模仿四法

1. **拆结构**：逐段拆解范文——每部分写什么、怎么衔接、逻辑怎么排。
2. **对比找规律**：找 3-5 篇同领域范文对比引言/讨论/结果写法，提炼通用模板（避免学成个例）。
3. **看创新点呈现**：重点学范文怎么在引言提 gap、在讨论突出创新、用结果支撑结论。
4. **学图表设计**：排版、标注、颜色区分、如何让图表自明。

---

## 四、神稿：角色模拟写作示范

以下示范模拟不同角色对同一研究内容（假设研究："大语言模型辅助医学影像诊断的初步效果评估"）的处理，展示"学生第一稿 → 教授改写稿 → 审稿人批注"的差异。写作时可按此做角色扮演自查。

### 示范 A：摘要——学生版 vs 教授版

**学生版（流水账）**
> 本文首先介绍了大语言模型在医学影像领域的应用背景，然后分析了当前存在的若干问题，最后提出了我们的改进方法并通过实验进行了验证，结果表明我们的方法有一定效果。

**教授版（四要素）**
> 目的：评估基于大语言模型的影像报告辅助系统对基层医师诊断准确率的影响。方法：纳入 120 例胸部 CT，由 30 名基层医师在有无系统辅助两种模式下阅片，以专家组诊断为标准计算准确率。结果：辅助模式下诊断准确率由 71.3% 提升至 84.2%（p<0.001），平均阅片时间减少 32%。结论：该系统可显著提升基层医师诊断准确率与效率，为 AI 辅助医疗落地提供证据。

### 示范 B：引言四段式——学生版 vs 教授版

**学生版（大而空）**
> 近年来，人工智能技术发展迅速，被广泛应用于各行各业。大语言模型作为人工智能的重要分支，也受到了越来越多的关注。本文研究了大语言模型在医学影像中的应用……

**教授版（四段式）**
> 【背景】医学影像判读依赖经验，基层医师误诊率显著高于三甲专家，已构成医疗资源不均衡的重要环节（引 2-3 篇近 3 年权威文献）。【现状与不足】现有 CAD 系统多针对单一病灶设计，泛化性差；大语言模型虽展现出通用理解能力，但缺乏在真实基层场景下的诊断效能证据。【gap】尚无研究系统评估大语言模型对基层医师实际诊断准确率的提升效应。【本文】为此，本研究在 120 例胸部 CT 上开展随机交叉试验，量化辅助系统对 30 名基层医师诊断准确率与阅片效率的影响。

### 示范 C：讨论——学生版 vs 教授版

**学生版（重复结果）**
> 我们的实验结果显示辅助组准确率更高，说明大语言模型对医学影像诊断有帮助。

**教授版（三部分）**
> 【核心发现】本研究首次在基层真实场景中证明大语言模型辅助可使诊断准确率提升 12.9 个百分点。【对比机制】这一提升幅度高于既往 CAD 系统报道的 4-7 个百分点，可能源于大语言模型能同时理解图像特征与临床上下文；与 Zhang 等(2024)的结论一致，但本研究进一步发现提升集中于低年资医师，提示系统价值在于弥补经验鸿沟。【局限与展望】本研究为单中心、样本量有限，随访周期短；未来需多中心前瞻性研究，并评估系统在不同病种上的泛化性与长期使用对医师判断力依赖的影响。

### 示范 D：审稿人批注示例（投稿前的"红线批注"）

模拟审稿人对一份稿件的批注，写作时逐条自查：

1. **BLOCKER** 摘要未报告样本量与 p 值 → 读者无法判断结果可信度。
2. **BLOCKER** 方法未交代伦理审批编号与知情同意 → 医学论文硬性要求。
3. **WARNING** 引言 3 页未提出研究 gap → 创新性表述不清。
4. **WARNING** 讨论中"该方法可推广至所有医疗机构"属过度外推 → 超出证据范围。
5. **WARNING** 引用中 60% 为 5 年前文献，且含 2 条 arXiv 预印本支撑核心结论 → 前沿性与来源可信度不足。
6. **INFO** 图表 3 无自明性，需补充统计方法与误差说明。

### 示范 E：投稿信——套模板 vs 教授级个性化

**套模板**
> Dear Editor, We are pleased to submit our manuscript entitled "…". We hope it will be suitable for your journal. Thank you.

**教授级**
> Dear Editor, We are pleased to submit our manuscript "Large Language Model-Assisted Interpretation Improves Diagnostic Accuracy Among Primary Care Physicians: A Randomized Crossover Study". This work addresses a gap highlighted by your journal's recent series on AI in primary care: no prior study quantified the real-world benefit of LLM assistance on diagnostic accuracy. Using 120 chest CTs and 30 physicians, we found a 12.9 percentage-point improvement (p<0.001). We confirm this manuscript is not under consideration elsewhere and all authors have approved submission. We suggest three potential reviewers with complementary expertise in medical AI evaluation. Thank you for your consideration.

### 示范 F：Response Letter——敷衍 vs 专业

**敷衍**
> We thank the reviewer. We have revised the paper.

**专业（三段式：感谢+复述意见+逐条回应）**
> We thank the reviewer for the constructive comments.
> **Comment 1**: The reviewer noted the absence of sample size justification.
> **Response**: We have added a power analysis section in Methods (Page 5, lines 118-124), citing the effect size from our pilot study (n=20), which yields 90% power at α=0.05. The revised text is highlighted in yellow.

## 五、使用建议

- 动笔前：先定范式（见"一、范式结构对照"），再选 1-2 篇范文拆解（见"二、三"）。
- 每完成一段：切换角色扮演——用"审稿人批注"视角扫一遍（示范 D）。
- 投稿前：用"教授版"对照自己的摘要/引言/讨论/投稿信，逐项升级（示范 A/B/C/E）。
- 返修时：严格按"三段式 Response Letter"逐条回应（示范 F），修改处标红。
