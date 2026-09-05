---
name: paper-review
description: 投稿前质量审查技能：以挑剔审稿人 + 文字编辑的双重视角审查成稿，执行 claim-evidence 对齐、五道审查法、审稿人 10 问、Red-team 压力测试，输出带 BLOCKER/WARNING/OK 等级的审查报告与可执行修复建议。
---

<!--
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_ff59c05e9ba611f1a98a525400f8a581
    ReservedCode1: E+90XRfy1qbNJxQjT1LvUbONkuUAY1P7WuvDro0ELcaHk1ithl+I+IwvsrBT2LLu0aUXbbuBj8NFGbFmYBuYz5gF6TwMmjSEosZhaoWdxkglO3cRnyi+Rdac4hsrFgy6MgA7ZijJfspiI/6vNKnB7UI0G8hQHezrGViAMMJM069nh4UJz5002RCU8FI=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_ff59c05e9ba611f1a98a525400f8a581
    ReservedCode2: E+90XRfy1qbNJxQjT1LvUbONkuUAY1P7WuvDro0ELcaHk1ithl+I+IwvsrBT2LLu0aUXbbuBj8NFGbFmYBuYz5gF6TwMmjSEosZhaoWdxkglO3cRnyi+Rdac4hsrFgy6MgA7ZijJfspiI/6vNKnB7UI0G8hQHezrGViAMMJM069nh4UJz5002RCU8FI=
-->

# paper-review：投稿前质量审查

## 目标

以挑剔审稿人 + 文字编辑的双重视角审查成稿，找出所有会削弱录用概率或损害可信度的问题，并给出可直接执行的修复建议。审查严格基于稿件内容与可核验证据，不注入新事实。

## 输入

- 成稿文件（Markdown 为主，可含 LaTeX）
- （可选）目标期刊/平台的审稿要求或 style guide

## 执行流程

按顺序执行四道审查，全部完成后汇总报告。

### 第 0 道：规则校对预检（paper-tools 自动化）

- 先调用 `proofread(markdown=全文)` 获取规则层校对报告：文风 AI 词/口语化/超长段句、中英标点混用、图表编号与引用对应、缩写定义一致性、句子重复、文献格式混用与未来年份。
- ERROR 项（幽灵图表引用、未来年份、格式混用、重复条目）直接列入审查报告的 BLOCKER 候选；WARNING 项转入第 2/3 道人工判断是否成立。规则报告不替代人工审查，只是收窄火力范围。
- 参考文献真实性单独跑 `verify_references(markdown=全文)`：C 级条目一律 BLOCKER。

### 第 1 道：Claim-Evidence 对齐

- 提取全文所有**可证伪论断**（含摘要、结论、各节首句）。
- 逐个论断定位直接证据（数据表/图/实验/引文）。
- 标记三类问题：
  - **Over-claim**：论断超出证据范围；
  - **Under-support**：证据不足（样本过小、无基线、无消融）；
  - **Orphan**：有论断无证据。
- 每条给出修复建议（降级措辞 / 补证据 / 收紧结论 / 删除）。

### 第 2 道：五道审查法

依据 `references/review-methods.md` 的"五道审查法"执行：
1. 清冗余（Clutter）；
2. 语态与动词活力（被动语态、名物化）；
3. 句子结构（主语动词靠近、长句拆分）；
4. 关键词一致性（术语漂移）；
5. 数值与引文完整性（单位、出处、图表编号对应）。

### 第 3 道：审稿人 10 问

依据 `references/review-methods.md` 的"审稿人 10 问"逐问作答，重点核查：方法可复现性、实验公平性、结果与结论一致性、图表自明性、参考文献真实性。

### 第 4 道：Red-team 压力测试

- 切换为对立审稿人：主动找全文最弱处（方法漏洞、对照组缺失、统计误用、选择性报告）。
- 提出至少 3 个攻击点，逐点书面回答；无法回答的攻击点升为 BLOCKER。

## 输出：审查报告

按问题严重度分级，每条含：位置（章节/行）→ 问题描述 → 证据/依据 → 修复建议：

| 等级 | 含义 | 处理 |
|------|------|------|
| BLOCKER | 影响可信度或录用，必须修复 | 返回 paper-writing 修复后重审 |
| WARNING | 削弱质量，建议修复 | 本轮或下轮修复 |
| OK | 通过 | 无需处理 |

报告末尾给出**总体结论**：可投 / 修复后投 / 不建议投。

## 铁律

- 审查不新增事实、不改结论；所有判断基于稿件内证据或可核验外部来源。
- 不因"表达自然"而降低对 claim 支撑度的要求。
- 发现学术不端红线项（伪造数据/抄袭/幽灵引用）必须标 BLOCKER 并明确提示。
