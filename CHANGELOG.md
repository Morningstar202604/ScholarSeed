# Changelog

本项目所有重要变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

> 本文件自 v0.1.0 起重新开始计数：仓库于 2026-08-30 以"论文交付质检引擎与写作流水线"定位重置发布，此前的 v1.x 开发线（2026-08-19 ~ 2026-08-26）已完成其历史使命，不再在版本号中延续。v0.1.0 ~ v0.6.0 为同日连续发布。

## [0.7.0] - 2026-09-05

### Added

- **门禁塔架构（docs/ARCHITECTURE.md）**：把"生成与验证分离"哲学向下推导为九层信任塔——P 合法前提 / L0 文件底座 / L1 存在 / L2 契合 / L3 一致 / L4 方法 / L5 规范 / L6 表达 + 取证支柱 + 裁决引擎；证据等级随层递减、门禁资格跟着证据等级走。立**新工具准入测试**（归属层/失败类型/证据等级/门禁资格四问），答不出归属的工具不再准入——治理工具清单碎片化生长。
- **PaperIR 文档中间表示（scripts/paper_ir.py，L0 地基）**：文档只解析一次、全塔共享；共享行号辅助函数集中迁入（`_line_starts`/`_blank_fences`/`_split_sentences` 等名称语义不变），`iter_sentences` 返回行号（行号是全项目证据通货，`_blank_fences` 保行数不保字符位置）。
- **10 个新工具（41→51），逐层落地**：
  - P：`check_ethics_statements` 合法前提声明——伦理/知情同意、利益冲突、AI 使用披露（AIGC 合规）、数据可用性声明的存在性；涉人研究缺伦理声明为 error（桌拒红线），其余 warning。工具查"写了没有"，真伪归人。
  - L0：`check_encoding` 编码健康——U+FFFD 替换符与 (cid:NN) PDF 提取残留（error，文本不可读）、UTF-8 被 Latin-1 误读的乱码特征、异常控制字符、文中部 BOM。底座损坏时上层所有行号证据不可信。
  - L1：`check_retraction` 撤稿筛查（联网）——Crossref update-to / relation.is-retracted-by 与撤稿声明标题特征；引用撤稿成果=error（诚信硬伤）；网络失败按 X 级纪律 unverifiable（info）永不触发门禁。
  - L2：`check_claim_citation_fit` 引证契合（联网+缓存）——强主张句与所引文献标题/摘要的词汇重叠率过低时提示人工复核；`check_version_mismatch` 预印本-正式版错配（联网）——arXiv 条目已有正式发表版时提示更新。语义级"源文是否支持主张"明确不做（需模型推理）。
  - L3：`check_symbol_consistency` 一符一义——定义句建符号→含义映射，同一符号两种低相似含义=error，同一含义多符号=warning（equations-symbols.md 代码化）；`check_abstract_promises` 摘要承诺兑现——承诺对象在正文零词元命中才告警（宽松阈值防误报）。
  - L4：`check_rigor_declarations` 方法严谨声明完备性——触发场景（t 检验/ANOVA/回归/声称 RCT/发放问卷）核对声明在场：正态性、多重比较校正、效能/样本量、随机盲法、缺失数据；查"声明了没有"，不判"方法选对了没有"。
  - L5：`check_anonymization` 盲审匿名化（需显式 blind=true）——致谢/基金、自引指涉、LaTeX uthor 与 frontmatter 身份字段（error）、本机路径（info），"已隐去/masked"行豁免；`check_units` 计量单位写法一致性——同族单位混用（ml/mL、ug/µg、℃/°C），µ 的 U+00B5/U+03BC 两码位归同族。
- **gate_suite 离线门禁 19→24 道**（新增 encoding/ethics/symbol/abstract_promises/rigor/units）；`next_actions` 三条计划插入资格声明/撤稿筛查/契合与版本步骤；paper-writing 技能阶段 6/7/8 接线全部新门禁（并修复"残留取证"条目重复）。
- 新增 69 个回归测试（总数 237→306）。

### Changed

- README（en/zh）工具计数 41→51、门禁数与测试数同步；文档索引新增 ARCHITECTURE.md。

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
