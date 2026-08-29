# ScholarSeed 能力本体评估：实测、对标与升级路径

> 日期：2026-08-25 · 方法：真实样本对照实验 + 学术文献调研 + 产业界独立测评汇总
> 回答三个问题：①它到底能不能查出问题？②它的检测算法离学术界最优有多远？③有哪些已知的 AI 文本漏洞可以借鉴？

---

## 一、实测结论（本次评审做的对照实验）

用 CLI 直接跑了四组样本（`D:\Temp\User\opencode\sstest\`，可复现）：

| 样本 | 性质 | check_ai_signature 结果 | 判定 |
|---|---|---|---|
| `ai_en.md` | 典型 AI 味英文（均匀句长+"Moreover/Furthermore"+模板短语） | **71/100 高档**，抓出低起伏(CV=0.28)、4 个模板短语（带行号）、6/12 转折开头句 | ✅ 正确识别 |
| `human_en.md` | 人类风格（句长剧烈起伏、口语化） | **0/100 低档**，零告警 | ✅ 零误报 |
| `ai_zh.md` | AI 味中文（综上所述/值得注意的是/显然/无疑/p=0.000） | **41/100 中档**，抓出模板短语+低起伏 | ⚠️ 抓到但偏松 |
| `adversarial_en.md` | **LLM 写的、刻意规避表层特征**的文本（高句长起伏、零模板短语、带个人叙事） | **3/100 低档**，完全漏检 | ❌ 核心漏洞实锤 |

全量审计（audit_paper）对中文样本还正确抓出：
- `p=0.000` 应写 p<0.001 且缺检验方法名（统计造假红线）✅
- "显然""无疑"绝对化断言未对冲 ✅
- 缺 Abstract/Methods/Results 等章节、缺关键词行 ✅

**顺带发现一个真 bug**：审计报告中"统计诚信"一节重复渲染了两次。已记录待修。

### 结论一：能力边界（诚实版）

| 能力 | 现状 |
|---|---|
| 引文真实性核验（Crossref/S2/OpenAlex 实时比对） | **强**。这是全场独有且可作硬门禁的能力 |
| 确定性格式/结构/数字/统计红线检查 | **强**。规则可复现、证据带行号 |
| 典型 AI 文本（默认参数生成）的痕迹画像 | **中**。能抓"模板腔"，中文偏松 |
| 规避型 AI 文本（改句长节奏/去模板词/降AI工具处理过） | **弱**。表层统计特征可被完全绕开 |
| "能不能写作" | 写作=确定性模板骨架(render_template/outline) + 由 LLM agent 按 skills 知识库填充。工具层只负责防幻觉脚手架，**不生成正文内容是设计使然而非缺陷** |

---

## 二、学术界 SOTA 全景：检测方法四大流派

按原理分类（依据 ACL 2025 综述、图灵研究所 2026-03 综述）：

### 流派 1：水印法（Watermarking）
- 代表：Kirchenbauer et al. 2023（绿名单红名单）；Google DeepMind SynthID-Text（已在 Gemini 生产环境部署）
- 原理：生成时在 token 选择上埋统计偏置，检测时验证偏置
- **致命限制**：只有生成方（模型厂商）埋了水印才能验。检测第三方文本（ChatGPT/Claude 输出）无效 → ScholarSeed 场景基本不可用，但值得在文档中说明支持未来"水印验证"接口

### 流派 2：白盒概率法（需要拿到语言模型的 log-probability）⭐ 当前学术主流
| 方法 | 出处 | 核心思想 | 效果 |
|---|---|---|---|
| **GLTR** | Gehrmann et al., ACL 2019（Harvard/MIT） | 用 GPT-2 给每个词算排名，人类文本低频词排名分布不同 | 开山之作，可视化辅助人工 |
| **DetectGPT** | Mitchell et al., ICML 2023（Stanford） | 概率曲率：AI 文本位于模型对数概率函数局部极大值处，小扰动后概率必降 | 零样本开创性，但慢且不稳 |
| **Fast-DetectGPT** | Bao et al., ICLR 2024 | 条件概率曲率，用两个小模型（如 GPT-J + GPT-Neo）采样近似 | 比 DetectGPT 快 340 倍、AUROC 提升约 0.06-0.1 |
| **Binoculars** | Hans et al., 2024（UCSC 等） | 双望远镜：两个近缘模型（Falcon-7B 与其 Instruct 版）交叉困惑度之比，零训练 | **零样本 SOTA：0.01% 误报率下检出 90%+ ChatGPT 文本**；图灵所评测 DetectRL 上综合 0.796 居第一梯队 |
| LogRank / LRR / Perplexity | Ippolito 2020; GPTZero 初代 | 秩/困惑度统计 | 单指标易被"提升文采"提示绕过（Stanford Zou 组演示）|

### 流派 3：监督分类器（训练一个判别模型）
- Ghostbuster（Verma et al. 2023, Berkeley）、RADAR（Hu et al. 2023，检测器与改写器对抗联合训练，对同义词替换鲁棒）、ArgGPT、T5Sentinel、Wild detector
- 新一代商用引擎（Pangram、新版 GPTZero）本质是此类：**Pangram 自报英文误报率 0.0041%**，Epoch AI 独立测试 495 篇人类文本 0 误报，斯坦福 Karpinska 独立复测评价"whatever we threw at it, really really good"；Nature 2026-08 报道确认新一代已大幅超越初代
- 弱点：域外泛化差（训练没见过的模型/文体掉点严重）；RADAR 在 GPT-4o 文本上误报漏报激增

### 流派 4：检索增强防御
- Krishna et al. 2023（UMass-Amherst, "Paraphrasing evades detectors...but retrieval is an effective defense"）：改写可骗过所有检测器，但对候选源文库做检索比对可还原 → 与查重思路合流，**这正是 ScholarSeed 的 check_duplicates/self_plagiarism 思路在学术场景的正名**

### 关键负面结论（必须知道的边界）
1. **Weber-Wulff et al. 2023**（IJETHE，多机构联合测 14 个工具）：没有工具准确率超过 80%；更早的 Perkins et al. 测七款主流工具对 AI 文本平均识别率仅 **39.5%**
2. **Stanford Liang/Zou et al. 2023**（Patterns）：七个检测器对非英语母语者 TOEFL 作文误报率 **61.3%**（母语者≈0）→ 困惑度类指标系统性歧视二语写作者。**这对 ScholarSeed 是警示也是机会：check_ai_signature 不依赖困惑度，天然没有这个偏见，应在文档中显式宣传**
3. **Sadasivan et al. 2023 理论分析**：随着 LLM 接近人类分布，任何检测器的可达精度都存在理论上限——"检测军备竞赛长期看对防守方不利"

## 三、产业界现状与大学态度

| 产品 | 宣称 | 独立实测 |
|---|---|---|
| Turnitin | 98% 准确/<1% 误报 | 实际 ~84%；句子级误报 ~4%（官方承认），<20% 区间直接不给分 |
| GPTZero | 99% | Chicago Booth 受控基准 99.3% 召回/0.24% 误报；但某大学 200+ 真实提交测试 15% 误报；<500 词误报 8% |
| Pangram | 0.0041% 误报 | Epoch AI 独立验证 495 篇零误报，新一代最强 |
| Originality.ai / Copyleaks / ZeroGPT | 99%/99%/— | 独立测 76%/90.7%/无验证；混合内容与公式化文本是重灾区 |

**大学禁用潮**（可作为 ScholarSeed"hints-not-verdicts"立场的最佳论据）：Vanderbilt（算账：75,000 篇/年 × 1% = 750 名学生被冤枉，直接禁用）、Yale（2025 年有学生因 GPTZero 误判被停学而起诉）、UCLA、UC Berkeley、UCSD、Waterloo、Michigan State、Georgetown 均禁用或限制。

## 四、中文生态（与 ScholarSeed 最相关的战场）

- **玩家**：知网 AIGC 检测（2023.09 上线，输出"疑似生成比"）、万方文察（多要素一站式）、维普（70-80%轻度/80-90%中度/90%+重度三档）、格子达 3.0、PaperPass/PaperYY、有道学术猹、MitataAI、AIGC-X（人民网传播内容认知全国重点实验室+中科大，中文宣称>90%）
- **乱象**（新华社 2025-05 报道）：《荷塘月色》《滕王阁序》片段被判高 AI 率；同一篇论文 PaperYY 50%、PaperPass 70%、知网仅 5%；正文一字未改两小时前后 AI 特征 27.2%→0.5%
- **政策**：福州大学要求 AIGC≤20%；多校引入"AI 智评"ABCD 四级评级；《学术出版中AIGC使用边界指南》3.0、中国传媒大学《生成式人工智能使用情况说明表》（自主披露制）
- **"降AI"灰色产业链**：删逻辑词、书面语改口水话、同义替换——学生被迫"把自己的论文改笨"（科学网 2025-05 报道原话）

## 五、已知漏洞清单（RAID 基准，ACL 2024）及转化机会

RAID：600 万+生成样本、11 个模型、8 域、11 种黑盒攻击、12 个检测器横评。各检测器在不同攻击下掉点：

| 攻击 | 手法 | 对 SOTA 的杀伤 | ScholarSeed 可否转化为功能？ |
|---|---|---|---|
| Paraphrase（DIPPER-11B 改写） | 专训改写模型绕检测 | 全线大幅下降 | 部分：n-gram 重叠检查可留痕 |
| **Homoglyph 同形字符替换**（e→е 西里尔字母） | 肉眼不可见的字符替换 | Binoculars 79.6→**37.7**（-41.9）；五个检测器平均 -40.6 | ✅ **可以！异常 Unicode 字符是客观痕迹，纯正则/unicodedata 即可检测（stdlib 可实现）** |
| **Zero-width space 零宽空格插入** | 插入不可见字符 | 导致多个检测器输出全部翻转 | ✅ **同上，可检测** |
| Whitespace 异常空白 | 多余空格 | 多个检测器 -16 左右 | ✅ 可检测 |
| Synonym swap（BERT 同义词替换） | 词级替换 | Binoculars -36.1 | 部分：术语一致性检查可间接暴露 |
| Repetition penalty 采样 | 生成端调参即让全体检测器掉最多 32 点 | 无解（检测侧） | 不可转化，如实写入局限 |

### 由此得出的差异化洞察（本评估最重要的产品判断）

> **别去做"第 N 个 AI 检测器"——那条赛道连 Pangram 都只能宣称概率性结论。去做"AI 使用痕迹取证"：**
> 1. 降AI服务必然留下客观痕迹：零宽字符、同形字、异常空白、术语漂移、逻辑连接词密度骤变、口语化突变——这些全是**确定性可检测**的，正好落在 ScholarSeed 的技术射程内；
> 2. 这个定位完美避开误判陷阱（检测的是"处理痕迹"而非"是否 AI 所写"，不会冤枉人）；
> 3. 中文市场无人做这件事，知网/万方/维普都在卷概率分数，而国内降AI产业链规模巨大（每篇收费几十到几百元）。

---

## 六、可落地升级路线（按投入分层）

### A 层：零依赖即可做（stdlib，1-2 周/项）
1. **新工具 `check_tamper_traces`（防篡改痕迹检查）**：unicodedata 扫描零宽字符(U+200B/D/FEFF)、同形字映射表（西里尔/希腊↔拉丁）、异常空白模式 → 直接对应 RAID 三大攻击的"事后痕迹"
2. 中文模板短语词典扩充 + 分档阈值收紧（实测 41 分偏松）
3. 修复 audit_paper 报告"统计诚信"重复渲染 bug
4. 把上述学术结论写成 `docs/AI-DETECTION-LANDSCAPE.md` 用户指南：明确告知用户"什么能信、什么不能信"——这份诚实本身就是竞争力（竞品不敢写）

### B 层：可选 extras（需装 transformers/torch，或调 API）
5. ~~`scholarseed[detector]`：集成 Fast-DetectGPT 或 Binoculars~~
   **【已决策不做，v1.30.0】**——项目定位是确定性工具，不引入模型推理依赖。概率性检测与确定性取证的能力边界见 [AI-DETECTION-LANDSCAPE.md](AI-DETECTION-LANDSCAPE.md)
6. 对接 RAID 公开基准子集跑回归（stdlib 攻击子集已落地为 `benchmarks/adversarial_suite.py`，v1.29.0）
7. 构建 AI 阳性对照集（受控生成 50-100 篇），公开检出率——目前全行业只有 Pangram 敢公开此数

### C 层：不建议做
8. 训练自己的神经检测器（数据/算力/维护成本不成比例，且域外泛化差）
9. 水印检测（依赖生成方配合，当前无可行场景）
10. 任何"AI 率 XX%"式的单一判决性数字（Stanford/RAID/Vanderbilt 证据链表明这在科学上站不住，且是诉讼风险来源）

## 七、参考文献（核心 12 篇）

1. Hans et al. *Spotting LLMs With Binoculars*. ICML 2024. arXiv:2401.12070
2. Bao et al. *Fast-DetectGPT: Efficient Zero-Shot Detection via Conditional Probability Curvature*. ICLR 2024
3. Mitchell et al. *DetectGPT: Zero-Shot Detection using Probability Curvature*. ICML 2023
4. Gehrmann, Strobelt, Pfister. *GLTR: Statistical Detection and Visualization of Generated Text*. ACL 2019
5. Dugan et al. *RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors*. ACL 2024. arXiv:2405.07940
6. Krishna et al. *Paraphrasing evades detectors of AI-generated text, but retrieval is an effective defense*. EMNLP 2023
7. Liang, Yuksekgonul, Zou et al. *GPT detectors are biased against non-native English writers*. Patterns 2023
8. Weber-Wulff et al. *Testing of detection tools for AI-generated text*. Int J Educ Technol High Educ 2023
9. Verma et al. *Ghostbuster: Detecting Text Ghostwritten by Large Language Models*. 2023
10. Hu et al. *RADAR: Robust AI-Text Detection via Adversarial Learning*. NeurIPS 2023
11. Sadasivan et al. *Can AI-Generated Text be Reliably Detected?* arXiv 2023
12. Alan Turing Institute. *Detecting AI-Generated Text: Informal Literature Review*. 2026-03
13. Kirchenbauer et al. *A Watermark for Large Language Models*. ICML 2024
14. 新华社：《名篇AI率也"超标"？论文AI率检测"误伤"引争议》2025-05；科学网：《用AI打败AI，毕业论文AI检测靠谱吗？》2025-05；Nature: *AI-detection tools have made huge leaps forward — how good are they?* 2026-08
