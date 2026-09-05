---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_fe4baf379ba611f1a98a525400f8a581
    ReservedCode1: 3wnAsqQAHVAb5sV/RVsf48RV430eIpXR/4ZPOxXYblvxmeOHCBW2BDWjb0c/fN7V6K3hRJXso5v/ART5RwBHYXp7Rt/C5qn7YovM7158S3f+jMRzX4fOCHZdzDEgvatAwfuX2REX7rNDq+es5OHQtvcU0TI2WjgKdS3fd7G7HXeQeCLlLaXzBIxEyPo=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_fe4baf379ba611f1a98a525400f8a581
    ReservedCode2: 3wnAsqQAHVAb5sV/RVsf48RV430eIpXR/4ZPOxXYblvxmeOHCBW2BDWjb0c/fN7V6K3hRJXso5v/ART5RwBHYXp7Rt/C5qn7YovM7158S3f+jMRzX4fOCHZdzDEgvatAwfuX2REX7rNDq+es5OHQtvcU0TI2WjgKdS3fd7G7HXeQeCLlLaXzBIxEyPo=
---

# 引文格式指南

写作期正文统一用 `[作者, 年份]` 占位，成稿阶段转换为目标引文格式。

## GB/T 7714（中文论文默认）

期刊：作者. 题名[J]. 刊名, 年, 卷(期): 页码.
示例：张三, 李四. 大语言模型研究综述[J]. 计算机学报, 2024, 47(3): 1-25.

书籍：作者. 书名[M]. 版本. 出版地: 出版社, 出版年.
示例：王五. 深度学习[M]. 北京: 人民邮电出版社, 2023.

会议：作者. 题名[C]// 会议名. 出版地: 出版者, 年: 页码.
学位论文：作者. 题名[D]. 城市: 学校, 年.
网络资源：作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.

## APA 7（英文/心理学）

期刊：Author, A. A. (Year). Title of article. Journal Name, Vol(Issue), pages.
示例：Smith, J. (2024). Large language models in medicine. Nature Medicine, 30(1), 12-20.

书籍：Author, A. A. (Year). Title of book. Publisher.
网络：Author, A. A. (Year, Month Day). Title. Site. URL

## IEEE

[1] A. Author and B. Author, "Title," Journal Name, vol. X, no. Y, pp. Z, Year.
[2] A. Author, "Title," in Proc. Conf. Name, City, Country, Year, pp. Z.

## 注意事项

- 作者超过 3 人时，GB/T 用"等"，APA 用"et al."。
- 所有条目信息必须真实可核；无法核实的条目标注"待核实"，由用户补充原始出处。
- 同一篇论文只出现一次，编号后文不重复。
- **MLA（文学/文化研究）与 Chicago（历史学）**：`format_citation` 已支持 `style="mla"`（MLA 9）与 `style="chicago"`（书目格式），直接生成；期刊要求的脚注式 Chicago 引注在书目条目基础上手工调整。
- 法学界多使用《法学引注手册》/Bluebook：工具暂不支持，走手工路径——先用 `citation_verify` 核验存在性，再按引注手册排版。
- 中文文史哲引用古籍/档案时，Crossref 覆盖有限：以版本（刻本/影印本）、卷次、页码的纸本规范人工核对为准，工具结果仅供参考。

## 文献管理工具

- **Zotero**（免费开源，浏览器插件抓取文献元数据，团队协作）
- **EndNote**（老牌付费，期刊模板多）
- **NoteExpress**（中文支持好，适配知网）
- **Mendeley**（Elsevier 出品，PDF 管理）
- 建议：写作期正文用占位符，成稿阶段用文献管理软件按目标格式统一生成文献表。

## 引用伦理与学术不端红线

- **二次引用（转引）**：读到"甲引用了乙"时，尽量溯源到乙原文；确无法获取时标注"转引自"。
- **幽灵引用**：不得引用无法核验的文献（尤其防 AI 生成幻觉 DOI/标题）。
- 不得篡改文献的年份、卷期、页码；引用前核对原文。
- 引用他人图表需按版权要求取得授权。
- DOI 是文献的唯一稳定标识，优先用 DOI 定位原文。
- 一稿多投、重复发表属学术不端；转投其他期刊前需确认已撤稿。

## DOI 三重核对协议（提交前对每条含 DOI 的文献执行）

1. **可解析**：把 DOI 输入 `https://doi.org/<DOI>` 应能打开到目标页面；无法解析即为失效 DOI。
2. **卷期页码匹配**：在 Crossref（`https://api.crossref.org/works/<DOI>`）核对该条目的卷/期/页/年份，与引用条目完全一致；不一致说明张冠李戴（如引了同作者另一篇）。
3. **作者年份匹配**：核对作者列表与年份正确对应；重点警惕：同名作者多篇混用、预印本（preprint）与正式发表版本混用、书章节与期刊论文混用。

核对结论分级：**A 级**＝三项全过；**B 级**＝文献真实但细节待核实；**C 级**＝无证据须补来源。B/C 级禁止直接进文献表，必须核实到 A 级。
与 `paper-tools` 的 `literature_checklist` 配合使用：工具输出逐条分级清单，本协议为 DOI 专项核验动作。

## GB/T 7714 文献类型标识速查

| 标识 | 类型 | | 标识 | 类型 |
|------|------|-|------|------|
| [J] | 期刊 | | [D] | 学位论文 |
| [M] | 专著 | | [R] | 科技报告 |
| [C] | 会议论文 | | [S] | 标准 |
| [EB/OL] | 网络电子资源 | | [P] | 专利 |

## 格式转换流程

1. 确定目标载体（期刊/平台）的 style guide。
2. 将正文 `[作者, 年份]` 占位符批量转换为目标格式。
3. 核对每条文献的 DOI 与页码。
4. 用文献管理软件统一生成参考文献表，避免手工格式漂移；本插件内置等价工具——`format_citation(doi=..., style="apa"|"gbt"|"ieee"|"bibtex")` 按 Crossref 真实元数据直接产出规范条目，未核验通过不产出（防幻觉门禁），优先使用。

## 文献防幻觉三段核对（集成 nature-ref-verifier / ARS，落笔前提）

公开评测中主流大模型伪造/错引参考文献的比例约为两成到五成（随模型与领域波动），任何一条不过关都不落笔：

1. **存在性**：用 Crossref / Semantic Scholar 检索确认文献真实存在（标题+作者+年份+venue 至少四项精确匹配）；
2. **字段级交叉验证**：DOI 可解析且与 Crossref 元数据一致；卷期页码与 Crossref 比对无误引；作者年份与正文占位一致；同名作者不同人用 ORCID 区分；
3. **版本识别**：区分会议版/期刊版/预印本/同一标题多篇，用 DOI 唯一锁定，引用正式发表版。

无法验证 → 标记 `[待用户提供原始出处]`，禁止编造 DOI 补齐；正文全部落定后对文献表逐条重跑一遍验证再交付。

## 他引审计

- 引用计数 ≠ 领域认可：区分真实他引与自引/引用圈，高被引可能来自方法惯性而非验证；
- 引用"关键争议"必须回对立双方原始论文，不引二手转述充当立场；
- 被引数注明统计来源与时间（Google Scholar / Scopus / WoS 口径差异大）。
