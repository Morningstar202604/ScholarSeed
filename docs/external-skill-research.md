# 外部论文 skill 调研与甄别记录（v1.8.0）

本文档记录 ScholarSeed v1.8.0 集成外部论文类 skill 的调研过程、甄别标准、采纳与放弃结论。
目的：复用社区公认好用的论文 skill，避免逐个自造；仅吸收方法与规则，未复制任何原文。

## 1. 调研范围（按论文生产环节）

| 环节 | 调研方向 | 典型外部 skill 形态 |
|------|----------|--------------------|
| 搜索环节 | 文献检索、深度搜索、引文验证 | academic-search / ref-verifier / literature-review |
| 思维环节 | 深度思考、头脑风暴、选题发散 | brainstorming（spike/bounded/architectural 三路径） |
| 写作环节 | 顶会写作、朴素写作、学术表达 | ml-paper-writing / plain-writing |
| 统计环节 | 统计方法选择与报告 | statistical-analysis / nature-statistics |
| 审稿环节 | 技术审查、claim-evidence | reviewer / review-methods（12 轴） |
| 最后环节 | 深度阅读、证据卡片、返修 | paper-card / response-to-reviewers |

## 2. 甄别标准

1. **对写论文是否真正有用**：是否直接命中论文生产的某一步，而非泛用聊天/通用 agent 技巧；
2. **方法可移植性**：规则是否以"可复述的方法清单"形态存在，能落成 references 供 Agent 查阅；
3. **许可合规**：Apache-2.0 或 MIT，允许方法借鉴；
4. **与现有插件互补性**：不与 ScholarSeed 既有 18 大坑、范文库、去 AI 味等重复；重复者跳过。

## 3. 采纳清单（已吸收进插件）

| 来源（许可） | 吸收内容 | 落点 |
|--------------|----------|------|
| nature-skills（Apache-2.0） | academic-search 检索协议、ref-verifier 引文存在性验证、paper-card 16 段证据卡片、reviewer 12 轴技术审查、response-to-reviewers 逐点返修 | `literature-search/`、`paper-card/`、`paper-review/references/review-methods.md`、`paper-publish/references/revision-response.md` |
| obra/superpowers（MIT） | brainstorming 三路径（Spike/Bounded/Architectural） | `paper-writing/references/thinking-protocol.md`、`topic-selection.md` |
| K-Dense-AI/scientific-agent-skills（MIT） | literature-review 综述筛选与综合、statistical-analysis 统计红线、claim-evidence 边界 | `literature-search/references/`、`paper-writing/references/statistical-analysis.md` |
| Orchestra-Research/AI-Research-SKILLs（MIT） | ml-paper-writing 顶会叙事三支柱、Gopen & Swan 句子七原则、引文绝不幻觉铁律 | `paper-writing/references/top-conference-writing.md` |
| docwriter plain-writing（MIT） | 朴素写作 25 条正反例清单 | `paper-writing/references/plain-writing.md` |

## 4. 放弃清单与理由

- **通用画图/图表生成 skill**：与本插件既有 `figures-tables.md`（图表规范 + 四步作图流程）重叠；且论文图表强依赖期刊/学科规范，通用生成器收益低，未采纳。
- **通用深度搜索/深度思考类 skill（泛用版）**：多数是"多轮思考 + 分步提问"的通用元技能，与本插件论文专用流程重复；论文专用检索与思维已由 nature-skills 与 superpowers 的方法吸收替代。
- **仅靠 Demo 脚本、无维护的 skill**：无法核实质量与许可，未采纳。
- **语言风格过度文学化的写作 skill**：与顶刊"朴素精确"取向相悖，未采纳。

## 5. 使用边界声明

- 本插件仅吸收上述来源的**方法规则**（检索式如何构建、证据如何分级、统计如何报告等），未复制其原文、示例或版权文本。
- 外部来源清单与许可以上表为准；如需逐字引用，请回各来源仓库核对授权。
- 已集成内容与各来源的关系在 `CHANGELOG.md` [1.8.0] Note 中同步声明。
