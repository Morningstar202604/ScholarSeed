---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_fc00aad39ba611f19467525400287e28
    ReservedCode1: uEQ/hFQlA3fLD3/6y78wiJd636GzFs4pYNNeGAno4giq/6bXgq6dij/pt+X2fOXtGUgJIwnk2jmXf/2+seZCtx3QPQiGUFuGq2hI8fi6JnpFcPOrMz1dUAz8/JSyY4zWCn1EbgnhimSTbRF0ecjYl4bDC50LVuNqYgfeMr05V6dRkQC5OiDzqlg4ytA=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_fc00aad39ba611f19467525400287e28
    ReservedCode2: uEQ/hFQlA3fLD3/6y78wiJd636GzFs4pYNNeGAno4giq/6bXgq6dij/pt+X2fOXtGUgJIwnk2jmXf/2+seZCtx3QPQiGUFuGq2hI8fi6JnpFcPOrMz1dUAz8/JSyY4zWCn1EbgnhimSTbRF0ecjYl4bDC50LVuNqYgfeMr05V6dRkQC5OiDzqlg4ytA=
---

# 投稿前自检与审稿人视角审查

> 来源与依据：综合公开调研——彭思达（Master-cai/Research-Paper-Writing-Skills，MIT）的审稿人视角投稿前自检、SNL-UCSB/paper-writing-skill（MIT）的独立红队协议、通用学术写作指南。用于论文成稿后的质量闸门。

## 一、Claim-Evidence 对齐检查（核心）

逐条走查全文每个论断：

1. 列出所有**可证伪论断**（含摘要与结论中的）。
2. 每个论断找到**直接证据**（数据表/图/实验/引用文献）。
3. 标记三类问题：
   - **Over-claim**：论断超出证据范围（如单数据集下结论说"普适"）。
   - **Under-support**：论断有证据但不足（样本过小、无消融、无基线）。
   - **Orphan**：说了论断但全文找不到证据支撑。
4. 每个 Over-claim 降级措辞或补实验/限定语；Under-support 补证据或收紧结论；Orphan 删除或补证。

## 二、审稿人 10 问（投稿前模拟外审）

以挑剔审稿人身份通读全文，逐问回答：

1. 研究问题是否清晰、有明确动机？
2. 与已有工作的差异是否说清（不是简单罗列）？
3. 方法能否被复现（数据/代码/超参/统计细节）？
4. 实验设计是否公平（基线是否最强、是否同设置）？
5. 结果是否支持结论，有无选择性报告？
6. 图表的自明性（不看正文能否读懂）？
7. 术语与缩写是否一致、无歧义？
8. 参考文献是否相关、完整、可核验？
9. 有无违反学术规范（一稿多投、数据造假、未披露利益冲突）？
10. 若审稿人只读摘要+结论，是否会被误导？

## 三、Red-team 独立审查协议

- 切换为"对立审稿人"视角：主动找论文最弱处（方法漏洞、对照组缺失、统计误用）。
- 尝试提出至少 3 个攻击点并书面回答。
- 若无法回答，回到上一阶段补强或弱化 claim。

## 四、投稿前最终闸门（Checklist）

- [ ] 全文无 AI 味残留（过 ai-cleanup 清单）
- [ ] 五道审查法全部执行（writing-standards.md）
- [ ] 结构校验通过（IMRaD/目标模板）
- [ ] 引文全部核验，格式符合目标要求
- [ ] 字数符合目标期刊/平台限制
- [ ] 图表编号、正文引用一一对应
- [ ] 无学术不端红线项
- [ ] 摘要自包含、结论不引入新内容

## 五、红线（学术诚信，不可触碰）
- 不伪造数据、不篡改结果、不选择性隐藏反例。
- 不抄袭、不自我抄袭（避免重复发表同一结果）。
- 不虚构或"美化"参考文献（含 DOI）。
- 一稿多投属学术不端；转投前需明确撤稿。
- AI 参与写作按目标期刊规定披露。
*（内容由AI生成，仅供参考）*
