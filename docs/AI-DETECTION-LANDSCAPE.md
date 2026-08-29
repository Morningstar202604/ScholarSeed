# AI 文本检测技术全景与 ScholarSeed 的能力边界（用户指南）

> 面向：论文作者、导师、期刊编辑。目的：说清楚"什么能信、什么不能信"。
> 学术依据见文末引用；完整对标分析见 [CAPABILITY-ASSESSMENT.md](CAPABILITY-ASSESSMENT.md)。

## 1. 先说结论

1. **任何"AI 率 XX%"式单一分数都不应作为处分依据。** 这不是 ScholarSeed 的保守，而是学界共识：斯坦福研究显示主流检测器对非英语母语者作文误报率高达 61.3%（Liang et al., Patterns 2023）；多机构联合测评 14 个商用工具无一准确率超过 80%（Weber-Wulff et al. 2023）。Vanderbilt、Yale、UC Berkeley 等大学已因此禁用自动检测。
2. **检测是概率性的，取证是确定性的。** 判断"是否 AI 所写"永远有误判空间；但判断"文本里有没有零宽字符/同形字注入/异常空白"是客观字符级事实——ScholarSeed 两条线都做，且明确标注哪条是哪种性质。
3. **引文核验是硬证据。** `citation_verify`/`verify_references` 走 Crossref/Semantic Scholar 实时比对，A/B/C 分级可直接作为交付门禁——这是全场唯一不依赖启发式的判定。

## 2. ScholarSeed 两个 AI 相关工具的分工

| 工具 | 检测什么 | 性质 | 局限 |
|---|---|---|---|
| `check_ai_signature` | 写作风格的统计画像：句长突发性 CV、词汇丰富度 MATTR、模板短语密度、句首转折占比 | **启发式提示**（0-100 分，档位仅代表"值得复核的密度"） | 对刻意规避表层特征的文本天然盲（实测规避型样本仅得 3 分）；对未经校准的文体（人文阐释类）请用 humanities 模式并降低预期 |
| `check_tamper_traces` | 处理痕迹取证：零宽/不可见字符、西里尔/希腊同形字混入拉丁单词、行内异常空白串 | **客观字符级证据**（每条带行号可复现） | 只证明"文本被非常规工具处理过"，不证明"是 AI 写的"；正常俄文/希腊文段落天然豁免 |

两者互补关系：降AI服务改写文本以骗过统计画像 → 改写与混淆过程本身会留下痕迹。统计画像测"像不像"，痕迹取证抓"动没动过手脚"。

## 3. 学术界方法谱系（为什么我们不做"第 N 个检测器"）

| 流派 | 代表工作 | 原理 | 为什么 ScholarSeed 不采用 |
|---|---|---|---|
| 白盒概率法 | Binoculars (ICML 2024)、Fast-DetectGPT (ICLR 2024)、DetectGPT (ICML 2023)、GLTR (ACL 2019) | 用语言模型 log-probability 计算困惑度比/概率曲率；Binoculars 在 0.01% 误报率下检出 90%+ ChatGPT 文本 | 需要 GPU 加载大模型或外部推理服务，破坏零依赖承诺；对非母语者有系统性偏见（困惑度低=简单=疑似AI） |
| 监督分类器 | Ghostbuster、RADAR (NeurIPS 2023)、Pangram（新一代商用，自报英文误报率 0.0041%） | 标注数据训练分类器；Pangram 经 Epoch AI 独立验证 | 域外泛化差（换模型/换体裁掉点）；需要训练数据与算力 |
| 水印法 | Kirchenbauer et al. (ICML 2024)、Google SynthID-Text | 生成时埋统计偏置 | 只有生成方配合才有效，无法检测第三方模型输出 |
| **表层统计启发式** | GPTZero 初代（perplexity+burstiness）、**ScholarSeed check_ai_signature** | 句长分布/词汇丰富度/模板短语 | 最弱一档：RAID 基准证明可被句长节奏调整完全绕开。我们保留它但诚实定位为提示；GPTZero 自己也已转向 ML 分类器 |
| **检索比对防御** | Krishna et al. (EMNLP 2023)：改写可骗过所有检测器，但检索可还原 | 与候选源做 n-gram 重叠比对 | 已采用：`check_duplicates` / `check_self_plagiarism` 即此思路 |

## 4. 已知攻击手段与对应防线（RAID 基准，ACL 2024）

| 攻击 | 手法 | 对 SOTA 检测器的杀伤 | ScholarSeed 防线 |
|---|---|---|---|
| Homoglyph 同形字 | e→е（西里尔）肉眼不可辨替换 | Binoculars 79.6→37.7 | ✅ `check_tamper_traces` 直接检出（客观痕迹） |
| Zero-width space | 词间插零宽空格 | 多个检测器输出整体翻转 | ✅ 同上 |
| Whitespace 异常空白 | 行内多余空白串 | 多个检测器掉 ~16 点 | ✅ info 级提示（排版可能如此，弱信号如实标注） |
| Paraphrase（DIPPER-11B） | 专训改写模型绕检测 | 全线大幅下降 | ⚠️ 无直接防线；n-gram 自查重可部分覆盖"改写既有文献"场景 |
| Repetition penalty 采样 | 生成端调参 | 全体检测器最多掉 32 点 | ❌ 检测侧无解，如实写入局限 |

## 5. 给不同读者的建议

- **论文作者**：交稿前跑 `audit_paper` + `verify_references --fail-on C`。自查的意义是把问题消灭在投稿前，而不是和学校/期刊的检测器博弈。
- **导师/编辑**：把 AI 分数当"待复核清单"，不当"判决书"。发现 tamper traces 时先约谈再定性——痕迹也可能是无害的复制粘贴残留。
- **机构管理者**：参考中国传媒大学"自主披露制"（《生成式人工智能使用情况说明表》）等制度设计，比单纯上检测系统更可持续。

## 6. 引用

1. Hans et al. *Spotting LLMs With Binoculars*. ICML 2024. arXiv:2401.12070
2. Bao et al. *Fast-DetectGPT*. ICLR 2024
3. Mitchell et al. *DetectGPT: Zero-Shot Detection using Probability Curvature*. ICML 2023
4. Dugan et al. *RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors*. ACL 2024. arXiv:2405.07940
5. Krishna et al. *Paraphrasing evades detectors of AI-generated text, but retrieval is an effective defense*. EMNLP 2023
6. Liang, Yuksekgonul, Zou et al. *GPT detectors are biased against non-native English writers*. Patterns, 2023
7. Weber-Wulff et al. *Testing of detection tools for AI-generated text*. Int J Educ Technol High Educ, 2023
8. Hu et al. *RADAR: Robust AI-Text Detection via Adversarial Learning*. NeurIPS 2023
9. Gehrmann et al. *GLTR: Statistical Detection and Visualization of Generated Text*. ACL 2019
10. Kirchenbauer et al. *A Watermark for Large Language Models*. ICML 2024
11. Sadasivan et al. *Can AI-Generated Text be Reliably Detected?* arXiv 2023
12. Alan Turing Institute. *Detecting AI-Generated Text: Informal Literature Review*. 2026-03
13. Nature. *AI-detection tools have made huge leaps forward — how good are they?* 2026-08
14. 新华社《名篇AI率也"超标"？论文AI率检测"误伤"引争议》2025-05；科学网《用AI打败AI，毕业论文AI检测靠谱吗？》2025-05
