---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_f8bccbcf9ba611f19467525400287e28
    ReservedCode1: 308jH4+p13Ij6F5meaC8yx3SH7X4a8mSC85i9GzHjTv4QVYOCPKisf6yETdRpS+y1QbPG27YKNzDycQsgwZ1y/3XZFeOWXcDRbMZPRFS0L9Pa79SECasr7jxhiDq7ACuMGKABBbpki39mhESl0uYkRbOLaoGZbRkETrYQD8lZeleFh5dvTl+wjaMr/A=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_f8bccbcf9ba611f19467525400287e28
    ReservedCode2: 308jH4+p13Ij6F5meaC8yx3SH7X4a8mSC85i9GzHjTv4QVYOCPKisf6yETdRpS+y1QbPG27YKNzDycQsgwZ1y/3XZFeOWXcDRbMZPRFS0L9Pa79SECasr7jxhiDq7ACuMGKABBbpki39mhESl0uYkRbOLaoGZbRkETrYQD8lZeleFh5dvTl+wjaMr/A=
---

# 学术文献检索渠道指南

> 来源与依据：综合公开调研（学术搜索引擎综述、各数据库官方说明、Awesome-Scientific-Skills 生态评估标准，2026-08 检索）。用于论文写作技能中的文献调研阶段。

## 一、文献检索优先级与渠道选择

检索不只靠一个引擎。按论文类型与学科选择主渠道，再用交叉验证补漏。

| 渠道 | 覆盖 | 适用场景 | 注意 |
|------|------|----------|------|
| Google Scholar | 全学科综合 | 通用起点、引文追踪、查被引 | 收录全但质量不均，需人工筛选 |
| Web of Science / Scopus | 全学科（索引规范） | 权威期刊检索、影响因子、文献计量 | 需机构订阅 |
| PubMed / PMC | 生物医学、生命科学 | 医学、生物、临床 | 主题词 MeSH 检索是核心能力 |
| arXiv | 物理、数学、计算机预印本 | AI/ML/系统领域最新工作 | 未经同行评审，注意版本 |
| Semantic Scholar | 全学科（AI 加持） | 语义检索、核心论文提炼 | 免费，API 友好 |
| CNKI（知网）/ 万方 / 维普 | 中文学术 | 中文期刊、学位论文、国内研究 | 中文学术主流 |
| IEEE Xplore | 电子工程、计算机 | 工程、信号、通信 | 需订阅 |
| ACM DL | 计算机 | CS 会议期刊 | 需订阅 |
| 学科专属库 | 按领域 | ChEMBL（化学）/ PDB（结构生物）/ TCGA（肿瘤）等 | 见 Awesome-Scientific-Skills 领域工具 |

## 二、检索策略规范

### 1. 关键词构建
- **主题词 + 自由词结合**：如 PubMed 用 MeSH 主题词 + 自由词（title/abstract 检索），提高查全率与查准率。
- **同义词扩展**：为每个核心概念列出同义词与上下位词（如 "LLM" → "large language model"、"foundation model"）。
- **布尔逻辑**：AND 缩小范围，OR 合并同义词，NOT 排除无关主题；用引号锁定短语。
- **时间窗口**：综述类需覆盖近 5 年 + 经典奠基文献；热点方向追踪近 1-2 年 + 预印本。

### 2. 引文追踪法（雪球检索）
- **前向追踪**：找到核心论文后，用 Google Scholar/Semantic Scholar 的"被引"功能找后续发展。
- **后向追踪**：读核心论文参考文献，追溯原始出处，避免二手转引。

### 3. 文献筛选标准
- 优先一手来源（原始实验论文），谨慎对待只读二手综述。
- 会议/期刊声誉与真实性核验：能查到 DOI/官方页为准，警惕论文工厂。
- 对 AI 生成检索结果保持警惕：链接/DOI 必须实际打开验证，禁止引用无法核验的条目。

### 4. 检索结果落地要求
- 每条关键文献记录：作者、年份、标题、出处（期刊/会议）、DOI 或 URL。
- 与论点映射：标注每条文献支持/反驳/补充哪个论点，形成证据表。
- 保存检索式与时间，保证可复现。

## 三、常见陷阱
- 只用单一搜索引擎导致漏检（尤其中英文献割裂）。
- 引用二手转引未溯源原文。
- 把预印本当已发表成果引用（需标注预印本状态）。
- 未核验 DOI/链接，引用不存在的文献。
