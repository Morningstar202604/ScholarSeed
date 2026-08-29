# Changelog

本项目所有重要变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

> 本文件自 v0.1.0 起重新开始计数：仓库于 2026-08-30 以"论文交付质检引擎与写作流水线"定位重置发布，此前的 v1.x 开发线（2026-08-19 ~ 2026-08-26）已完成其历史使命，不再在版本号中延续。v0.1.0 ~ v0.6.0 为同日连续发布。

## [0.6.0] - 2026-08-30

### Added

- **`check_vague_attribution` 模糊归因检查（工具 40→41，gate_suite 门禁 18→19）**：句子向不具名的"研究表明/experts say/人们普遍认为"借权威却同句无任何引注时告警——这是文献公认 AI 文本"光润但空洞"（polished but vague）的核心特征（Kobak et al. 2024 词汇激增研究、Wikipedia "Signs of AI writing" 指南、refine.so 模糊归因分析均指向此类）。同句含 [1]/(Smith, 2020)/（王五，2021）/et al 即豁免，命中项需补引文或改为具体表述。
- **AI 模板短语词表 45→51**：依据调研补齐 in an era of / a plethora of / at its core / not just / fast-paced / game-changer 六条高频 AI 特征短语。
- 新增 3 个回归测试（总数 196→237）。

### Changed

- **许可证由 Apache-2.0 变更为 PolyForm Noncommercial 1.0.0**：学习、研究、个人使用与教育机构使用保持自由，商业使用需向维护者另行获取授权（见 LICENSE 文末联系渠道）。全部源文件头部与 README/CONTRIBUTING 同步更新。

### Decisions

- **检查器只要求"溯源落实"，不判断引文真伪**：真伪判断归 citation_verify（实时 API），归因检查只负责把"无据断言"暴露出来——两道独立的门禁职责分离。COPE 对"表层词汇误伤 ESL 写作者"的警示再次确认 hints-not-verdicts 立场。

## [0.5.0] - 2026-08-30

### Added

- **`check_references_completeness` 文献完整性（工具 36→40）**：逐条查缺年份/缺来源/缺卷期页、中文条目缺 GB/T 7714 类型标识、DOI 语法异常（注册符长度/含空格/标点截断）——编辑部第一道退回理由。
- **`check_references_recency` 文献时效性**：中位文献年龄与过时占比，全部或七成以上早于 10 年即提示综述陈旧。
- **`check_placeholders` 未完成痕迹**：TODO/FIXME/???/[citation needed]/待补充 等，交付前必须清零。
- **`check_links` 链接可信**：离线查占位域名（example.com/localhost）、非法 TLD、无主机名；live=true 联网 HEAD 验活（404/410 死链，403/405 反爬诚实降级为无法核验，上限 20 条）。
- **`check_numbers` 摘要-正文样本口径一致性**：摘要声明的样本数必须在正文再次出现（"摘要 250 人、方法 300 人"的经典编辑退回点）；存在性检查用数字否定环视（汉字与数字间无词边界）。
- **`check_stats` 不可能统计值**：相关系数 |r|>1 判 error，Cohen's d>5 判 warning（编造数据常见形态）。
- gate_suite 门禁数 13→18；新增 8 个回归测试。

## [0.4.0] - 2026-08-30

### Added

- **Persona 深度测评体系（benchmarks/persona_eval/）**：4 篇埋雷测试论文（Nature 风实证 / SSCI 管理学 / 中文核心 / AI 代写风，31 处已知缺陷）+ ground truth + 可复现评测器 run_eval.py。首发实测检测率 67%（21/31），据此修复后 31/31——测量驱动的补强闭环。
- **英文支持补全**：`check_numbers` 支持英文互斥分桶（"of whom ... while ..."）与 "a sample of N" 口径；`check_hedging` 英文绝对词（undoubtedly/proves that 等）逐条报告（此前只参与章节阈值）；overclaim 词表补 revolutioniz。
- 新增 6 个回归测试。

### Fixed

- gate_suite 门禁注册表补注册 references_format（未来年份此前在套件中不可见，两篇测试论文共同根因）。
- `check_duplicates` 删除标题行后再切句——标题文本黏进句片曾导致跨节英文重复整体漏检。
- `check_punctuation` 只扫正文——GB/T 7714 文献表的半角标点是合规写法，误扫单篇中文稿产生 8 条噪声。

## [0.3.0] - 2026-08-30

### Added

- **智能体动力原语（agent-native dynamics，工具 33→36）**：`next_actions`（计划路由：按 submission/thesis/polish 返回 工具/参数/通过条件 有序计划）、`gate_suite`（组合门禁：一次调用跑全部离线检查器，统一 pass 判定 + blocking 清单）、`audit_delta`（修复增量：前后两版差集 + 净改善判定，行号漂移不影响签名比对）。
- **`audit_paper` brief 模式**：fmt=json 时仅返回 ERROR 项与计数，适配智能体迭代循环的上下文经济。
- `paper-writing` 技能接线迭代回路；新增 8 个回归测试。

## [0.2.0] - 2026-08-30

### Added

- **核验分级新增 X 级（无法核验）**：网络不可达/限流此前被折叠成 C 级（"查无此文"），离线 CI 用 --fail-on C 会误拦全部文献；现在基础设施失败返回 X 并显式计数，永不触出门禁，HTTP 404 仍为 C。CLI 计数同步防未知等级崩溃。
- **英文与中文边界修复**：千分位数字（1,500）支持；中文紧邻 p 值（"表明p=0.000"）检测（ 词边界在汉字后失效）；`check_terms` 新增两种定义形态识别（"Anomaly Detection, AD" / "anomaly detection (AD)"）与 IT 豁免。

### Fixed

- **行号完整性（证据可信度的命门）**：check_ai_signature/check_tamper_traces/check_figures_tables 等对围栏代码块做破坏性剥离后行号整体漂移；统一改用保留换行数的 _blank_fences；check_stats/check_numbers 豁免代码块内容。
- verify_claims.py 工具计数去硬编码（v1.25 时代 32 已过期）；测试中两处未关闭文件句柄。

## [0.1.0] - 2026-08-30

**定位重置版**：从"学术防幻觉检测"转向"**论文交付质检引擎 + 写作流水线**"。核心判断：写作初稿已由大模型解决，"交得出去"才是学术写作的真实瓶颈——ScholarSeed 只做确定性可验证的那半边（引用核验、统计红线、结构格式、证据链留档），AI 腔检查降级为"润色自己稿子的自检 lint"，不再以"检测器"身份对外承诺。

### Added

- **写作流水线文档化**：README（en/zh）新增"写作流水线"章节——五项技能把工具串成 阶段→门禁→通过条件 的流水线，MCP 工具表按 实时核验/全文门禁/自检/复合审计 重新分组。
- **`check_numbers` 互斥分桶加和校验（partition_sum_overflow）**：段落级检测"总样本 N，其中 a…另外 b…"加和越界，带发放/回收流量豁免、总分层等和守卫、双命中关键词确认三重防误报——修复"300 名学生，其中 180…另外 200…"完全放行的真实漏检。
- **中文紧邻 p 值检测**：P_VALUE_PATTERN 弃用  词边界，改用否定环视；数值后环视防截断。
- `check_tamper_traces` 接入 paper-writing 技能交付阶段。
- 新增 8 个回归测试。

### Changed

- README（en/zh）按新定位全文重写：标语改为"证明可携带的论文流水线"，检测表述收敛为"写作自检，不是判决机器"，明确声明对规避文体的检出率未测、不宣称。
- plugin.json 描述与版本同步；verify_claims.py 校验口径更新。

### Decisions

- **不拆分为两个项目**：查错引擎（工具层）与写作流水线（技能编排层）是同一插件的引擎与控制器；插件单目录分发形态决定合一是最优解。
- **版本线重置为 0.1.0 重新计数**，语义化版本纪律不变。
