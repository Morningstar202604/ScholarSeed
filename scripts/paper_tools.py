#!/usr/bin/env python3
# Copyright 2026 ScholarSeed contributors
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE.
# Commercial use requires a separate license from the maintainers.
# ScholarSeed MCP stdio server: 本地论文工具。
# 纯标准库实现 JSON-RPC 2.0 over stdio，无第三方依赖。
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections import Counter
from pathlib import Path

from paper_ir import (
    _blank_fences,
    _count_cjk,
    _count_words_en,
    _extract_abstract,
    _find_pattern,
    _find_reference_heading,
    _line_starts,
    _pos_to_line,
    _split_body_references,
    _split_sentences,
    iter_sentences,
)

SERVER_NAME = "paper-tools"


def _load_version() -> str:
    """版本号单一来源：从仓库根目录 plugin.json 动态读取，禁止在代码中硬编码。"""
    plugin_json = Path(__file__).resolve().parent.parent / "plugin.json"
    try:
        return str(json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "0.0.0"))
    except (OSError, ValueError):
        return "0.0.0"


VERSION = _load_version()

# 外部验证/检索 API（均无需 API key，公开接口）
CROSSREF_API = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_API = "https://api.openalex.org/sources"
API_TIMEOUT = 15  # 秒

# 期刊类型 -> 目标篇幅与说明（供 render_template 输出篇幅规划）
JOURNAL_PROFILES = {
    "top_conceptual": {
        "label": "SSCI 顶刊概念/理论论文（如 Human Resource Management Review）",
        "total": "8000-10000 词（正文含摘要与命题，不含参考文献）",
        "by_section": {
            "Abstract": "250-300 词",
            "Introduction": "1000-1200 词",
            "Theoretical foundations": "1500-1800 词",
            "Framework": "1500-2000 词",
            "Propositions": "1500-2000 词",
            "Discussion": "1200-1500 词",
            "Conclusion": "300-400 词",
        },
        "note": "概念论文重理论贡献、构念新颖度与命题可检验性；需给出可追溯的理论根基与边界条件。",
    },
    "top_empirical": {
        "label": "SSCI 顶刊实证论文（如 The International Journal of Human Resource Management）",
        "total": "8000-10000 词（正文，不含参考文献）",
        "by_section": {
            "Abstract": "250-300 词",
            "Introduction": "800-1000 词",
            "Theory & hypotheses": "2000-2500 词",
            "Methods": "1500-2000 词",
            "Results": "1500-2000 词",
            "Discussion": "1500-2000 词",
            "Conclusion": "300-400 词",
        },
        "note": "实证论文需完整报告样本、测度信效度、稳健性检验与伦理审批；显著结果须附效应量与稳健性说明。",
    },
    "general": {
        "label": "一般期刊/会议",
        "total": "4000-6000 词（正文）",
        "by_section": {
            "Abstract": "150-250 词",
            "Introduction": "600-800 词",
            "Main body": "2500-3500 词",
            "Conclusion": "300-400 词",
        },
        "note": "篇幅适中，重完整性与清晰度。",
    },
}


def _journal_plan(journal: str | None) -> str:
    """生成目标篇幅规划文本；未指定期刊时返回空字符串。"""
    if not journal:
        return ""
    profile = JOURNAL_PROFILES.get(journal.strip().lower())
    if not profile:
        return f"\n> ⚠️ 未知期刊类型 '{journal}'，可用: {', '.join(JOURNAL_PROFILES)}。未附加篇幅规划。\n"
    lines = [
        "",
        f"> 【目标篇幅 · {profile['label']}】",
        f"> 全篇: {profile['total']}",
    ]
    for section, target in profile["by_section"].items():
        lines.append(f"> - {section}: {target}")
    lines.append(f"> 提示: {profile['note']}")
    lines.append("")
    return "\n".join(lines)


def render_template(genre: str, journal: str | None = None) -> str:
    """按体裁返回 Markdown 文章模板；可指定目标期刊类型以附加篇幅规划。"""
    genre = (genre or "survey").strip().lower()
    templates = {
        "survey": """# {标题}

> 摘要：研究背景；已有工作梳理；关键问题；本文结论。

## 1. 引言
- 背景与研究意义
- 已有工作的现状与局限
- 本文目的与贡献

## 2. 领域核心概念与分类

## 3. 代表方法与工作
### 3.1 {方法一}
### 3.2 {方法二}

## 4. 方法与工作对比
| 方法 | 核心思想 | 优势 | 局限 |

## 5. 关键问题与挑战

## 6. 未来研究方向

## 7. 结论

## 参考文献
""",
        "empirical": """# {标题}

> 摘要（结构化）：目的 / 方法 / 结果 / 结论。

## 1. 引言
- 问题提出
- 相关文献
- 研究假设

## 2. 方法
### 2.1 样本与数据
### 2.2 实验设计
### 2.3 指标与分析方法

## 3. 结果
### 3.1 描述性结果
### 3.2 假设检验

## 4. 讨论
### 4.1 结果解读
### 4.2 与已有文献对照
### 4.3 局限

## 5. 结论

## 参考文献
""",
        "tech": """# {标题}

> 一句话摘要：解决什么问题，怎么解决。

## 背景与动机

## 方案设计

## 关键实现

## 效果与数据

## 局限与后续

## 参考链接
""",
        "thesis": """# {标题}

> 摘要：研究背景；研究问题；研究方法；主要结论；创新点。

## 第 1 章 绪论
- 研究背景与意义
- 国内外研究现状与缺口
- 研究内容、方法与技术路线
- 论文组织结构

## 第 2 章 相关理论基础

## 第 3 章 {核心研究内容一}

## 第 4 章 {核心研究内容二}

## 第 5 章 实验/验证与分析

## 第 6 章 总结与展望
- 工作总结
- 创新点
- 不足与展望

## 参考文献
""",
        "argumentative": """# {标题}

> 摘要：争议问题；本文立场；核心论证路径；理论意涵。

## 一、问题的提出
- 现象/争议与本文要回答的问题
- 既有讨论的脉络与本问题的位置

## 二、概念界定与分析框架
- 核心概念的操作性界定
- 论证框架与评判标准

## 三、论证主体
### 3.1 论据一：{文本/史料/义理依据}
### 3.2 论据二：{进一步论证}
### 3.3 论据三：{辅助论证}

## 四、对主要反驳的回应
- 可能的反驳一及其回应
- 可能的反驳二及其回应

## 五、结论与限度
- 立场重述与理论/实践意涵
- 论证限度和待决问题

## 参考文献
""",
    }
    return templates.get(genre, templates["survey"]).lstrip() + _journal_plan(journal)


def word_count(markdown: str, source_format: str = "markdown") -> dict:
    """统计去除标记后的中文字符数、词数与代码块数。source_format 可选 latex。"""
    markdown = _maybe_latex(markdown, source_format)
    code_blocks = len(re.findall(r"```", markdown)) // 2
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    text = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", text)  # 链接/图片
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[#>*`_~\-|]+", " ", text)
    chars = _count_cjk(text)
    words = _count_words_en(text)
    return {"chars": chars, "words": words, "code_blocks": code_blocks}


def literature_checklist(markdown: str) -> str:
    """从论文参考文献段生成逐条核验清单（A/B/C 分级 + DOI 与格式提醒）。"""
    if not markdown:
        return "输入为空：未提供论文文本。"
    # 截取参考文献段
    ref_match = _find_reference_heading(markdown)
    body = markdown[ref_match.end() :].strip() if ref_match else markdown.strip()
    refs = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    # 只保留看起来像参考文献条目的行（含 4 位年份）
    entries = []
    for ln in refs:
        if re.search(r"\((?:19|20)\d{2}\)|(?:19|20)\d{2}[.,;:]", ln):
            entries.append(ln)
    if not entries:
        return (
            "未在文本中识别到含年份的参考文献条目。\n"
            "若确已有参考文献，请确认使用 APA/GB-T 等含年份的引用格式，"
            "或手动按 A/B/C 分级核对每条：\n"
            "A=检索直接命中完整出处；B=文献真实存在但 DOI/卷期待核实；C=无证据，需补来源。"
        )
    lines = [
        f"共识别到 {len(entries)} 条参考文献，请逐条按下表核验后提交：",
        "",
        "| # | 条目 | 核验状态(A/B/C) | DOI(已核实/待核实/无) | 备注 |",
        "|---|------|----------------|----------------------|------|",
    ]
    for i, entry in enumerate(entries, 1):
        entry_short = entry if len(entry) <= 80 else entry[:77] + "..."
        entry_short = entry_short.replace("|", "\\|")  # 转义竖线，防止破坏 Markdown 表格
        lines.append(f"| {i} | {entry_short} | A/B/C | 已核实/待核实/无 | |")
    lines += [
        "",
        "## 铁律提醒（提交前必读）",
        "1. 严禁伪造或美化参考文献、作者、卷期页码与 DOI；不确定的条目必须标 B 级并在投稿前到期刊数据库核实。",
        "2. A 级 = 检索结果直接命中完整出处（含 DOI）；B 级 = 文献真实存在但出处细节凭知识补充，须核实；C 级 = 无证据，须补原始来源。",
        "3. 正文引文与参考文献表必须一一对应（引用伦理），格式统一为 APA 7 / GB/T 7714 / IEEE 之一。",
        "4. 投稿前须增补目标期刊近 2 年相关文献，避免时效性被审稿人诟病。",
        "5. DOI 三重核对（提交前对每条含 DOI 的文献）：① 可解析——DOI 能打开到目标页面；② 卷期页码匹配——与 Crossref 元数据一致；③ 作者年份匹配——警惕同名多篇与预印本/书章节混淆。",
    ]
    return "\n".join(lines)


def submission_checklist(journal: str = "", topic: str = "") -> str:
    """生成投稿前检查清单（期刊匹配/署名/材料/伦理/文献核实）。"""
    j = journal.strip() or "（待定目标期刊）"
    t = topic.strip() or "（论文主题）"
    return f"""# 投稿前检查清单

论文主题: {t}
目标期刊: {j}

## 1. 目标期刊匹配（五维评估）
- [ ] 理论/方法贡献与期刊定位一致（可参考 journal-matching.md）
- [ ] 已通读该刊近 2 年同类文章，确认选题与写法对齐
- [ ] 确认期刊类型：概念论文 / 实证 / 综述 / 短评，并据此匹配篇幅与结构
- [ ] 字数与格式符合投稿指南（可用 render_template(journal=...) 获取篇幅规划）
- [ ] 一稿多投红线：确认未同时投往其他刊物

## 2. 作者与署名
- [ ] 作者名单、顺序与贡献说明（对照 ICMJE 署名四标准：实质贡献/起草或审改/最终批准/可担责）
- [ ] 通讯作者信息与 ORCID

## 3. 必备材料
- [ ] Cover Letter（5 段式：期刊与稿件信息/核心贡献/与期刊匹配/无冲突声明/推荐审稿人）——参考 cover-letter.md
- [ ] 摘要与关键词符合期刊要求
- [ ] 图表规范（caption、分辨率、可读性）——参考 figures-tables.md
- [ ] 数据可用性 / 补充材料说明

## 4. 伦理与合规
- [ ] 利益冲突声明（COI）
- [ ] 伦理审批（涉人研究）或豁免说明
- [ ] AI 使用披露（生成式 AI 辅助写作的声明方式符合期刊政策）
- [ ] 重复发表/一稿多投自查

## 5. 文献最终核验（投稿前必做）
- [ ] 逐条核对参考文献：DOI、卷期页码、作者拼写（用 literature_checklist 生成清单）
- [ ] B 级条目（凭知识补充的 DOI/出处）已到数据库核实
- [ ] 增补目标期刊近 2 年文献

## 6. 提交执行
- [ ] 按投稿系统逐项填写元信息
- [ ] 保留投稿确认邮件与稿件编号
- [ ] 记录投稿日期以便后续返修跟进
"""


def check_structure(markdown: str, source_format: str = "markdown") -> dict:
    """校验标题层级是否连续（不跳级）。支持 markdown / latex 两种源格式。"""
    if not markdown:
        return {"ok": True, "issues": [], "headings": []}
    markdown = _maybe_latex(markdown, source_format)
    prose = _blank_fences(markdown)
    headings = []
    for line in prose.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if m:
            headings.append({"level": len(m.group(1)), "title": m.group(2).strip()})
    issues = []
    prev = 0
    for h in headings:
        if prev and h["level"] > prev + 1:
            issues.append({"type": "skipped_level", "severity": "warning", "detail": f"标题跳级: '{h['title']}' 为 H{h['level']}, 前一个为 H{prev}"})
        prev = h["level"]
    if not headings:
        issues.append({"type": "no_headings", "severity": "warning", "detail": "未检测到任何标题"})
    return {"ok": not issues, "issues": issues, "headings": headings}


def generate_outline(topic: str, genre: str = "empirical") -> str:
    """基于研究问题与体裁生成结构化论文大纲。"""
    topic = (topic or "未命名主题").strip()
    genre = (genre or "empirical").strip().lower()
    if genre == "survey":
        return f"""# {topic}：综述大纲

> 一句话定位：覆盖 __ 主题的现状、对比与缺口。

## 1. 引言
- 背景与意义：为什么该主题重要
- 已有综述/工作概览
- 本文综述范围、检索方法与贡献

## 2. 核心概念与分类体系

## 3. 方法/工作全景（按时间线或维度展开）
### 3.1 阶段/维度一
### 3.2 阶段/维度二

## 4. 对比分析
| 维度 | 代表工作 | 核心思想 | 优势 | 局限 |

## 5. 关键挑战与开放问题

## 6. 未来研究方向

## 7. 结论

## 参考文献
""".lstrip()
    if genre == "tech":
        return f"""# {topic}：技术文章大纲

> 一句话摘要：解决什么问题，怎么解决，效果如何。

## 背景与动机
- 问题场景
- 痛点与已有方案不足

## 方案设计
- 核心思路
- 架构/流程
- 关键取舍

## 关键实现
- 技术要点
- 代码/配置片段

## 效果与数据
- 量化结果
- 对比

## 局限与后续

## 参考链接
""".lstrip()
    if genre == "argumentative":
        return f"""# {topic}：论证体大纲

> 争议问题：{topic}；本文立场：一句话可证伪的论点。

## 一、问题的提出
- 争议现象与问题缘起
- 既有讨论梳理与本问题的位置

## 二、概念界定与分析框架
- 核心概念操作性定义
- 论证框架与评判标准

## 三、论证主体
- 论据一（文本/史料/义理依据）
- 论据二（递进论证）
- 论据三（辅助论证）

## 四、对主要反驳的回应
- 反驳一及其回应
- 反驳二及其回应

## 五、结论与限度
- 立场重述与意涵
- 论证限度与待决问题

## 参考文献
""".lstrip()
    if genre == "thesis":
        return f"""# {topic}：学位论文大纲

> 学位论文类型：请说明硕士/博士/本科；总体目标与主要贡献。

## 第 1 章 绪论
- 研究背景与意义
- 国内外研究现状与缺口（综述归纳）
- 研究内容、方法与技术路线
- 论文组织结构

## 第 2 章 相关理论基础

## 第 3 章 核心研究内容一
- 问题建模
- 关键设计

## 第 4 章 核心研究内容二
- 问题建模
- 关键设计

## 第 5 章 实验/验证与分析
- 实验设置（数据/环境/基线）
- 结果展示
- 分析与讨论

## 第 6 章 总结与展望
- 工作总结
- 创新点凝练
- 不足与展望

## 参考文献
""".lstrip()
    return f"""# {topic}：实证论文大纲

> 研究问题（PICOT 四要素）：对象 / 干预或输入 / 结果 / 范围时间

## 1. 引言
- 研究问题与动机
- 背景与相关文献
- 研究假设
- 贡献总结

## 2. 相关工作
- 方法类相关工作
- 场景类相关工作
- 与本文的差异

## 3. 方法
### 3.1 数据与样本
### 3.2 实验设计
### 3.3 指标与分析方法

## 4. 结果
### 4.1 描述性结果
### 4.2 假设检验
### 4.3 稳健性检验

## 5. 讨论
### 5.1 结果解读
### 5.2 与已有文献对照
### 5.3 局限与伦理考量

## 6. 结论

## 参考文献
""".lstrip()


# 投稿匹配期刊库：数据外置于 data/journals.json，用户可直接编辑扩充，无需改代码。
def _load_journals() -> list:
    path = Path(__file__).resolve().parent.parent / "data" / "journals.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


JOURNAL_DB = _load_journals()


def journal_matcher(topic: str, paper_type: str = "conceptual") -> str:
    """按论文主题关键词与类型推荐候选期刊，输出匹配度评分与理由。"""
    topic = (topic or "").strip()
    paper_type = (paper_type or "conceptual").strip().lower()
    if not topic:
        return "未提供论文主题。请传入 topic（论文主题/关键词），paper_type 可选：conceptual(概念) / empirical(实证) / review(综述)，默认 conceptual。"
    tokens = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9-]*", topic)}
    scored = []

    def _stem(w: str) -> str:
        return w[:-1] if w.endswith("s") else w

    def _term_match(token: str, domain: str) -> bool:
        """词干级匹配：全等，或长词(≥4字符)的前缀匹配。

        替代旧的双向子串匹配——子串会把 "training" 误命中领域 "ai"。
        """
        t, d = _stem(token), _stem(domain)
        if t == d:
            return True
        return (len(d) >= 4 and t.startswith(d)) or (len(t) >= 4 and d.startswith(t))

    for j in JOURNAL_DB:
        score = 0
        type_ok = paper_type in j["type"]
        if type_ok:
            score += 3
        elif paper_type == "conceptual" and "conceptual" in j["type"]:
            score += 2
        hits = [d for d in j["domains"] if any(_term_match(t, d) for t in tokens)]
        score += min(len(hits) * 2, 6)
        scored.append((score, hits, j))
    scored.sort(key=lambda x: (-x[0], x[2]["name"]))
    lines = [
        "# 投稿期刊匹配建议",
        "",
        f"论文主题: {topic}",
        f"论文类型: {paper_type}",
        "",
        "> 说明：匹配度为基于主题关键词与期刊定位的启发式评估，供投稿方向参考；分区与政策以期刊官网为准。",
        "",
        "| 期刊 | 匹配度 | 定位 | 主题命中 | 篇幅参考 | 投稿提示 |",
        "|------|--------|------|----------|----------|----------|",
    ]
    for score, hits, j in scored[:8]:
        level = "高" if score >= 7 else ("中" if score >= 4 else "低")
        hit_str = ", ".join(hits) if hits else "—"
        lines.append(f"| {j['name']} | {level}({score}) | {j['position']} | {hit_str} | {j['length']} | {j['note']} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 外部 API 工具（纯标准库 urllib，零第三方依赖）
# ---------------------------------------------------------------------------

TITLE_SIMILARITY_THRESHOLD = 0.85  # 按标题核验时的最低相似度，低于此值判定为"未命中同一文献"
TITLE_SEARCH_ROWS = 3  # 标题检索返回候选数，取相似度最高者而非盲取第一条


def _normalize_title(title: str) -> str:
    """标题归一化：小写、仅保留字母数字，供相似度比较。"""
    return "".join(ch.lower() for ch in title if ch.isalnum())


def _title_similarity(a: str, b: str) -> float:
    """两标题的归一化相似度（0-1）。任一为空返回 0。"""
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _crossref_headers() -> dict:
    return {"User-Agent": f"scholarseed/{VERSION} (mailto:scholarseed@example.com)"}


RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = 1.0

# 磁盘缓存：同一 URL 的 GET 结果在 TTL 内直接复用（省配额、加速批量核验）。
# TTL 秒数可用环境变量 SCHOLARSEED_CACHE_TTL 覆盖，设为 0 禁用。
CACHE_DIR = Path(tempfile.gettempdir()) / "scholarseed-cache"
CACHE_TTL = int(os.environ.get("SCHOLARSEED_CACHE_TTL", "86400"))
CACHE_MAX_FILES = 500  # 缓存文件数上限，超出时清理最旧一半


def _cache_key(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def _cache_get(url: str) -> dict | None:
    if CACHE_TTL <= 0:
        return None
    path = _cache_key(url)
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - cached["ts"] <= CACHE_TTL:
            return cached["data"]
    except (OSError, ValueError, KeyError):
        pass
    return None


def _cache_put(url: str, data: dict) -> None:
    if CACHE_TTL <= 0:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_key(url).write_text(json.dumps({"ts": time.time(), "data": data}), encoding="utf-8")
        # 防膨胀：超过上限时清理最旧的一半缓存文件
        files = sorted(CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if len(files) > CACHE_MAX_FILES:
            for old in files[: len(files) // 2]:
                old.unlink(missing_ok=True)
    except OSError:
        pass  # 缓存写入失败不影响主流程


def _fetch_json(url: str, headers: dict | None = None, retries: int = 1) -> dict:
    """GET 并解析 JSON；带磁盘缓存与 429/5xx 指数退避重试（默认重试 1 次）。

    Crossref / Semantic Scholar 在限流与瞬时故障时返回这些状态码，
    单次失败即放弃会把可恢复错误当成"文献不存在"，污染核验结论。
    """
    hit = _cache_get(url)
    if hit is not None:
        return hit
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            _cache_put(url, data)
            return data
        except urllib.error.HTTPError as e:
            if e.code in RETRYABLE_HTTP_CODES and attempt < retries:
                last_exc = e
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
        except Exception as e:
            if attempt < retries:
                last_exc = e
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    raise last_exc if last_exc else RuntimeError("unreachable")


def _crossref_by_doi(doi: str) -> dict:
    """通过 Crossref API 按 DOI 核验文献存在性并返回元数据。"""
    if not doi or not doi.strip():
        return {"verified": False, "doi": doi, "note": "DOI 为空"}
    doi = doi.strip()
    url = f"{CROSSREF_API}/{urllib.parse.quote(doi, safe='')}"
    try:
        data = _fetch_json(url, headers=_crossref_headers())
        return _parse_crossref_message(data.get("message", {}), doi)
    except urllib.error.HTTPError as e:
        if e.code in RETRYABLE_HTTP_CODES:
            # 限流/服务端故障：无法核验 ≠ 查无此文，标 X 级避免污染门禁
            return {"verified": False, "doi": doi, "unverifiable": True, "note": f"Crossref 暂不可达 (HTTP {e.code})，无法核验"}
        return {"verified": False, "doi": doi, "note": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"verified": False, "doi": doi, "unverifiable": True, "note": f"网络不可达：{e}"}


def _crossref_by_title(title: str) -> dict:
    """通过 Crossref API 按标题检索文献。

    返回候选中归一化标题相似度最高的一条；若最高相似度低于
    TITLE_SIMILARITY_THRESHOLD，判定 verified=False（防止把同名/近题论文误当命中）。
    """
    if not title or not title.strip():
        return {"verified": False, "title": title, "note": "标题为空"}
    params = urllib.parse.urlencode({"query.title": title.strip(), "rows": TITLE_SEARCH_ROWS})
    url = f"{CROSSREF_API}?{params}"
    try:
        data = _fetch_json(url, headers=_crossref_headers())
        items = data.get("message", {}).get("items", [])
        if not items:
            return {"verified": False, "title": title.strip(), "similarity": 0.0, "note": "未找到匹配文献"}
        best = max(items, key=lambda it: _title_similarity(title, ((it.get("title") or [""])[0])))
        best_title = (best.get("title") or [""])[0]
        similarity = round(_title_similarity(title, best_title), 4)
        if similarity < TITLE_SIMILARITY_THRESHOLD:
            return {
                "verified": False,
                "title": title.strip(),
                "closestMatch": best_title,
                "similarity": similarity,
                "note": (f"最接近候选《{best_title}》相似度 {similarity} 低于阈值 {TITLE_SIMILARITY_THRESHOLD}，不能确认为同一文献"),
            }
        result = _parse_crossref_message(best, None)
        result["similarity"] = similarity
        return result
    except urllib.error.HTTPError as e:
        if e.code in RETRYABLE_HTTP_CODES:
            return {"verified": False, "title": title.strip(), "unverifiable": True, "note": f"Crossref 暂不可达 (HTTP {e.code})，无法核验"}
        return {"verified": False, "title": title.strip(), "note": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"verified": False, "title": title.strip(), "unverifiable": True, "note": f"网络不可达：{e}"}


def _parse_crossref_message(msg: dict, fallback_doi: str | None) -> dict:
    """将 Crossref API 返回的 message 对象解析为标准化输出。"""
    doi = msg.get("DOI", fallback_doi) or ""
    titles = msg.get("title", []) or []
    authors = []
    authors_structured = []
    for a in msg.get("author", []) or []:
        given = a.get("given", "")
        family = a.get("family", "")
        authors.append(f"{given} {family}".strip() if given and family else (given or family))
        if family or given:
            authors_structured.append({"family": family, "given": given})
    container = msg.get("container-title", []) or []
    journal = container[0] if container else ""
    date_parts = (msg.get("published-print", {}) or msg.get("published-online", {}) or msg.get("issued", {}) or {}).get("date-parts", [[None]])[0]
    year = date_parts[0] if date_parts and date_parts[0] else None
    return {
        "verified": True,
        "doi": doi,
        "title": titles[0] if titles else "",
        "authors": authors,
        "authorsStructured": authors_structured,
        "journal": journal,
        "volume": msg.get("volume", "") or "",
        "issue": msg.get("issue", "") or "",
        "pages": msg.get("page", "") or "",
        "year": year,
        "publisher": msg.get("publisher", "") or "",
        "type": msg.get("type", "") or "",
        "url": f"https://doi.org/{doi}" if doi else "",
    }


def _check_cite_keys(tex: str) -> dict:
    r"""LaTeX 源的引用核对：比对 \cite 键与 \bibitem 键的双向覆盖。

    文本型核对（作者-年份/[n]）在 LaTeX 转换后不可用——\cite 已变 [CITE] 占位，
    参考文献表由 \bibitem 生成；此函数在原始 tex 上做键级比对。
    """
    cite_keys = set()
    bib_keys = set()
    for m in re.finditer(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^{}]*)\}", tex):
        for k in m.group(1).split(","):
            k = k.strip()
            if k:
                cite_keys.add(k)
    for m in re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^{}]*)\}", tex):
        bib_keys.add(m.group(1).strip())
    # 正文引用位于 \input 子文件中时（多文件工程常见），同样诚实降级
    if not cite_keys and bib_keys:
        return {
            "ok": True,
            "issues": [
                {
                    "type": "cites_in_subfiles",
                    "severity": "info",
                    "detail": f"检测到 {len(bib_keys)} 个 \\bibitem，但主文件无 \\cite 命令（正文引用可能位于 \\input 子文件），已跳过键级核对；请合并全部子文件后重测",
                }
            ],
            "mode": "latex-keys",
            "entries": len(bib_keys),
        }
    # BibTeX 外挂数据库工作流：\bibliography{db} + 编译期生成条目，
    # 源码里没有完整 \bibitem -> 键级比对不可用，诚实降级
    uses_bibtex = bool(re.search(r"\\bibliography\s*\{", tex))
    if uses_bibtex and (not bib_keys or len(cite_keys - bib_keys) >= max(3, len(cite_keys) // 2)):
        return {
            "ok": True,
            "issues": [{"type": "bibtex_external", "severity": "info", "detail": "检测到 \\bibliography 外部文献数据库工作流，键级核对需要编译后的 .bbl 内容；已跳过"}],
            "mode": "latex-keys",
            "entries": len(bib_keys),
        }
    # 参考文献在独立 .bbl 中时（单文件输入常见），键级比对不可用——诚实降级
    if not bib_keys and cite_keys:
        return {
            "ok": True,
            "issues": [{"type": "bbl_external", "severity": "info", "detail": f"检测到 {len(cite_keys)} 个 \\cite 键，但未提供 \\bibitem（参考文献可能位于独立 .bbl 文件），已跳过键级核对"}],
            "mode": "latex-keys",
            "entries": 0,
        }
    issues = []
    for k in sorted(cite_keys - bib_keys):
        issues.append({"type": "citation_missing_entry", "severity": "error", "detail": f"\\cite 键 '{k}' 在 \\bibitem 中不存在"})
    for k in sorted(bib_keys - cite_keys):
        issues.append({"type": "entry_never_cited", "severity": "warning", "detail": f"\\bibitem '{k}' 未被任何 \\cite 引用"})
    return {"ok": not issues, "issues": issues, "mode": "latex-keys", "entries": len(bib_keys)}


def _author_matches(expected: str, actual_authors: list) -> bool:
    """期望作者串（逗号/分号分隔）中每个姓氏是否都出现在返回作者列表中。"""
    expected_names = [p.strip().lower() for p in re.split(r"[,;，；]", expected) if p.strip()]
    if not expected_names:
        return False
    joined = " | ".join(str(a).lower() for a in actual_authors)
    return all(name in joined for name in expected_names)


def _lookup_reference(doi: str = "", title: str = "") -> dict:
    """按 DOI（优先）或标题查找文献元数据；两者皆空返回未验证结果。"""
    if doi and doi.strip():
        return _crossref_by_doi(doi)
    if title and title.strip():
        return _crossref_by_title(title)
    return {"verified": False, "note": "请提供 DOI 或标题，至少一项"}


def _apply_grade(result: dict, title: str = "", authors: str = "", year: int = 0) -> dict:
    """就地为核验结果添加 fieldChecks 与 A/B/C/X 分级，返回同一 dict。

    分级口径：A=存在且提供的期望字段全部匹配；B=存在但字段不匹配；
    C=未找到/不可确认；X=网络不可达/限流等基础设施原因无法核验。
    X 与 C 必须区分：把"我没查成"当成"查无此文"会在离线环境误拦门禁。
    """
    field_checks: dict = {"title": None, "authors": None, "year": None}
    if result.get("unverifiable"):
        result["grade"] = "X"
    elif result.get("verified"):
        if title and title.strip():
            field_checks["title"] = _title_similarity(title, str(result.get("title", ""))) >= TITLE_SIMILARITY_THRESHOLD
        if authors and authors.strip():
            field_checks["authors"] = _author_matches(authors, result.get("authors", []))
        if year and int(year) > 0:
            field_checks["year"] = result.get("year") == int(year)
        provided = [v for v in field_checks.values() if v is not None]
        result["grade"] = "A" if all(provided) else "B"
    else:
        result["grade"] = "C"
    result["fieldChecks"] = field_checks
    return result


def citation_verify(doi: str = "", title: str = "", authors: str = "", year: int = 0) -> str:
    """按 DOI 或标题核验文献存在性，返回格式化结果与 A/B/C 分级。

    - 优先 DOI 精确核验；无 DOI 时按标题检索（相似度阈值防误配）。
    - 提供 authors/year 时执行字段级交叉验证。
    - 分级：A=存在且提供的期望字段全部匹配；B=存在但字段不匹配或无法比对；
      C=未找到/不可确认；X=网络不可达/限流，无法核验（不计入门禁失败，
      联网后重跑）。与 literature_checklist 的 A/B/C 口径一致。
    """
    if not (doi and doi.strip()) and not (title and title.strip()):
        return json.dumps({"verified": False, "grade": "C", "note": "请提供 DOI 或标题，至少一项"}, ensure_ascii=False, indent=2)
    result = _apply_grade(_lookup_reference(doi, title), title, authors, year)
    return json.dumps(result, ensure_ascii=False, indent=2)


# 贪婪匹配到空白为止，尾部标点/括号交给 _clean_doi 清理。
# 注意：不能用惰性量词（\S+? 会把 DOI 截断成斜杠后第一个字符）。
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s]+", re.IGNORECASE)
VERIFY_REFERENCES_MAX_ENTRIES = 30  # 单次批量核验上限，防止配额被一次打爆


def _extract_reference_entries(markdown: str) -> list:
    """从论文文本的参考文献段提取条目；折行续行自动并入上一条。

    判定新条目：行首列表标记/序号，或行前段含年份特征；
    不满足者视为上一条的换行续写，最终仅保留含年份的完整条目。
    """
    ref_match = _find_reference_heading(markdown)
    body = markdown[ref_match.end() :].strip() if ref_match else markdown.strip()
    year_re = re.compile(r"\((?:19|20)\d{2}[a-z]?\)|(?:19|20)\d{2}[.,;:]")
    merged = []
    for raw in body.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        head_year = bool(year_re.search(ln[:100]))
        starts_marker = bool(re.match(r"^([-*•]|\[\d{1,3}\]|\d{1,2}[.)])\s*", ln))
        if head_year or starts_marker or not merged:
            merged.append(ln)
        else:
            merged[-1] += " " + ln
    return [e for e in merged if year_re.search(e)]


def _clean_doi(raw: str) -> str:
    """去除 DOI 尾部随条目带出的标点与未闭合括号。"""
    doi = raw.rstrip(".,;:")
    while doi.endswith(")") and doi.count("(") < doi.count(")"):
        doi = doi[:-1]
    return doi


def _entry_title(entry: str) -> str:
    """从参考文献条目启发式提取标题。

    支持 APA 风格（'(年). 标题. 来源'）与 GB/T 风格（'. 标题[J].'）。
    """
    m = re.search(r"\((?:19|20)\d{2}[a-z]?\)[.:]?\s*(.+)", entry)
    if m:
        return m.group(1).split(". ")[0].strip()
    m = re.search(r"\.\s*([^.\[\]]{4,}?)\s*\[[JCMDS]\]", entry)
    if m:
        return m.group(1).strip()
    return ""


def _title_hint_long_enough(title: str) -> bool:
    """长度门槛按中英文加权：CJK 字符计双倍权重，避免中文短标题被一刀切过滤。"""
    cjk_count = _count_cjk(title)
    return len(title) + cjk_count >= 14


def _grade_reference_entries(markdown: str, max_entries: int = VERIFY_REFERENCES_MAX_ENTRIES) -> tuple:
    """提取参考文献条目并逐条核验分级（verify_references 与 CLI 共用的引擎循环）。

    返回 (rows, truncated)：rows=[{entry, result, method}]，truncated 表示超上限截断。
    """
    entries = _extract_reference_entries(markdown)
    if not entries:
        return [], False
    truncated = len(entries) > max_entries
    rows = []
    for entry in entries[:max_entries]:
        doi_m = DOI_PATTERN.search(entry)
        title_hint = _entry_title(entry)
        try:
            if doi_m:
                result, method = _apply_grade(_lookup_reference(doi=_clean_doi(doi_m.group(0)))), "DOI"
            elif _title_hint_long_enough(title_hint):
                result, method = _apply_grade(_lookup_reference(title=title_hint)), "标题"
            else:
                result, method = {"verified": False, "grade": "C"}, "无法提取"
        except Exception as e:
            result, method = {"verified": False, "grade": "C", "note": str(e)}, "异常"
        rows.append({"entry": entry, "result": result, "method": method})
    return rows, truncated


def verify_references(markdown: str, max_entries: int = VERIFY_REFERENCES_MAX_ENTRIES) -> str:
    """批量核验论文参考文献段中每条文献的真实性，输出汇总报告（Markdown 表格 + A/B/C 统计）。

    每条优先按 DOI 精确核验，无 DOI 时按标题检索（相似度阈值防误配）。
    单条失败不影响整体；结果受磁盘缓存加速。
    """
    if not markdown or not markdown.strip():
        return "输入为空：未提供论文文本。"
    graded, truncated = _grade_reference_entries(markdown, max_entries)
    if not graded:
        return "未在文本中识别到含年份的参考文献条目。请确认使用 APA/GB-T 等含年份的引用格式后重试。"

    rows = ["| # | 条目 | 分级 | 命中标题 | 相似度 | 说明 |", "|---|------|------|----------|--------|------|"]
    counts = {"A": 0, "B": 0, "C": 0, "X": 0}
    for i, g in enumerate(graded, 1):
        entry, result, method = g["entry"], g["result"], g["method"]
        short = entry if len(entry) <= 60 else entry[:57] + "..."
        short = short.replace("|", "\\|")
        grade = result.get("grade", "C")
        counts[grade] += 1
        sim = result.get("similarity", "")
        note = str(result.get("note", "") or ("命中" if result.get("verified") else ""))[:60]
        hit_title = str(result.get("title", ""))[:50].replace("|", "\\|")
        note = note.replace("|", "\\|")
        rows.append(f"| {i} | {short} | {grade}({method}) | {hit_title} | {sim} | {note} |")

    summary_line = f"共核验 {len(graded)} 条：**A 级 {counts['A']}**（存在且字段匹配）/ **B 级 {counts['B']}**（存在但需人工复核）/ **C 级 {counts['C']}**（未确认，投稿前必须补来源）"
    if counts["X"]:
        summary_line += f" / **X 级 {counts['X']}**（网络不可达或限流，无法核验——不是'查无此文'，不计入门禁失败，联网后重跑）"
    summary = [
        "# 参考文献批量核验报告",
        "",
        summary_line,
        "",
    ]
    if truncated:
        summary.append(f"> ⚠️ 条目超过 {VERIFY_REFERENCES_MAX_ENTRIES} 条，仅核验前 {max_entries} 条，其余请分段核验。")
    summary.append("")
    summary.extend(rows)
    summary.append("")
    summary.append("> 结果由 Crossref 实时核验并经磁盘缓存加速；C 级条目严禁以当前形态写进投稿稿件；X 级为网络原因未能核验，联网后重跑即可。")
    return "\n".join(summary)


def lit_search(query: str, limit: int = 5) -> str:
    """通过 Semantic Scholar API 检索学术文献，返回 JSON 结果字符串。"""
    if not query or not query.strip():
        return json.dumps({"total": 0, "results": [], "query": query, "note": "查询为空"}, ensure_ascii=False, indent=2)
    params = urllib.parse.urlencode(
        {
            "query": query.strip(),
            "limit": min(max(limit, 1), 20),
            "fields": "title,authors,year,abstract,citationCount,externalIds,url",
        }
    )
    url = f"{SEMANTIC_SCHOLAR_API}?{params}"
    headers = _crossref_headers()
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key
    try:
        data = _fetch_json(url, headers=headers, retries=2)
        results = []
        for paper in data.get("data", []):
            ext_ids = paper.get("externalIds", {}) or {}
            results.append(
                {
                    "title": paper.get("title", ""),
                    "authors": [a.get("name", "") for a in (paper.get("authors", []) or [])],
                    "year": paper.get("year"),
                    "abstract": (paper.get("abstract", "") or "")[:500],
                    "citationCount": paper.get("citationCount", 0),
                    "doi": ext_ids.get("DOI", ""),
                    "url": paper.get("url", ""),
                    "semanticScholarId": paper.get("paperId", ""),
                }
            )
        return json.dumps(
            {
                "total": data.get("total", len(results)),
                "results": results,
                "query": query.strip(),
            },
            ensure_ascii=False,
            indent=2,
        )
    except urllib.error.HTTPError as e:
        if e.code == 429:
            note = "Semantic Scholar 限流(429)：请稍后重试；或在环境变量 SEMANTIC_SCHOLAR_API_KEY 配置免费 API key 提升配额（https://www.semanticscholar.org/product/api）"
        else:
            note = f"HTTP {e.code}: {e.reason}"
        return json.dumps(
            {
                "total": 0,
                "results": [],
                "query": query.strip(),
                "error": note,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {
                "total": 0,
                "results": [],
                "query": query.strip(),
                "error": str(e),
            },
            ensure_ascii=False,
            indent=2,
        )


def journal_search_openalex(query: str, limit: int = 5) -> str:
    """通过 OpenAlex API 按主题检索学术期刊/来源，返回 JSON 结果字符串。

    弥补内置期刊库（data/journals.json）领域覆盖不足：任意学科实时搜库。
    """
    if not query or not query.strip():
        return json.dumps({"total": 0, "results": [], "query": query, "note": "查询为空"}, ensure_ascii=False, indent=2)
    params = urllib.parse.urlencode(
        {
            "search": query.strip(),
            "per-page": min(max(limit, 1), 10),
            "mailto": "scholarseed@example.com",
        }
    )
    url = f"{OPENALEX_API}?{params}"
    try:
        data = _fetch_json(url)
        results = []
        for src in data.get("results") or []:
            stats = src.get("summary_stats", {}) or {}
            results.append(
                {
                    "name": src.get("display_name", ""),
                    "publisher": src.get("host_organization_name", "") or "",
                    "worksCount": src.get("works_count", 0),
                    "citedByCount": src.get("cited_by_count", 0),
                    "hIndex": stats.get("h_index", 0),
                    "issn": src.get("issn", []) or [],
                    "openAccess": bool(src.get("is_in_doaj", False)),
                    "homepage": src.get("homepage_url", "") or "",
                    "openAlexId": (src.get("id", "") or "").rsplit("/", 1)[-1],
                }
            )
        return json.dumps(
            {
                "total": data.get("meta", {}).get("count", len(results)),
                "results": results,
                "query": query.strip(),
                "note": "指标为 OpenAlex 实时数据，投稿决策请以期刊官网为准",
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {
                "total": 0,
                "results": [],
                "query": query.strip(),
                "error": str(e),
            },
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# 写作者工具：引用条目格式化 / 摘要结构 / 标题质量
# ---------------------------------------------------------------------------

CITATION_STYLE_LABELS = {
    "apa": "APA 7",
    "gbt": "GB/T 7714-2015",
    "ieee": "IEEE",
    "bibtex": "BibTeX",
    "mla": "MLA 9",
    "chicago": "Chicago（书目格式）",
}


def _nat_name(a: dict) -> str:
    """自然序姓名：Yann LeCun。"""
    return f"{a.get('given', '')} {a.get('family', '')}".strip()


def _rev_name(a: dict) -> str:
    """倒序姓名：LeCun, Yann。"""
    return f"{a.get('family', '')}, {a.get('given', '')}".strip().rstrip(",")


def _fmt_authors_mla(structured: list) -> str:
    """MLA 9：第一作者倒序；两位用 and；三位及以上 et al.。"""
    if not structured:
        return ""
    head = _rev_name(structured[0])
    if len(structured) == 1:
        return head
    if len(structured) == 2:
        return f"{head}, and {_nat_name(structured[1])}"
    return f"{head}, et al."


def _fmt_authors_chicago(structured: list) -> str:
    """Chicago 书目格式：首作者倒序，其余自然序，最多列全部。"""
    if not structured:
        return ""
    head = _rev_name(structured[0])
    rest = [_nat_name(a) for a in structured[1:]]
    if not rest:
        return head
    if len(rest) == 1:
        return f"{head}, and {rest[0]}"
    return f"{head}, " + ", ".join(rest[:-1]) + ", and " + rest[-1]


def _initials(given: str) -> str:
    """'Yann Yoshua' -> 'Y. Y.'；无 given 返回空。"""
    parts = [p for p in re.split(r"[\s-]+", given.strip()) if p]
    if not parts:
        return ""
    return " ".join(f"{p[0].upper()}." for p in parts)


def _fmt_authors_apa(structured: list) -> str:
    if not structured:
        return ""
    names = []
    for a in structured:
        fam = a.get("family", "").strip()
        ini = _initials(a.get("given", ""))
        names.append(f"{fam}, {ini}".strip().rstrip(","))
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", ... " + names[-1]


def _fmt_authors_gbt(structured: list) -> str:
    if not structured:
        return ""
    names = []
    for a in structured:
        fam = a.get("family", "").strip()
        # GB/T 7714 惯例：姓大写 + 名首字母不带点（LECUN Y）
        ini = _initials(a.get("given", "")).replace(".", "")
        name = f"{fam.upper()} {ini}".strip()
        # 纯中文姓名（无分隔的 family+given 合并字段）原样保留
        if re.fullmatch(rf"[{CJK}]{{2,4}}", a.get("family", "") + a.get("given", "")):
            name = (a.get("family", "") + a.get("given", "")).strip()
        names.append(name)
    shown = names[:3]
    tail = "等" if re.fullmatch(rf"[{CJK}]+", shown[-1]) else "et al"
    if len(names) > 3:
        return ", ".join(shown) + f", {tail}."
    return ", ".join(names) + "."


def _fmt_authors_ieee(structured: list) -> str:
    if not structured:
        return ""
    names = []
    for a in structured[:6]:
        ini = _initials(a.get("given", ""))
        fam = a.get("family", "").strip()
        names.append(f"{ini} {fam}".strip())
    if len(structured) > 6:
        body = ", ".join(names) + " et al."
    elif len(names) > 1:
        body = ", ".join(names[:-1]) + ", and " + names[-1]
    else:
        body = names[0]
    return body


def _bibtex_key(result: dict) -> str:
    authors = result.get("authorsStructured") or []
    head = re.sub(r"[^a-z]", "", (authors[0].get("family", "") if authors else "anon").lower())
    year = result.get("year") or "nd"
    title_word = re.sub(r"[^a-z]", "", (result.get("title", "title").split() or ["title"])[0].lower())
    return f"{head or 'anon'}{year}{title_word or 'title'}"


def format_citation(doi: str = "", title: str = "", style: str = "apa", authors: str = "", year: int = 0) -> str:
    """按 DOI/标题核验文献后生成规范引用条目（真实 Crossref 元数据，杜绝手打错误）。

    style 可选：apa(APA 7)/gbt(GB/T 7714-2015)/ieee/bibtex/mla(MLA 9)/chicago(书目格式)。
    返回核验分级与格式化条目。
    """
    style_key = (style or "apa").strip().lower()
    aliases = {"apa7": "apa", "apa-7": "apa", "gb": "gbt", "gbt7714": "gbt", "gb-t": "gbt", "mla9": "mla", "mla-9": "mla", "chicago-notes": "chicago", "turabian": "chicago"}
    style_key = aliases.get(style_key, style_key)
    if style_key not in CITATION_STYLE_LABELS:
        return json.dumps({"ok": False, "note": f"未知 style '{style}'，可用: {', '.join(CITATION_STYLE_LABELS)}"}, ensure_ascii=False)
    if not (doi and doi.strip()) and not (title and title.strip()):
        return json.dumps({"ok": False, "note": "请提供 DOI 或标题，至少一项"}, ensure_ascii=False)
    result = _apply_grade(_lookup_reference(doi, title), title, authors, year)
    if not result.get("verified"):
        return json.dumps({"ok": False, "grade": "C", "note": result.get("note", "未命中该文献"), "hint": "未核验通过不生成条目——请确认 DOI/标题或改用 lit_search 检索"}, ensure_ascii=False)

    st = result.get("authorsStructured") or []
    t = result.get("title", "")
    j = result.get("journal", "")
    y = result.get("year") or ""
    vol = result.get("volume", "")
    iss = result.get("issue", "")
    pages = (result.get("pages", "") or "").replace("–", "-")
    doi_url = result.get("url", "")

    if style_key == "apa":
        entry = f"{_fmt_authors_apa(st)} ({y}). {t}. {j}"
        if vol and iss:
            entry += f", {vol}({iss})"
        elif vol:
            entry += f", {vol}"
        if pages:
            entry += f", {pages}"
        entry += "."
        if doi_url:
            entry += f" {doi_url}"
    elif style_key == "gbt":
        entry = f"{_fmt_authors_gbt(st)} {t}[J]. {j}, {y}"
        if vol:
            entry += f", {vol}" + (f"({iss})" if iss else "")
        if pages:
            entry += f": {pages}"
        entry += "."
    elif style_key == "ieee":
        entry = f'{_fmt_authors_ieee(st)}, "{t}," {j}'
        if vol:
            entry += f", vol. {vol}" + (f", no. {iss}" if iss else "")
        if pages:
            entry += f", pp. {pages}"
        entry += f", {y}."
    elif style_key == "mla":
        # MLA 9：作者. "题名." 刊名, vol. 卷, no. 期, 年, pp. 页码.
        mla_authors = _fmt_authors_mla(st).rstrip(".")
        entry = f'{mla_authors}. "{t}." {j}'
        segs = []
        if vol:
            segs.append(f"vol. {vol}")
        if iss:
            segs.append(f"no. {iss}")
        segs.append(str(y))
        if pages:
            segs.append(f"pp. {pages.replace('-', '–')}")
        entry += ", " + ", ".join(segs) + "."
    elif style_key == "chicago":
        # Chicago 书目格式：作者. "题名." 刊名 卷, no. 期 (年): 页码.
        entry = f'{_fmt_authors_chicago(st)}. "{t}." {j}'
        if vol:
            entry += f" {vol}" + (f", no. {iss}" if iss else "")
        if y:
            entry += f" ({y})"
        if pages:
            entry += f": {pages.replace('-', '–')}"
        entry += "."
    else:
        pages_bib = pages.replace("-", "--")
        lines = [
            f"@article{{{_bibtex_key(result)},",
            f"  author  = {{ {' and '.join((a.get('family', '') + ', ' + a.get('given', '')).strip(', ') for a in st)} }},",
            f"  title   = {{{t}}}",
            f"  journal = {{{j}}}",
            f"  year    = {{{y}}}",
        ]
        if vol:
            lines.append(f"  volume  = {{{vol}}}")
        if iss:
            lines.append(f"  number  = {{{iss}}}")
        if pages_bib:
            lines.append(f"  pages   = {{{pages_bib}}}")
        if result.get("doi"):
            lines.append(f"  doi     = {{{result['doi']}}}")
        entry = "\n".join(lines) + "\n}"

    label = CITATION_STYLE_LABELS[style_key]
    grade = result.get("grade", "B")
    header = f"**[{label}] 引用条目**（Crossref 已核验 · 分级 {grade}）\n\n"
    body = f"```bibtex\n{entry}\n```" if style_key == "bibtex" else f"> {entry}"
    footer = (
        "\n\n> 字段缺失处已省略（如卷/期/页码），以 Crossref 元数据为准；作者超过 3 人时 GB/T 按'等'截断、IEEE 按 et al 截断。"
        if style_key != "bibtex"
        else "\n\n> 键名规则：第一作者姓 + 年份 + 标题首词；页码连字符已转 BibTeX 双横线。"
    )
    return header + body + footer


# ---------------------------------------------------------------------------
# 全文质检校对套件（纯规则启发式：术语/文风/标点/图表/重复/文献格式）
# ---------------------------------------------------------------------------

CJK = r"\u4e00-\u9fff"
COMMON_ACRONYMS = {  # 无需定义即可使用的通用缩写
    "AI",
    "API",
    "CPU",
    "GPU",
    "RAM",
    "URL",
    "URI",
    "DOI",
    "PDF",
    "HTML",
    "HTTP",
    "HTTPS",
    "SQL",
    "JSON",
    "XML",
    "CSV",
    "TCP",
    "UDP",
    "DNS",
    "SSH",
    "IoT",
    "IT",
    "GPS",
    "GDP",
    "CEO",
    "CTO",
    "PhD",
    "DNA",
    "RNA",
    "MRI",
    "CT",
    "ECG",
    "HIV",
    "CI",
    "SD",
    "SE",
    "OR",
    "HR",
    "SEM",
    "ANOVA",
    # CS/ML 常见缩写（v1.21.0 语料实测扩充）
    "ML",
    "DL",
    "RL",
    "CNN",
    "RNN",
    "LSTM",
    "GRU",
    "GAN",
    "VAE",
    "BERT",
    "GPT",
    "LLM",
    "NLP",
    "CV",
    "SOTA",
    "SGD",
    "ReLU",
    "GPU",
    "TPU",
    "KPI",
    "ROI",
    "WHO",
    "FDA",
    "EEG",
    "PCR",
    "AIDS",
    "IQ",
    "PTSD",
    "ICU",
    "EU",
    "UN",
    "UK",
}
ROMAN_NUMERALS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XIX", "XX", "XXI"}
PLACEHOLDER_TOKENS = {"REF", "CITE", "ENV", "MATH"}
HEADING_WORDS = {
    "ABSTRACT",
    "KEYWORDS",
    "INTRODUCTION",
    "BACKGROUND",
    "METHODS",
    "METHOD",
    "RESULTS",
    "RESULT",
    "DISCUSSION",
    "CONCLUSIONS",
    "CONCLUSION",
    "REFERENCES",
    "APPENDIX",
    "ACKNOWLEDGMENTS",
    "ACKNOWLEDGEMENTS",
    "LIMITATIONS",
    "RELATED",
    "SUMMARY",
}
AI_FLAVOR_WORDS_EN = [
    "delve",
    "delving",
    "pivotal",
    "crucial",
    "underscore",
    "underscores",
    "leverage",
    "leveraging",
    "holistic",
    "seamless",
    "seamlessly",
    "utilize",
    "utilizing",
    "paradigm shift",
    "game-changer",
    "cutting-edge",
]
COLLOQUIAL_ZH = ["我觉得", "大家都", "毋庸置疑", "说白了", "其实吧", "搞出来", "整一个"]
FILLER_PHRASES_ZH = ["总而言之", "综上所述", "不言而喻", "显而易见", "众所周知"]
OVERCLAIM_WORDS_EN = ["prove that", "guarantee", "perfectly", "completely solves", "outperforms all", "revolutioniz"]
BUZZWORDS_ZH = ["赋能", "抓手", "底层逻辑", "颗粒度"]  # 互联网黑话，学术语境应为具体表述


# _line_starts/_pos_to_line/_find_pattern/_blank_fences/_count_cjk/_count_words_en/
# _find_reference_heading/_split_sentences/_split_body_references/_extract_abstract
# 已集中迁入 paper_ir.py（docs/ARCHITECTURE.md：一次解析、全塔共享），此处导入复用。
def check_style(markdown: str) -> dict:
    """文风检查：AI 高频词、口语化、凑字数短语、过度声明词、超长段落与句子。

    忽略围栏代码块内的内容（代码注释中的 AI 词不是正文问题）。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": [], "summary": {}}
    markdown = _blank_fences(markdown)
    issues = []
    for word in AI_FLAVOR_WORDS_EN:
        hits = _find_pattern(markdown, rf"\b{word}\b", re.IGNORECASE)
        for line, snip in hits:
            issues.append({"type": "ai_flavor", "severity": "warning", "line": line, "detail": f"AI 高频词 '{snip}'，建议替换为朴素表达"})
    for phrase in COLLOQUIAL_ZH:
        for line, snip in _find_pattern(markdown, re.escape(phrase)):
            issues.append({"type": "colloquial", "severity": "warning", "line": line, "detail": f"口语化表达 '{snip}'"})
    for word in BUZZWORDS_ZH:
        for line, snip in _find_pattern(markdown, re.escape(word)):
            issues.append({"type": "buzzword", "severity": "info", "line": line, "detail": f"互联网黑话 '{snip}'，学术语境应替换为具体表述"})
    for phrase in FILLER_PHRASES_ZH:
        for line, snip in _find_pattern(markdown, re.escape(phrase)):
            issues.append({"type": "filler", "severity": "info", "line": line, "detail": f"凑字数式短语 '{snip}'，确认必要后保留"})
    for word in OVERCLAIM_WORDS_EN:
        for line, snip in _find_pattern(markdown, re.escape(word), re.IGNORECASE):
            issues.append({"type": "overclaim", "severity": "warning", "line": line, "detail": f"过度声明词 '{snip}'，确认有证据支撑"})
    # 超长段落（连续非空行；中文字符>700 或 英文词>350）
    para_starts = _line_starts(markdown)
    for pm in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", markdown):
        para = pm.group(0)
        cjk_chars = _count_cjk(para)
        en_words = _count_words_en(para)
        if cjk_chars > 700 or en_words > 350:
            issues.append({"type": "long_paragraph", "severity": "info", "line": _pos_to_line(pm.start(), para_starts), "detail": f"段落过长（中文 {cjk_chars} 字 / 英文 {en_words} 词），建议拆分"})
    # 超长句（>90 字符且非列表行）
    for li, ln in enumerate(markdown.splitlines(), 1):
        s = ln.strip()
        if s.startswith(("-", "*", "#", "|", ">")) or not s:
            continue
        for sent in _split_sentences(s, keep_punct=True):
            # 语言感知阈值：CJK 按字、拉丁按词加权（纯英文规范学术句常超 90 字符）
            sent_cjk = _count_cjk(sent)
            sent_words = _count_words_en(sent)
            weighted = sent_cjk + sent_words
            if weighted > 45:
                issues.append({"type": "long_sentence", "severity": "info", "line": li, "detail": f"超长句（约 {weighted} 字/词）：{sent[:40]}..."})
                break
    summary = {}
    for it in issues:
        summary[it["type"]] = summary.get(it["type"], 0) + 1
    return {"ok": not issues, "issues": issues, "summary": summary}


def check_punctuation(markdown: str) -> dict:
    """标点规范：中英文标点混用（CJK 语境出现半角逗号/句号等）、CJK 与拉丁字符间缺空格提示。

    只扫描正文：GB/T 7714 中文文献表规范即使用半角标点（"张三. 标题[J]. 学报,"），
    扫进文献区会把合规写法全部误报。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    markdown, _refs = _split_body_references(markdown)
    issues = []
    code_spans = re.sub(r"`[^`]*`", "", markdown)
    # CJK 字符后跟半角逗号/句号/分号/冒号 → 应为全角
    for line, snip in _find_pattern(code_spans, rf"[{CJK}][,;:.](?![0-9])"):
        issues.append({"type": "halfwidth_after_cjk", "severity": "warning", "line": line, "detail": f"CJK 后使用半角标点 '{snip[-2:]}'，应为全角（，；：。）"})
    # 半角逗号后紧跟 CJK → 应为全角
    for line, snip in _find_pattern(code_spans, rf",[{CJK}]"):
        issues.append({"type": "halfwidth_before_cjk", "severity": "warning", "line": line, "detail": f"半角逗号后直接接中文 '{snip}'，应为全角逗号"})
    # 全角句号出现在纯英文单词之间
    for line, snip in _find_pattern(code_spans, r"[A-Za-z]。[A-Za-z]"):
        issues.append({"type": "fullwidth_in_english", "severity": "warning", "line": line, "detail": f"英文之间使用中文句号 '{snip}'"})
    return {"ok": not issues, "issues": issues}


def check_figures_tables(markdown: str) -> dict:
    """图表完整性：编号连续性、caption 与正文引用双向对应。"""
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    prose = _blank_fences(markdown)
    captions = {"figure": {}, "table": {}}
    refs = {"figure": set(), "table": set()}
    kind_map = {"图": "figure", "Figure": "figure", "Fig": "figure", "表": "table", "Table": "table"}
    starts = _line_starts(prose)
    for m in re.finditer(r"(图|Figure|Fig\.?|表|Table)\s*(\d+)", prose):
        kind = kind_map[re.sub(r"\.", "", m.group(1))]
        num = int(m.group(2))
        line_no = _pos_to_line(m.start(), starts)
        ls = starts[line_no - 1] if m.start() > 0 else 0
        line_prefix = prose[ls : ls + 40]
        is_caption = bool(re.match(r"\s*(?:\*\*)?\s*(?:图|表|Figure|Fig\.?|Table)\s*\d+", line_prefix))
        if is_caption:
            captions[kind][num] = line_no
        else:
            refs[kind].add(num)
    issues = []
    for kind, label in (("figure", "图"), ("table", "表")):
        cap_nums = sorted(captions[kind])
        ref_nums = refs[kind]
        if cap_nums and cap_nums != list(range(1, max(cap_nums) + 1)):
            missing = sorted(set(range(1, max(cap_nums) + 1)) - set(cap_nums))
            issues.append({"type": "numbering_gap", "severity": "error", "kind": label, "detail": f"{label}编号不连续，缺: {missing}"})
        uncited = sorted(set(cap_nums) - ref_nums)
        phantom = sorted(ref_nums - set(cap_nums))
        for n in uncited:
            issues.append({"type": "uncited_caption", "severity": "warning", "kind": label, "detail": f"{label}{n} 有 caption 但正文未引用"})
        for n in phantom:
            issues.append({"type": "phantom_reference", "severity": "error", "kind": label, "detail": f"正文引用了{label}{n}，但不存在对应 caption"})
    return {"ok": not issues, "issues": issues}


def check_terms(markdown: str, allow_common: bool = True, source_format: str = "markdown") -> dict:
    """术语一致性：缩写未定义先用、已定义未使用、同词异写变体。"""
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    markdown = _maybe_latex(markdown, source_format)
    body_only, _refs = _split_body_references(markdown)
    prose = re.sub(r"`[^`]*`", "", body_only)
    prose = _blank_fences(prose)
    defined = {}  # acronym -> expansion
    # 先移除定义处，再统计使用——避免"定义本身"被算作一次使用
    prose_wo_defs = re.sub(r"\b[A-Z]{2,10}\s*[（(][^（）()]{2,60}[）)]", " ", prose)
    prose_wo_defs = re.sub(rf"[{CJK}]（[A-Z]{{2,10}}）", " ", prose_wo_defs)
    for m in re.finditer(r"\b([A-Z]{2,10})\s*[（(]([^（）()]{2,60})[）)]", prose):
        defined.setdefault(m.group(1), m.group(2).strip())
    for m in re.finditer(rf"[{CJK}]（([A-Z]{{2,10}})）", prose):
        defined.setdefault(m.group(1), "")
    # 定义形态三：全称在前、缩写收尾——"(Anomaly Detection, AD)" / "（异常检测, AD）"
    prose_wo_defs = re.sub(r"[（(][^（）()]{2,60}?[,，]\s*[A-Z]{2,10}[）)]", " ", prose_wo_defs)
    for m in re.finditer(r"[（(]([^（）()]{2,60}?[,，]\s*([A-Z]{2,10}))[）)]", prose):
        defined.setdefault(m.group(2), m.group(1).strip())
    # 定义形态四：英文全称在前、缩写紧跟括号——"anomaly detection (AD)"
    prose_wo_defs = re.sub(r"\b[a-z][A-Za-z-]+\s[（(]([A-Z]{2,10})[）)]", " ", prose_wo_defs)
    for m in re.finditer(r"\b[a-z][A-Za-z-]+\s[（(]([A-Z]{2,10})[）)]", prose):
        defined.setdefault(m.group(1), "")
    used = Counter()
    for m in re.finditer(r"\b[A-Z]{2,10}\b", prose_wo_defs):
        used[m.group(0)] += 1
    skip = (COMMON_ACRONYMS | ROMAN_NUMERALS | HEADING_WORDS | PLACEHOLDER_TOKENS) if allow_common else (HEADING_WORDS | PLACEHOLDER_TOKENS | {"ET"})
    issues = []
    suppressed = 0
    for acr, count in sorted(used.items()):
        if acr in defined or acr in skip:
            continue
        # 上限 5 条：专业领域缩写会大量出现，全部报告会淹没其他问题
        if sum(1 for i in issues if i["type"] == "undefined_acronym") >= 5:
            suppressed += 1
            continue
        issues.append({"type": "undefined_acronym", "severity": "warning", "detail": f"缩写 '{acr}' 出现 {count} 次但未见定义（首次出现处应给出全称）"})
    if suppressed:
        issues.append({"type": "undefined_acronym_suppressed", "severity": "info", "detail": f"另有 {suppressed} 个未定义缩写未列出，建议全文检索补定义"})
    for acr in sorted(set(defined) - set(used)):
        issues.append({"type": "unused_definition", "severity": "info", "detail": f"定义了 '{acr}' 但正文未使用该缩写"})
    variants = Counter(re.findall(r"\b[A-Z]{2,10}-?\d+[A-Za-z]*\b", prose))
    base_groups = {}
    for token, cnt in variants.items():
        base = re.sub(r"[-_]", "", token.lower())
        base_groups.setdefault(base, {}).setdefault(token, cnt)
    for base, tokens in base_groups.items():
        if len(tokens) > 1:
            issues.append({"type": "inconsistent_variant", "severity": "warning", "detail": f"同一术语多种写法: {sorted(tokens)}，应全文统一"})
    return {"ok": not issues, "issues": issues}


def check_duplicates(markdown: str, min_len: int = 12) -> dict:
    """重复内容检测：规范化后完全相同的句子在文中多次出现。"""
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    prose = _blank_fences(markdown)
    # 删除标题行：否则标题文本黏连进句片（"## Discussion\n\nPatients..."），
    # 同一句在标题前后的归一化结果不同，英文论文的跨节重复会整体漏检
    prose = re.sub(r"(?m)^#{1,6}\s*[^\n]*$", "", prose)
    sentences = _split_sentences(prose)
    counter = Counter()
    samples = {}
    for s in sentences:
        norm = re.sub(r"\s+", "", s).lower()
        if len(norm) >= min_len:
            counter[norm] += 1
            samples.setdefault(norm, s.strip()[:50])
    issues = []
    # 每文档最多 5 条 duplicate 警告（长文样板句噪声治理），其余逐条降为 info
    ranked = sorted(counter.items(), key=lambda kv: -kv[1])
    warn_budget = 5
    for norm, cnt in ranked:
        if cnt <= 1:
            continue
        sev = "warning" if (cnt >= 3 and warn_budget > 0) else "info"
        if sev == "warning":
            warn_budget -= 1
        issues.append({"type": "duplicate_sentence", "severity": sev, "detail": f'重复 {cnt} 次："{samples[norm]}..."'})
    return {"ok": not issues, "issues": issues}


def check_references_format(markdown: str, current_year: int | None = None) -> dict:
    """参考文献格式检查：重复条目、未来年份（幻觉信号）、多风格混用。"""
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    entries = _extract_reference_entries(markdown)
    issues = []
    if current_year is None:
        current_year = time.localtime().tm_year

    def _norm(e: str) -> str:
        t = _entry_title(e) or e
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", t.lower())[:50]

    seen = {}
    styles = {}
    for idx, entry in enumerate(entries, 1):
        key = _norm(entry)
        if key and key in seen:
            issues.append({"type": "duplicate_entry", "severity": "error", "detail": f"第 {seen[key]} / {idx} 条疑似重复：{entry[:40]}..."})
        else:
            seen[key] = idx
        for ym in re.finditer(r"\b(19|20)(\d{2})\b", entry):
            year = int(ym.group(0))
            if year > current_year:
                issues.append({"type": "future_year", "severity": "error", "detail": f"第 {idx} 条含未来年份 {year}——典型幻觉信号，必须核实原文"})
        if re.search(r"\[[JCMDS]\]", entry):
            styles.setdefault("GB/T", []).append(idx)
        elif re.match(r"^\[\d+\]", entry):
            styles.setdefault("IEEE", []).append(idx)
        elif re.search(r"\((?:19|20)\d{2}[a-z]?\)\.", entry):
            styles.setdefault("APA", []).append(idx)
        else:
            styles.setdefault("未知格式", []).append(idx)
    named = [s for s in styles if s != "未知格式"]
    if len(named) > 1:
        detail = "; ".join(f"{s}×{len(v)}" for s, v in sorted(styles.items()))
        issues.append({"type": "mixed_styles", "severity": "error", "detail": f"参考文献多种格式混用（{detail}），须统一为一种"})
    elif "未知格式" in styles and named:
        issues.append({"type": "unrecognized_entries", "severity": "warning", "detail": f"{len(styles['未知格式'])} 条无法识别格式，请人工确认"})
    return {"ok": not issues, "issues": issues, "entries": len(entries), "styles": {k: len(v) for k, v in styles.items()}}


def _expand_num_citation(token: str) -> set:
    """展开数字引用标记：'2'->{2}；'2,5'->{2,5}；'2-5'->{2,3,4,5}。"""
    nums = set()
    for part in re.split(r"[，,]", token):
        m = re.match(r"\s*(\d{1,3})\s*[–—-]\s*(\d{1,3})\s*$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < a <= b <= 999:
                nums.update(range(a, b + 1))
        elif part.strip().isdigit():
            n = int(part.strip())
            if 0 < n <= 999:
                nums.add(n)
    return nums


def check_intext_citations(markdown: str) -> dict:
    """正文引用与文献表双向核对（数字式 [n] 与作者-年份式）。

    - 数字式：正文 [1]/[2,5]/[3-7] 与文献表编号（显式 [n] 或顺序号）比对；
    - 作者-年份式：(Smith, 2020)、[王五, 2021] 与文献表条目的 (首作者, 年份) 比对；
    - 两种风格混用给出警告；叙事式引用（如 "Smith (2020) 提出"）为已知启发式盲区。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    body, _refs = _split_body_references(markdown)
    entries = _extract_reference_entries(markdown)

    ref_ids = []
    for idx, e in enumerate(entries, 1):
        m = re.match(r"\s*[-*]?\s*\[(\d{1,3})\]", e)
        ref_ids.append(int(m.group(1)) if m else idx)
    dup_ids = sorted({i for i, c in Counter(ref_ids).items() if c > 1})

    numeric_cited = set()
    author_year = []
    # 兼容半角 () 与中文全角 （） 两种引用括号
    for m in re.finditer(r"\[([^\[\]\n]+)\]|[(（]([^()（）\n]+)[)）]", body):
        inner = (m.group(1) or m.group(2) or "").strip()
        if re.fullmatch(r"\d{1,3}(?:\s*[，,]\s*\d{1,3})*", inner) or re.fullmatch(r"\d{1,3}\s*[–—-]\s*\d{1,3}", inner):
            numeric_cited |= _expand_num_citation(inner.replace("，", ","))
            continue
        if "[" in inner or "]" in inner or len(inner) > 120:
            continue
        for piece in re.split(r"[;；]", inner):
            # 引用形态必须是 "姓氏 + 逗号 + 年份"（可选 et al./等），
            # 过滤 （截至2020年）/（2020年版） 等时间状语误报
            cm = re.search(r"^\s*([A-Za-z\u4e00-\u9fff]{2,12})(?:\s*(?:et\s+al\.?|等))?\s*[,，]\s*((?:19|20)\d{2}[a-z]?)", piece)
            if cm:
                author_year.append((cm.group(1).lower(), cm.group(2)))

    issues = []
    if numeric_cited and author_year:
        issues.append({"type": "mixed_citation_style", "severity": "warning", "detail": f"正文同时出现数字式({len(numeric_cited)}个编号)与作者-年份式({len(author_year)}处)引用，须统一为一种"})
    mode = "numeric" if numeric_cited else ("author-year" if author_year else "none")

    if numeric_cited:
        ref_set = set(ref_ids)
        for n in sorted(numeric_cited - ref_set):
            issues.append({"type": "citation_missing_entry", "severity": "error", "detail": f"正文引用 [{n}] 在文献表中不存在对应条目"})
        for n in sorted(set(ref_ids) - numeric_cited):
            issues.append({"type": "entry_never_cited", "severity": "warning", "detail": f"文献表条目 [{n}] 未被正文任何位置引用"})
    elif author_year:
        entry_keys = set()
        for e in entries:
            em = re.search(r"(?:19|20)\d{2}[a-z]?", e)
            sm = re.match(r"\s*[-*]?\s*(?:\[\d{1,3}\])?\s*([A-Za-z\u4e00-\u9fff]{2,})", e)
            if em and sm:
                entry_keys.add((sm.group(1).lower(), em.group(0)))
        cited_keys = set(author_year)
        for surname, year in sorted(cited_keys - entry_keys):
            issues.append({"type": "citation_no_match", "severity": "warning", "detail": f"正文引用 ({surname}, {year}) 在文献表中未找到对应条目"})
        for ek in sorted(entry_keys - cited_keys):
            issues.append({"type": "entry_never_cited", "severity": "warning", "detail": f"文献表条目 ({ek[0]}, {ek[1]}) 未被正文任何位置引用"})
    elif entries:
        issues.append({"type": "no_intext_citations", "severity": "warning", "detail": "正文未检测到任何引用标记（数字式或作者-年份式）"})

    if dup_ids:
        issues.append({"type": "duplicate_ref_number", "severity": "error", "detail": f"文献表编号重复: {dup_ids}"})
    return {"ok": not issues, "issues": issues, "mode": mode, "entries": len(entries)}


SECTION_REQUIREMENTS = {
    "empirical": [
        ("Abstract", r"摘要|abstract"),
        ("Introduction", r"引言|绪论|introduction"),
        ("Methods", r"方法|研究设计|methods"),
        ("Results", r"结果|发现|results?"),
        ("Discussion", r"讨论|discussion"),
        ("Conclusion", r"结论|conclusions?"),
        ("References", r"参考文献|references"),
    ],
    "survey": [
        ("Abstract", r"摘要|abstract"),
        ("Introduction", r"引言|introduction"),
        ("Classification / Related work", r"分类|相关工作|对比|related|taxonomy"),
        ("Challenges / Future", r"挑战|未来|展望|open problems?"),
        ("Conclusion", r"结论|conclusions?"),
        ("References", r"参考文献|references"),
    ],
    "tech": [
        ("Motivation", r"背景|动机|问题|motivation|background"),
        ("Design", r"设计|方案|design"),
        ("Evaluation", r"效果|评测|数据|evaluation|benchmark"),
        ("Limitations", r"局限|后续|limitations?"),
    ],
    "thesis": [
        ("绪论", r"绪论|第一章|chapter\s*1"),
        ("理论基础", r"理论基础|相关技术|文献综述"),
        ("核心章节", r"第[三四三四]|core"),
        ("验证与分析", r"实验|验证|分析"),
        ("总结与展望", r"总结与展望|结论|第[六七]章"),
        ("参考文献", r"参考文献|references"),
    ],
    "argumentative": [
        ("问题提出", r"问题的提出|论题|引言|introduction|问题缘起"),
        ("概念界定", r"概念界定|分析框架|定义|definitions?|framework"),
        ("论证主体", r"论证主体|论证|论据|argument|analysis"),
        ("反驳与回应", r"反驳与回应|反驳|回应|rebuttal|objection"),
        ("结论", r"结论与限度|^## .*结论|conclusion"),
    ],
}


def _clean_md_prefix(line: str) -> str:
    """去掉行首 Markdown 标记（#/加粗/斜体/引用等），供章节标签匹配。

    注意标签后侧的闭合标记也要清（如 "**关键词**：" 中冒号前的 **），
    因此对整行移除全部 Markdown 标记字符后再匹配。
    """
    return re.sub(r"[*_`#>]+", "", line.strip())


def check_sections(markdown: str, genre: str = "empirical") -> dict:
    """按体裁检查必备章节是否齐全 + 关键词行规范。

    章节识别覆盖两类位置：Markdown 标题行，以及以标签开头的独立短行
    （如 "**摘要**：……"、"Keywords: ..."——不少成稿的摘要并非标题层级）。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    genre = (genre or "empirical").lower()
    structure = check_structure(markdown)
    requirements = SECTION_REQUIREMENTS.get(genre, SECTION_REQUIREMENTS["empirical"])
    norm_lines = [_clean_md_prefix(ln) for ln in markdown.splitlines()]
    issues = []
    missing = []
    for label, pattern in requirements:
        in_headings = any(re.search(pattern, h["title"], flags=re.I) for h in structure["headings"])
        in_labels = any(re.match(pattern, s, flags=re.I) for s in norm_lines if s)
        if not (in_headings or in_labels):
            missing.append(label)
    if missing:
        issues.append({"type": "missing_sections", "severity": "warning", "detail": f"体裁 [{genre}] 缺少常见章节: {', '.join(missing)}（若确属非常规结构可忽略）"})
    # 关键词行：存在性 + 数量（兼容 "**关键词**：" / "Keywords:" 等写法）
    kw_clean = None
    for s in norm_lines:
        if re.match(r"(关键词|keywords?)\s*[:：]", s, flags=re.I):
            kw_clean = s
            break
    if kw_clean is None:
        issues.append({"type": "missing_keywords", "severity": "warning", "detail": "未找到关键词/Keywords 行（多数期刊要求 3-8 个）"})
    else:
        kw_body = re.sub(r"^(关键词|keywords?)\s*[:：]", "", kw_clean, flags=re.I)
        kws = [k for k in re.split(r"[；;，,、]", kw_body) if k.strip()]
        if not 3 <= len(kws) <= 8:
            issues.append({"type": "keyword_count", "severity": "info", "detail": f"关键词 {len(kws)} 个，常规区间为 3-8 个"})
    return {"ok": not issues, "issues": issues, "genre": genre}


ABSTRACT_ELEMENTS = [
    ("目的/背景", r"目的|旨在|背景|研究问题|本文|本研究|this (?:paper|study|article)|we (?:propose|study|investigate|examine)|aims? to|objective"),
    ("方法", r"方法|采用|基于|构建|样本|数据|实验设计|method|approach|dataset|data from|we use|using|experiment"),
    ("结果", r"结果|表明|显示|发现|results?|findings?|(?:shows?|indicates?|demonstrates?|reveals?) that"),
    ("结论", r"结论|意义|启示|贡献|implicat|contribut|conclusion|suggest(?:s|ing)?|impl(?:y|ies)"),
]


def check_abstract(markdown: str, genre: str = "empirical") -> dict:
    """摘要质量检查：结构化要素覆盖（目的/方法/结果/结论）、篇幅带、实证含量化结果。

    结构化摘要是审稿人第一眼——缺'结果'或全篇无数字的实证摘要是高频拒稿点。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    abstract = _extract_abstract(markdown)
    issues = []
    if not abstract:
        issues.append({"type": "missing_abstract", "severity": "warning", "detail": "未找到摘要段（支持 '## 摘要' 标题或 '**摘要**：' 标签行）"})
        return {"ok": False, "issues": issues, "summary": {}}
    cjk = _count_cjk(abstract)
    words = _count_words_en(abstract)
    weighted = cjk + words
    if weighted < 100:
        issues.append({"type": "abstract_too_short", "severity": "warning", "detail": f"摘要过短（约 {weighted} 字/词），常规区间 150-300 词或 300-500 字"})
    elif weighted > 500:
        issues.append({"type": "abstract_too_long", "severity": "warning", "detail": f"摘要过长（约 {weighted} 字/词），多数期刊要求 150-300 词或 300-500 字"})
    found = [name for name, pat in ABSTRACT_ELEMENTS if re.search(pat, abstract, flags=re.I)]
    missing = [name for name, _ in ABSTRACT_ELEMENTS if name not in found]
    for name in missing:
        issues.append({"type": "abstract_missing_element", "severity": "warning", "detail": f"摘要疑似缺少'{name}'要素（结构化四要素：目的/方法/结果/结论）"})
    is_empirical = (genre or "empirical").lower() == "empirical"
    if is_empirical and not re.search(r"\d", abstract):
        issues.append({"type": "abstract_no_numbers", "severity": "info", "detail": "实证摘要未含任何量化数字（样本量/效应/百分比）——建议补充关键统计量"})
    summary = {"lengthWeighted": weighted, "elementsFound": found, "elementsMissing": missing}
    return {"ok": not issues, "issues": issues, "summary": summary}


WEAK_TITLE_WORDS_ZH = ["浅析", "试论", "浅谈", "探析", "略论", "刍议", "之我见", "小议"]
WEAK_TITLE_PAT_EN = re.compile(r"^a (?:brief )?(?:study|discussion|analysis|review)?\s*(?:of|on)\b|^some thoughts on|^preliminary (?:study|analysis|report)|^a note on", re.I)


def check_title(markdown: str = "", title: str = "") -> dict:
    """标题质量检查：长度带、空泛措辞、英文大小写规范、问号与副标题结构提示。

    标题是检索入口：过长被数据库截断，空泛词降低可检索性与可信度。
    """
    t = (title or "").strip()
    if not t and markdown:
        # 仅接受 H1 标题行；无 H1 时如实报缺，不拿首段冒充标题
        m = re.search(r"^#\s+(.+)$", markdown, flags=re.M)
        if m:
            t = m.group(1).strip()
    issues = []
    if not t:
        return {"ok": False, "issues": [{"type": "missing_title", "severity": "warning", "detail": "未提供 title 参数且正文未找到 H1 标题"}], "stats": {}}
    cjk = _count_cjk(t)
    en_words = _count_words_en(t)
    if cjk > 25:
        issues.append({"type": "title_too_long", "severity": "warning", "detail": f"中文标题 {cjk} 字超过建议上限 25 字，检索与目录展示会被截断"})
    if en_words > 20:
        issues.append({"type": "title_too_long", "severity": "warning", "detail": f"英文标题 {en_words} 词超过建议上限 20 词"})
    for w in WEAK_TITLE_WORDS_ZH:
        if w in t:
            issues.append({"type": "weak_title_word", "severity": "warning", "detail": f"空泛措辞 '{w}'——直接陈述研究对象与结论更利于检索与评审"})
            break
    wm = WEAK_TITLE_PAT_EN.search(t)
    if wm:
        issues.append({"type": "weak_title_word", "severity": "warning", "detail": f"空泛开头 '{wm.group(0).strip()}'——建议直接以研究对象/发现命名"})
    latin_letters = re.findall(r"[A-Za-z]", t)
    if latin_letters and not re.search(rf"[{CJK}]", t):
        if all(ch.islower() or not ch.isalpha() for ch in latin_letters):
            issues.append({"type": "title_case_suspect", "severity": "info", "detail": "英文标题全部小写——多数期刊要求 Title Case 或 Sentence case，请核对目标刊规范"})
        elif all(not ch.islower() for ch in latin_letters):
            issues.append({"type": "title_case_suspect", "severity": "warning", "detail": "英文标题全部大写——除特定刊要求外不建议"})
    if "?" in t or "？" in t:
        issues.append({"type": "question_title", "severity": "info", "detail": "疑问句式标题——部分期刊与数据库不友好，确认目标刊惯例"})
    if ":" in t or "：" in t:
        issues.append({"type": "subtitle_structure", "severity": "info", "detail": "主副标题结构——确保副题承载具体信息而非重复主题"})
    stats = {"cjkChars": cjk, "enWords": en_words}
    return {"ok": not issues, "issues": issues, "stats": stats, "note": "启发式提示；以目标期刊投稿指南为准"}


def _split_h2_blocks(markdown: str) -> list:
    """按 H2 标题切块，返回 [(title, text)]；首个 H2 前的内容记为 (front matter)。"""
    blocks = []
    current_title, current_lines = "(front matter)", []
    for line in markdown.splitlines():
        hm = re.match(r"^##\s+(.*)$", line)
        if hm:
            blocks.append((current_title, "\n".join(current_lines)))
            current_title, current_lines = hm.group(1).strip(), []
        else:
            current_lines.append(line)
    blocks.append((current_title, "\n".join(current_lines)))
    return blocks


def word_budget(markdown: str, journal: str = "") -> dict:
    """分章词数对照目标期刊篇幅规划（数据源与 render_template 同一套 JOURNAL_PROFILES）。"""
    profile = JOURNAL_PROFILES.get((journal or "").strip().lower())
    if not profile:
        return {"ok": False, "note": f"未知期刊类型 '{journal}'，可用: {', '.join(JOURNAL_PROFILES)}"}
    key_map = [
        ("Abstract", r"摘要|abstract"),
        ("Introduction", r"引言|绪论|introduction"),
        ("Theoretical foundations", r"理论基础|theoretical"),
        ("Framework", r"框架|framework"),
        ("Propositions", r"命题|proposition"),
        ("Theory & hypotheses", r"理论与假设|理论|hypothes"),
        ("Methods", r"方法|methods"),
        ("Results", r"结果|results?"),
        ("Discussion", r"讨论|discussion"),
        ("Conclusion", r"结论|conclusion"),
        ("Main body", r".*"),
    ]
    # 按 H2 切块
    blocks = _split_h2_blocks(markdown)

    def _size(text: str) -> int:
        cjk = _count_cjk(text)
        en = _count_words_en(text)
        return cjk + en

    rows = []
    matched_titles = set()
    front_text = next((txt for t, txt in blocks if t == "(front matter)"), "")
    for section, target in profile["by_section"].items():
        pat = next((p for name, p in key_map if name == section), None)
        found = None
        if pat:
            for title, text in blocks:
                if title != "(front matter)" and title.lower() not in matched_titles and re.search(pat, title, flags=re.I):
                    found = (title, _size(text))
                    matched_titles.add(title.lower())
                    break
            # 摘要等常落在前置区（首个 H2 之前）
            if found is None and re.search(r"摘要|abstract", pat, flags=re.I) and re.search(rf"[{CJK}]|abstract", front_text, flags=re.I):
                found = ("(front matter)", _size(front_text))
        rows.append({"section": section, "target": target, "actualTitle": found[0] if found else "", "actual": found[1] if found else None})
    unmatched = [(t, _size(txt)) for t, txt in blocks if t != "(front matter)" and t.lower() not in matched_titles]
    return {"ok": True, "journal": journal, "label": profile["label"], "total": profile["total"], "rows": rows, "unmatchedBlocks": unmatched}


def _norm_grams(text: str, n: int = 8) -> set:
    """规范化后取 n-gram 集合（仅字母数字/CJK），供跨文档重叠比较。"""
    norm = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.lower())
    if len(norm) < n:
        return set()
    return {norm[i : i + n] for i in range(len(norm) - n + 1)}


def check_self_plagiarism(markdown: str, corpus_dir: str, min_gram: int = 8, threshold: float = 0.05, max_files: int = 50) -> dict:
    """跨文档自查重：当前稿与语料库目录中历史稿件的重叠率（n-gram 启发式）。

    适用场景：学位论文章节复用自己已发表内容、系列论文模板句复用等。
    合理的方法学表述复用同样会命中——结果为提示，需人工判断是否改写或引用。
    """
    from pathlib import Path as _P

    cdir = _P(corpus_dir) if corpus_dir else None
    if cdir is None or not cdir.is_dir():
        return {"ok": True, "note": "语料库目录不存在或未提供，跳过自查重", "corpusFiles": 0}
    cur = _norm_grams(markdown, min_gram)
    if not cur:
        return {"ok": True, "note": "正文过短，无法提取 n-gram", "corpusFiles": 0}
    files = sorted(f for f in cdir.iterdir() if f.is_file() and f.suffix.lower() in {".md", ".txt", ".tex"})
    files = files[:max_files]
    results = []
    issues = []
    for f in files:
        try:
            grams = _norm_grams(_maybe_latex(f.read_text(encoding="utf-8"), "latex" if f.suffix.lower() == ".tex" else "markdown"), min_gram)
        except (OSError, ValueError):
            continue
        shared = cur & grams
        ratio = len(shared) / max(len(cur), 1)
        if ratio >= threshold:
            example = sorted(shared)[0][:24]
            results.append({"file": f.name, "sharedGrams": len(shared), "ratio": round(ratio, 4), "exampleGram": example})
            issues.append({"type": "self_overlap", "severity": "warning", "detail": f"与 {f.name} 共享 {len(shared)} 个 {min_gram}-gram（占当前稿 {ratio:.1%}），示例：{example}…"})
    results.sort(key=lambda r: -r["ratio"])
    return {"ok": not issues, "issues": issues, "files": results, "corpusFiles": len(files), "threshold": threshold}


# ---------------------------------------------------------------------------
# 学术诚信三件套：AI 痕迹画像 / 数字一致性 / 断言强度对冲
# ---------------------------------------------------------------------------


def _latex_to_text(tex: str) -> str:
    r"""LaTeX 稿件转近似 Markdown：保留章节结构/正文，剥命令、注释与公式。

    花括号感知：支持标题内一层嵌套（如 \section{About \texttt{X}}）；
    跳过转义美元符（\$ 为字面美元而非公式定界符）。
    """
    t = re.sub(r"(?m)^%.*$", "", tex)
    t = re.sub(r"(?<!\\)%.*$", "", t, flags=re.M)

    # 环境整体替换（thebibliography 的机构名会污染术语检查；
    # 引用核对在原始 tex 上走键级比对，不依赖该环境文本）
    t = re.sub(r"\\begin\{thebibliography\}\s*(?:\{[^{}]*\})?.*?\\end\{thebibliography\}", "\n\n", t, flags=re.S)
    t = re.sub(r"\\begin\{(equation|align|gather|figure|table)\*?\}.*?\\end\{\1\*?\}", "\n\nENV\n\n", t, flags=re.S)

    # 公式定界（跳过转义 \$）
    t = re.sub(r"\$\$.*?\$\$", " MATH ", t, flags=re.S)
    t = re.sub(r"(?<!\\)\$[^$\n]*?(?<!\\)\$", " MATH ", t)

    # 文本包裹类命令：循环解包以支持嵌套（\textbf{a \emph{b}}）
    wrap_pat = re.compile(r"\\(?:textbf|textit|emph|texttt|mbox|textrm|underline)\{([^{}]*)\}")
    for _ in range(10):
        if not wrap_pat.search(t):
            break
        t = wrap_pat.sub(r"\1", t)

    # 无正文的引用/标签命令
    t = re.sub(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{[^{}]*\}", " [CITE] ", t)
    t = re.sub(r"\\(?:label|ref|eqref)\{[^{}]*\}", " REF ", t)

    def _sec(m):
        level = "##" if (m.group(1) or "section") == "section" else "###"
        title = m.group(2).strip()
        return f"\n\n{level} {title}\n\n"

    # 章节标题：允许标题内一层花括号嵌套
    sec_pat = re.compile(r"\\((?:sub)*section)\*?(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}")
    prev = None
    while prev != t:
        prev = t
        t = sec_pat.sub(_sec, t)

    # 剩余无参/有参命令与散落花括号
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", t)
    t = t.replace("{", " ").replace("}", " ").replace("~", " ")
    return t.strip()


def _maybe_latex(markdown: str, source_format: str) -> str:
    return _latex_to_text(markdown) if (source_format or "markdown").lower() == "latex" else markdown


# PDF 文本提取为尽力级：支持 FlateDecode 与未压缩流中的 (..) Tj / [..] TJ 算子；
# 不解析 CID/CJK 字体映射与复杂编码——中文 PDF 提取结果可能不完整。
_PDF_STREAM_HEAD = re.compile(rb"stream\r?\n")
_PDF_LITERAL = re.compile(r"\((?:\\.|[^\\()])*\)")


def _pdf_inflate_streams(data: bytes) -> list:
    out = []
    for m in _PDF_STREAM_HEAD.finditer(data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        raw = data[start:end].rstrip(b"\r\n")
        try:
            out.append(zlib.decompress(raw))
        except Exception:
            out.append(raw)  # 未压缩流
    return out


def _pdf_extract_text(data: bytes) -> str:
    parts = []
    for stream in _pdf_inflate_streams(data):
        try:
            s = stream.decode("latin-1", errors="ignore")
        except Exception:
            continue
        for tm in re.finditer(r"\((?:\\.|[^\\()])*\)\s*Tj|\[(?:[^\[\]]|\\.)*?\]\s*TJ", s):
            chunk = tm.group(0)
            for lit in _PDF_LITERAL.findall(chunk):
                inner = lit[1:-1]
                inner = re.sub(r"\\([()\\])", r"\1", inner)
                parts.append(inner)
    text = " ".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def audit_pdf(pdf_path: str, genre: str = "empirical", fmt: str = "markdown", min_chars: int = 200) -> str:
    """对 PDF 投稿做尽力级审计：提取文本后运行适用于纯文本的检查子集。

    适用：style / duplicates / hedging / numbers / stats(empirical) / ai_signature。
    跳过：结构层级、标点排版、图表对应、术语定义、引用核对（PDF 无法可靠还原）。
    提取为尽力级——复杂字体编码的 PDF 可能得到空/残缺文本，报告会如实标注。
    """
    path = Path(pdf_path) if pdf_path else None
    if path is None or not path.is_file():
        return json.dumps({"ok": False, "note": f"文件不存在: {pdf_path}"}, ensure_ascii=False)
    try:
        text = _pdf_extract_text(path.read_bytes())
    except Exception as e:
        return json.dumps({"ok": False, "note": f"提取失败: {e}"}, ensure_ascii=False)
    if len(text) < min_chars:
        return json.dumps(
            {
                "ok": False,
                "note": f"文本提取过短（{len(text)} 字符 < {min_chars}）——该 PDF 可能使用复杂字体编码（如 CID/CJK），或本身内容过短；超出尽力级提取范围",
            },
            ensure_ascii=False,
        )

    style = check_style(text)
    dupes = check_duplicates(text)
    hedging = check_hedging(text)
    numbers = check_numbers(text)
    is_empirical = (genre or "empirical").lower() == "empirical"
    stats = check_stats(text) if is_empirical else {"ok": True, "issues": [], "summary": {"note": f"体裁 [{genre}] 非实证类，统计红线已跳过"}}

    sections = [("文风", style), ("重复内容", dupes), ("断言强度对冲", hedging), ("数字一致性", numbers)]
    if is_empirical:
        sections.append(("统计诚信", stats))
    total_error = sum(1 for _, r in sections for i in r["issues"] if i["severity"] == "error")
    total_warn = sum(1 for _, r in sections for i in r["issues"] if i["severity"] == "warning")
    total_info = sum(1 for _, r in sections for i in r["issues"] if i["severity"] == "info")

    skipped = ["标题结构", "标点排版", "图表对应", "术语定义", "引用核对", "词数预算"]
    result = {
        "scoreNote": "尽力级提取 + 子集检查；分数反映待复核密度，非论文质量判决",
        "summary": {"errors": total_error, "warnings": total_warn, "infos": total_info},
        "extractedChars": len(text),
        "sections": [{"name": n, "ok": r.get("ok"), "issues": r.get("issues", [])} for n, r in sections],
        "skippedChecks": skipped,
        "statsSummary": stats.get("summary", {}),
    }

    if (fmt or "markdown").lower() == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    headline = f"ERROR {total_error} · WARNING {total_warn} · INFO {total_info}　|　体裁 [{genre}]　|　提取字符 {len(text)}"
    lines = [
        "# PDF 审计报告（audit_pdf，尽力级）",
        "",
        headline,
        "",
        f"跳过项：{'、'.join(skipped)}（PDF 无法可靠还原对应信息）",
        "",
    ]
    for s in result["sections"]:
        status = "通过" if s["ok"] else f"{len(s['issues'])} 项"
        lines.append(f"## {s['name']}：{status}")
        seen = set()
        for issue in s["issues"]:
            key = (issue.get("type"), issue.get("detail"))
            if key in seen:
                continue
            seen.add(key)
            loc = f"L{issue['line']} " if issue.get("line") is not None else ""
            lines.append(f"- [{issue['severity'].upper()}] {loc}{issue['detail']}")
        if not s["issues"]:
            lines.append("- （无问题）")
        lines.append("")
    return "\n".join(lines)


AI_TEMPLATE_ZH = [
    "值得注意的是",
    "不难发现",
    "由此可见",
    "在一定程度上",
    "扮演着重要的角色",
    "提供了新的思路",
    "具有重要意义",
    "与此同时",
    "不仅如此",
    "综上所述",
    "总而言之",
    "总的来说",
    # v1.29.0 扩充：中文大模型高频套话（证据词表扩展，不改变已校准的评分权重）
    "众所周知",
    "不言而喻",
    "毋庸置疑",
    "发挥着重要作用",
    "起到了关键作用",
    "取得了显著成果",
    "得到了广泛应用",
    "具有广阔的应用前景",
    "为后续研究提供了参考",
    "为相关研究提供了借鉴",
    "随着科技的不断发展",
    "随着社会的不断进步",
    "日益增长的需求",
    "不可忽视的问题",
    "本文将从以下几个方面",
]
AI_TEMPLATE_EN = [
    "it is worth noting",
    "it is important to note",
    "in conclusion",
    "plays a crucial role",
    "plays a vital role",
    "plays a pivotal role",
    "paves the way",
    "shed light on",
    "delve into",
    "delves into",
    "delving into",
    "in the realm of",
    "the landscape of",
    "a testament to",
    "navigating the complexities",
    "unlock the potential",
    "harness the power",
    "embark on",
    "has garnered significant attention",
    "in today's rapidly evolving",
    # v1.30.0 expansion: high-frequency LLM academic vocabulary documented by
    # Liang et al. 2024 (arXiv:2403.07183) and detector-benchmark literature.
    # Multi-word phrases preferred for precision; advisory info-severity only.
    "underscores the importance",
    "underscores the need",
    "underscoring the importance",
    "highlighting the need",
    "in the ever-evolving landscape",
    "ever-evolving world of",
    "navigate the complexities",
    "navigating the intricacies",
    "holistic approach",
    "multifaceted nature",
    "complex interplay",
    "intricate relationship",
    "seamless integration",
    "paradigm shift",
    "bridge the gap between",
    "opens up new avenues",
    "gain valuable insights",
    "actionable insights",
    "comprehensive understanding",
    "robust framework",
    "cutting-edge techniques",
    "leverage the power",
    "showcasing",
    "tapestry",
    "in the digital age",
"in an era of", "a plethora of", "at its core", "not just", "fast-paced", "game-changer", ]
PASSIVE_PROXY_PATTERN = re.compile(r"\b(was|were|is|are|has been|have been|had been)\s+\w+(ed|en)\b", re.I)
SENTENCE_INITIAL_TRANSITIONS = re.compile(
    r"^(Moreover|Furthermore|Additionally|Notably|Importantly|In addition|Ultimately|Consequently|In essence|In summary)\b"
    r"|^(此外|同时|与此同时|不仅如此|首先|其次|再次|最后|总之|综上|值得注意的是)",
    re.I,
)


_ABBREV_DOT = re.compile(r"\b(al|e\.g|i\.e|etc|vs|cf|Fig|fig|Dr|Prof|Sr|Jr|St|Mr|Ms|No|Vol|pp|approx)\.(?=\s)", re.I)


def _sentences_of(text: str) -> list:
    # 先保护常见缩写点号（et al. / Fig. / e.g. 等），避免把一句切成多句
    protected = _ABBREV_DOT.sub(lambda m: m.group(0)[:-1] + "\u0001", text)
    sents = []
    for raw in re.split(r"[。！？!?]+|(?<=[.])\s+", protected):
        s = raw.replace("\u0001", ".").strip()
        if len(s) >= 4:
            sents.append(s)
    return sents


def check_ai_signature(markdown: str, min_sentences: int = 8, style: str = "stem") -> dict:
    """AI 痕迹统计画像（启发式参考，非判决）。

    指标：句长突发性(CV 越低越均匀)、词汇丰富度(TTR/二元组多样性)、
    模板短语密度、句首转折词占比、em-dash 密度、"不仅…更…"句式。
    输出证据清单 + 0-100 相似度分值区间。
    style="humanities"（人文阐释性文体）：剥离 STEM 校准的分布项
    （句长 CV / TTR），只保留跨学科词汇证据——文科术语密集与均匀句长
    属正常形态，不作为扣分项。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "note": "输入为空"}
    body, _refs = _split_body_references(markdown)
    body = _blank_fences(body)  # 围栏置空但保留换行数：代码块内容不计入，且行号不漂移
    sents = _sentences_of(body)
    if len(sents) < min_sentences:
        return {"ok": True, "note": f"句子数 {len(sents)} < {min_sentences}，样本过短无法可靠评估"}

    lengths = [_count_cjk(s) + _count_words_en(s) for s in sents]
    mean_len = sum(lengths) / len(lengths)
    var = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
    cv = (var**0.5) / mean_len if mean_len else 0.0

    en_words = [w.lower() for w in re.findall(r"[A-Za-z]+", body)]
    cjk_chars = re.findall(f"[{CJK}]", body)
    zh_bigrams = [(cjk_chars[i], cjk_chars[i + 1]) for i in range(len(cjk_chars) - 1)]

    def _mattr(tokens, window=300):
        """移动窗口 TTR（MATTR）：消除原文长度对丰富度的系统性压低。"""
        if not tokens:
            return 0.0
        if len(tokens) <= window:
            return len(set(tokens)) / len(tokens)
        step = max(1, window // 4)
        vals = [len(set(tokens[i : i + window])) / window for i in range(0, len(tokens) - window + 1, step)]
        return sum(vals) / len(vals)

    ttr_en = _mattr(en_words)
    ttr_zh = _mattr(zh_bigrams)

    template_hits = []
    starts = _line_starts(body)
    for phrase in AI_TEMPLATE_ZH + AI_TEMPLATE_EN:
        for m in re.finditer(re.escape(phrase), body, flags=re.I):
            template_hits.append((_pos_to_line(m.start(), starts), f"模板短语 '{phrase}'"))
    transitions = sum(1 for s in sents if SENTENCE_INITIAL_TRANSITIONS.match(s))
    transition_ratio = transitions / len(sents)

    emdash_count = len(re.findall(r"—|――", body))
    emdash_per_1000 = emdash_count * 1000 / max(len(body), 1)

    not_only = len(re.findall(r"不仅[^。]{0,20}(?:更|还|而且)", body))
    passive_hits = len(PASSIVE_PROXY_PATTERN.findall(body))
    passive_ratio = passive_hits / max(len(sents), 1)

    # 语言项仅在该语言存在时参与评分（纯中文文本不应因无英文词被扣分）
    en_term = max(0.0, (0.55 - ttr_en)) * 70 if en_words else 0.0
    zh_term = max(0.0, (0.60 - ttr_zh)) * 45 if zh_bigrams else 0.0
    # 破折号密度对短样本会爆炸，单列封顶
    emdash_term = min(20.0, emdash_per_1000 * 5)

    humanities_mode = (style or "stem").strip().lower().startswith("hum")
    if humanities_mode:
        # 人文阐释性文体模式：剥离 STEM 校准的分布项（句长 CV / TTR——
        # 文科术语密集、句长均匀属正常形态），只保留跨学科词汇证据
        score = min(100, round(len(template_hits) * 6 + transition_ratio * 45 + emdash_term + not_only * 3 + passive_ratio * 25))
    else:
        score = min(100, round(max(0.0, (0.45 - cv)) * 150 + en_term + zh_term + len(template_hits) * 6 + transition_ratio * 45 + emdash_term + not_only * 3 + passive_ratio * 25))
    band = "高" if score >= 60 else ("中" if score >= 30 else "低")
    issues = []
    if cv < 0.4 and not humanities_mode:
        issues.append({"type": "low_burstiness", "severity": "warning", "detail": f"句长高度均匀（CV={cv:.2f}<0.4），人类写作通常变化更大"})
    for it in set(template_hits):
        issues.append({"type": "template_phrase", "severity": "info", "line": it[0], "detail": it[1]})
    if transition_ratio > 0.25:
        issues.append({"type": "transition_opener", "severity": "info", "detail": f"{transitions}/{len(sents)} 句以 Moreover/Furthermore 类开头"})
    return {
        "ok": not issues and band == "低",
        "score": score,
        "band": band,
        "style": ("humanities" if humanities_mode else "stem"),
        "metrics": {
            "sentences": len(sents),
            "meanSentenceLen": round(mean_len, 1),
            "burstinessCV": round(cv, 3),
            "mattrEn": round(ttr_en, 3),
            "mattrZhBigram": round(ttr_zh, 3),
            "templateHits": len(template_hits),
            "transitionRatio": round(transition_ratio, 3),
            "emDashPer1000": round(emdash_per_1000, 2),
            "notOnlyPattern": not_only,
            "passiveRatio": round(passive_ratio, 3),
        },
        "issues": issues,
        "note": "统计画像为启发式参考；高分只代表'值得人工复核'，不构成 AI 代写判定",
    }


# 零宽/不可见字符 → 说明（降AI工具与规避检测攻击的常见残留）
ZERO_WIDTH_CHARS = {
    "\u200b": "零宽空格 U+200B",
    "\u200c": "零宽非连接符 U+200C",
    "\u200d": "零宽连接符 U+200D",
    "\u2060": "词连接符 U+2060",
    "\ufeff": "零宽不换行空格(BOM) U+FEFF",
    "\u00ad": "软连字符 U+00AD",
}

# 西里尔/希腊字母 ↔ 拉丁同形字映射（RAID 基准 homoglyph 攻击字符集，Wolff 2020/Dugan et al. ACL 2024）
_HOMOGLYPHS = {
    # 西里尔 → 拉丁
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "У": "Y",
    "Х": "X",
    # 希腊 → 拉丁
    "ο": "o",
    "Ο": "O",
    "ρ": "p",
    "τ": "t",
    "υ": "u",
    "Α": "A",
    "Β": "B",
    "Ε": "E",
    "Ζ": "Z",
    "Η": "H",
    "Κ": "K",
    "Μ": "M",
    "Ν": "N",
    "Ρ": "P",
    "Τ": "T",
    "Υ": "Y",
    "Χ": "X",
}
_LATIN = re.compile(r"[A-Za-z]")


def _strip_fenced(text: str) -> str:
    """围栏置空但保留换行数：内容不再参与检查，同时行号映射不漂移。"""
    return _blank_fences(text)


def check_tamper_traces(markdown: str) -> dict:
    """防篡改痕迹取证：检测'降AI'处理与规避检测攻击留下的客观文本痕迹。

    检测对象（全部为确定性可验证的客观特征，非写作风格判断）：
    1. 零宽/不可见字符（U+200B/200C/200D/2060/FEFF、软连字符）——
       RAID 基准 zero-width space 攻击可使多个检测器输出整体翻转；
    2. 西里尔/希腊同形字混入拉丁单词（如 e→е）——RAID homoglyph 攻击
       使主流检测器平均掉点约 40；正常俄文/希腊文段落自动豁免；
    3. 行内连续 3+ 空白串——RAID whitespace 攻击特征（段首缩进豁免）。

    定位是"取证提示"而非"AI 判决"：发现痕迹只说明文本被非常规工具
    处理过或复制自异常来源，需人工复核。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": [], "summary": {}}
    body = _strip_fenced(_split_body_references(markdown)[0])
    starts = _line_starts(body)
    issues = []
    summary = {"zeroWidth": 0, "homoglyph": 0, "whitespaceRuns": 0}

    # 1. 零宽/不可见字符
    zw_by_char = {}
    for ch, label in ZERO_WIDTH_CHARS.items():
        hits = [m.start() for m in re.finditer(re.escape(ch), body)]
        if hits:
            lines = sorted({_pos_to_line(p, starts) for p in hits})[:5]
            zw_by_char[label] = {"count": len(hits), "lines": lines}
            summary["zeroWidth"] += len(hits)
    if zw_by_char:
        detail = "；".join(f"{k}×{v['count']}(L{','.join(map(str, v['lines']))})" for k, v in zw_by_char.items())
        issues.append(
            {
                "type": "zero_width_chars",
                "severity": "warning",
                "detail": f"检测到不可见字符——人眼不可见但机器可读，常见于规避检测的文本处理残留：{detail}",
            }
        )

    # 2. 同形字混入拉丁单词。判据是局部特征：同形字两侧至少一侧紧邻拉丁
    # 字母才可疑——正常俄文/希腊文段落中字符邻居同为西里尔/希腊字母，
    # 天然豁免；RAID homoglyph 攻击把字母替换进拉丁单词内部，必然留下
    # 拉丁邻居。不用文档级占比做前置门控：θ=100% 全文字符级替换会把
    # 占比抬高到误触发放行阈值。
    homo_hits = []
    for m in re.finditer(r"\S+", body):
        word = m.group(0)
        stripped = word.strip("\"'()[]{}。，；：、！？")
        for i, ch in enumerate(stripped):
            if ch in _HOMOGLYPHS:
                prev_l = i > 0 and _LATIN.match(stripped[i - 1])
                next_l = i + 1 < len(stripped) and _LATIN.match(stripped[i + 1])
                if prev_l or next_l:
                    homo_hits.append((_pos_to_line(m.start(), starts), word[:40], ch, _HOMOGLYPHS[ch]))
    if homo_hits:
        summary["homoglyph"] = len(homo_hits)
        shown = ", ".join(f"L{ln} '{w}'({c}→{t})" for ln, w, c, t in homo_hits[:5])
        extra = f" 等 {len(homo_hits)} 处" if len(homo_hits) > 5 else ""
        issues.append(
            {
                "type": "homoglyph_injection",
                "severity": "warning",
                "detail": f"西里尔/希腊同形字混入拉丁单词（肉眼不可辨，机器视为不同字符）：{shown}{extra}",
            }
        )

    # 3. 行内异常空白串（≥3 连续空格/tab；行首缩进豁免）
    ws_hits = []
    for li, line in enumerate(body.split("\n"), start=1):
        content = line.lstrip()
        indent = len(line) - len(content)
        for m in re.finditer(r"[ \t]{3,}", content):
            ws_hits.append((li, indent + m.start() + 1, len(m.group(0))))
    if ws_hits:
        summary["whitespaceRuns"] = len(ws_hits)
        shown = ", ".join(f"L{ln}C{c}×{n}" for ln, c, n in ws_hits[:5])
        extra = f" 等 {len(ws_hits)} 处" if len(ws_hits) > 5 else ""
        issues.append(
            {
                "type": "whitespace_anomaly",
                "severity": "info",
                "detail": f"行内异常空白串（弱信号，排版也可能如此）：{shown}{extra}",
            }
        )

    warnings = [i for i in issues if i["severity"] == "warning"]
    return {
        "ok": not warnings,
        "issues": issues,
        "summary": summary,
        "note": "痕迹取证为客观字符级证据；发现痕迹说明文本经非常规处理，是否构成问题由人工复核判断",
    }


ABSOLUTE_ZH = ["显然", "必然", "无疑", "完全证明", "彻底解决", "极大地", "显著优于", "首次实现", "完美", "毋庸置疑"]
ABSOLUTE_EN = ["clearly", "obviously", "undoubtedly", "proves that", "completely solves", "first ever", "the only way"]
HEDGE_ZH = ["可能", "或许", "一定程度上", "在某种程度上", "相对而言", "倾向于", "大约", "约为", "接近于", "有助于", "或受", "大致", "大体上"]
HEDGE_EN = ["may", "might", "suggest", "appears", "likely", "possibly", "approximately", "relatively"]


def check_hedging(markdown: str) -> dict:
    """逐节断言强度对冲画像：绝对化用词密集且零对冲的章节给出警告。

    学术写作惯例：强断言需伴随限定或证据引用；全篇无对冲往往是过度声明信号。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": [], "sections": []}
    body, _refs = _split_body_references(markdown)
    blocks = [(t, txt) for t, txt in _split_h2_blocks(body) if t != "(front matter)" or len(txt.strip()) > 200]

    def _count(words, text):
        total = 0
        for w in words:
            if re.search(r"[a-z]", w):
                total += len(re.findall(rf"\b{re.escape(w)}\b", text, flags=re.I))
            else:
                total += text.count(w)
        return total

    issues = []
    profile = []
    for title, text in blocks:
        abs_n = _count(ABSOLUTE_ZH, text) + _count(ABSOLUTE_EN, text)
        hedge_n = _count(HEDGE_ZH, text) + _count(HEDGE_EN, text)
        profile.append({"section": title, "absoluteTerms": abs_n, "hedges": hedge_n})
        if abs_n >= 3 and hedge_n == 0:
            issues.append({"type": "unhedged_section", "severity": "warning", "detail": f"章节 '{title}' 出现 {abs_n} 处绝对化表述且无任何对冲措辞"})
    for word in ABSOLUTE_ZH:
        for line, snip in _find_pattern(body, re.escape(word)):
            issues.append({"type": "absolute_term", "severity": "info", "line": line, "detail": f"绝对化表述 '{snip}'——确认有直接证据支撑"})
    # 英文绝对词此前只参与章节级阈值计数，从不逐条报告——英文稿的
    # "undoubtedly/proves that" 单处出现完全不可见。补逐条 info 级报告。
    for word in ABSOLUTE_EN:
        for line, snip in _find_pattern(body, re.escape(word), re.IGNORECASE):
            issues.append({"type": "absolute_term", "severity": "info", "line": line, "detail": f"绝对化表述 '{snip}'——确认有直接证据支撑"})
    return {"ok": not issues, "issues": issues, "sections": profile, "note": "绝对化本身不是错误；逐项确认证据后可保留"}


# ---------------------------------------------------------------------------
# 文献完整性与链接可信（审稿人/编辑部的常见退回理由）
# ---------------------------------------------------------------------------

def check_references_completeness(markdown: str) -> dict:
    """逐条文献完整性：缺年份、缺来源、缺卷期页、中文条目缺 GB/T 7714 类型标识、DOI 语法异常。

    文献表不完整是编辑部第一道退回理由：缺来源的条目无法核验，缺 [J]/[M]
    标识不符合国标。全部为确定性规则。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    entries = _extract_reference_entries(markdown)
    issues = []
    for idx, e in enumerate(entries, 1):
        ym = re.search(r"\((?:19|20)\d{2}[a-z]?\)|(?:19|20)\d{2}[.,;:]", e)
        if not ym:
            issues.append({"type": "missing_year", "severity": "error", "detail": f"第 {idx} 条缺年份，无法核验"})
            after = e
        else:
            after = e[ym.end():]
        if len(after.strip().strip(".,;，。；")) < 4:
            issues.append({"type": "missing_source", "severity": "error", "detail": f"第 {idx} 条缺来源（期刊名/出版社/预印本平台）——无法定位原文"})
        if not re.search(r"\d+\s*[（(]?\d{1,4}[）)]?\s*[,：:]\s*\d+", after) and not re.search(r"\b\d+\s*[-–—]\s*\d+\b", after):
            issues.append({"type": "missing_pages", "severity": "info", "detail": f"第 {idx} 条缺卷期页码（图书/网页类可忽略）"})
        if re.search(r"[一-鿿]", e) and not re.search(r"\[[A-Z]{1,2}(?:/OL)?\]", e):
            issues.append({"type": "missing_type_marker", "severity": "info", "detail": f"第 {idx} 条为中文文献但缺文献类型标识（[J]/[M]/[C]/[D]），不符合 GB/T 7714"})
        for dm in re.finditer(r"10\.(\d+)", e):
            if not 4 <= len(dm.group(1)) <= 9:
                issues.append({"type": "malformed_doi", "severity": "warning", "detail": f"第 {idx} 条 DOI 注册符长度异常（10.{dm.group(1)}），应为 10.4~9位数字/…"})
            break
        dm2 = re.search(r"(?:doi[:\s]+|doi\.org/)(10\.\d{4,9}/\S+)", e, re.I)
        if dm2:
            doi = dm2.group(1)
            if re.search(r"\s", doi):
                issues.append({"type": "malformed_doi", "severity": "warning", "detail": f"第 {idx} 条 DOI 中含空格（'{doi[:30]}…'），不是合法 DOI"})
            elif re.search(r"[.,;，。]$", doi):
                issues.append({"type": "malformed_doi", "severity": "warning", "detail": f"第 {idx} 条 DOI 以标点结尾（复制粘贴截断），解析会失败"})
    return {"ok": not issues, "issues": issues}


def check_references_recency(markdown: str, current_year: int | None = None) -> dict:
    """文献时效性信号：绝大多数参考文献早于 10 年前时提示综述可能陈旧。

    确定性启发式：参考文献年份取每条首个 19xx/20xx。未来年份已由
    check_references_format 单独报错，此处忽略。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    if current_year is None:
        current_year = time.localtime().tm_year
    entries = _extract_reference_entries(markdown)
    years = []
    for e in entries:
        ym = re.search(r"\b((?:19|20)\d{2})\b", e)
        if ym and int(ym.group(1)) <= current_year:
            years.append(int(ym.group(1)))
    if len(years) < 4:
        return {"ok": True, "issues": [], "note": f"可识别年份的文献不足 4 条（{len(years)}），不做时效性判定"}
    ages = sorted(current_year - y for y in years)
    median_age = ages[len(ages) // 2]
    stale_ratio = sum(1 for a in ages if a >= 10) / len(ages)
    issues = []
    if stale_ratio == 1.0:
        issues.append({"type": "stale_references", "severity": "warning", "detail": f"全部 {len(years)} 条文献均早于 {current_year - 10} 年（中位文献年龄 {median_age} 年），综述可能过时"})
    elif stale_ratio >= 0.7:
        issues.append({"type": "stale_references", "severity": "info", "detail": f"{int(stale_ratio * 100)}% 的文献早于 {current_year - 10} 年（中位年龄 {median_age} 年），建议补充近年研究"})
    return {"ok": not issues, "issues": issues, "summary": {"entries": len(years), "medianAge": median_age, "staleRatio": round(stale_ratio, 2)}}


PLACEHOLDER_PATTERN = re.compile(
    r"\bTODO\b|\bFIXME\b|\bTBD\b|XXX|\?\?\?|\[citation needed\]|\[insert[^]]*\]|lorem ipsum|待补充|待填写|待完成|待添加|此处插入|【占位",
    re.I,
)


def check_placeholders(markdown: str) -> dict:
    """占位符/未完成痕迹：TODO、???、[citation needed]、待补充 等——交付前必须清零。"""
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    starts = _line_starts(markdown)
    issues = []
    for m in PLACEHOLDER_PATTERN.finditer(markdown):
        issues.append({"type": "placeholder_left", "severity": "warning", "line": _pos_to_line(m.start(), starts), "detail": f"未完成痕迹 '{m.group(0)}'——交付前必须清除"})
    return {"ok": not issues, "issues": issues}


# 模糊归因：向不具名的"研究/专家"借权威却同句无任何引注——学界公认的
# AI 文本"空润感"核心特征（polished but vague）。同句含引注则豁免。
VAGUE_ATTRIBUTION_ZH = [
    "众所周知", "人们普遍认为", "普遍认为", "大量研究表明", "越来越多的研究表明",
    "有研究表明", "有研究显示", "研究表明", "专家认为", "专家指出", "一般认为", "有人说",
]
VAGUE_ATTRIBUTION_EN = [
    "studies have shown", "studies show", "studies suggest", "research shows",
    "research suggests", "research indicates", "it is widely believed",
    "widely accepted that", "experts agree", "experts believe", "experts say",
    "scientists say", "analysts say", "industry insiders", "some argue", "many argue",
    "critics argue",
]
_CITATION_IN_SENTENCE = re.compile(
    r"\[\d+(?:[，,]\s*\d+)*\]"
    r"|\(\s*[A-Za-z][^()]{0,40}?\d{4}\s*\)"
    r"|（[^（）]{0,40}?\d{4}[^（）]{0,10}?）"
    r"|\bet al\b",
    re.I,
)


def check_vague_attribution(markdown: str) -> dict:
    """模糊归因检查：句子引用了不具名的"研究/专家/普遍认为"却同句无任何引注。

    这是 AI 代写文本"光润但空洞"（polished but vague）的核心特征，也是审稿人
    高频意见 "source?" 的来源。同句含 [1]、(Smith, 2020)、（王五，2021）或
    et al 即视为已溯源，豁免。severity=warning：补引注或删归因，二选一。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    body, _refs = _split_body_references(markdown)
    body = _blank_fences(body)
    starts = _line_starts(body)
    issues = []
    suppressed = 0
    for sent in _split_sentences(body, keep_punct=True):
        if not sent.strip() or _CITATION_IN_SENTENCE.search(sent):
            continue
        hit = None
        for phrase in VAGUE_ATTRIBUTION_ZH:
            if phrase in sent:
                hit = phrase
                break
        if hit is None:
            for phrase in VAGUE_ATTRIBUTION_EN:
                if re.search(rf"\b{re.escape(phrase)}\b", sent, re.I):
                    hit = phrase
                    break
        if hit is None:
            continue
        if sum(1 for i in issues if i["type"] == "vague_attribution") >= 8:
            suppressed += 1
            continue
        probe = sent.strip()[:30]
        pos = body.find(probe)
        issues.append({
            "type": "vague_attribution",
            "severity": "warning",
            "line": _pos_to_line(pos if pos >= 0 else 0, starts),
            "detail": f"模糊归因 '{hit}'——同句无任何引注，需补引文或改为可查证的具体表述",
        })
    if suppressed:
        issues.append({"type": "vague_attribution_suppressed", "severity": "info", "detail": f"另有 {suppressed} 处模糊归因未列出"})
    return {"ok": not issues, "issues": issues, "note": "同句含引注即豁免；本检查不判断真伪，只要求溯源落实"}


_SUSPICIOUS_HOSTS = {"example.com", "example.org", "example.net", "localhost", "test.com", "domain.com", "yoursite.com", "website.com", "foo.com", "bar.com"}
_BAD_URL_SUFFIXES = (".example", ".invalid", ".test", ".localhost", ".local")


def check_links(markdown: str, live: bool = False) -> dict:
    """链接可信检查：离线查语法与虚假特征；live=True 时逐个 HEAD 验活。

    离线可确定性检出：占位域名（example.com/localhost）、非法 TLD（.example/.invalid）、
    无主机名、含空格。live 模式逐个发 HEAD：404/410 为死链（warning），
    2xx/3xx 存活，其余或超时为"无法核验"（X 式诚实降级，最多验 20 条）。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    urls = []
    for u in re.findall(r"https?://[^\s<>\"')\]]+", markdown):
        u = u.rstrip(".,;，。；")
        if u not in urls:
            urls.append(u)
    issues = []
    checked = 0
    for u in urls:
        parsed = urllib.parse.urlparse(u)
        host = parsed.netloc.lower()
        if not host or "." not in host:
            issues.append({"type": "malformed_url", "severity": "warning", "detail": f"链接无有效主机名: {u[:60]}"})
            continue
        if host in _SUSPICIOUS_HOSTS or any(host.endswith("." + h) for h in _SUSPICIOUS_HOSTS):
            issues.append({"type": "placeholder_url", "severity": "warning", "detail": f"占位符域名（不会指向真实文献）: {u[:60]}"})
            continue
        if any(host.endswith(t) for t in _BAD_URL_SUFFIXES):
            issues.append({"type": "placeholder_url", "severity": "warning", "detail": f"保留/非法 TLD（虚假链接特征）: {u[:60]}"})
            continue
        if not live or checked >= 20:
            continue
        checked += 1
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "ScholarSeed/0.1 (link check)"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            if status >= 400:
                issues.append({"type": "dead_link", "severity": "warning", "detail": f"链接返回 HTTP {status}: {u[:60]}"})
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                issues.append({"type": "dead_link", "severity": "warning", "detail": f"死链（HTTP {e.code}）: {u[:60]}"})
            # 403/405（反爬/不支持 HEAD）等按无法核验处理，不报死链
        except Exception:
            issues.append({"type": "unverifiable_link", "severity": "info", "detail": f"无法核验（网络不可达或超时）: {u[:60]}"})
    note = "live=False 仅做离线语法与虚假特征检查" if not live else f"live 验活已完成 {checked}/{len(urls)} 条；403/405 反爬按无法核验处理"
    return {"ok": not issues, "issues": issues, "checked": len(urls), "note": note}


# 编码健康（门禁塔 L0 文件底座）：底座损坏时上层所有行号证据不可信。
# 高置信 mojibake 特征：UTF-8 字节流被按 Latin-1 误读的双字节序列
#（如 中→"ä¸­"、智能引号→"â€™"）；合法法文/德文重音字母后跟 ASCII 不命中。
_MOJIBAKE_RE = re.compile(
    r"Ã[©¨®°¼½¾±¸¹º»]"
    r"|â€[™œšž]"
    r"|[\u00e4\u00e5\u00e6\u00e7\u00e8\u00e9\u00ea\u00eb\u00ec\u00ed\u00ee\u00ef\u00f1\u00f2\u00f3\u00f4\u00f5\u00f6\u00f8\u00f9\u00fa\u00fb\u00fc\u00fd][\u0080-\u00bf\u00c0-\u00ff]",
    re.UNICODE,
)
_CID_MARKER_RE = re.compile(r"\(cid:\d+\)")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def check_encoding(markdown: str) -> dict:
    """编码健康检查：U+FFFD 替换符、(cid:NN) PDF 提取残留、mojibake 乱码、控制字符、文中部 BOM。

    底座层检查：替换符/CID 意味着文本在该处**不可读**（error 级），乱码/控制字符是
    高置信损坏特征（warning 级）。只报告客观字符事实，不猜测成因归属。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    starts = _line_starts(markdown)
    issues = []

    def _add(itype: str, severity: str, pos: int, detail: str) -> None:
        issues.append({"type": itype, "severity": severity, "line": _pos_to_line(pos, starts), "detail": detail})

    counts = {"replacement_char": 0, "cid_extracted": 0, "mojibake": 0, "control_char": 0, "bom_midfile": 0}
    for m in re.finditer("\ufffd", markdown):
        counts["replacement_char"] += 1
        if counts["replacement_char"] <= 3:
            _add("replacement_char", "error", m.start(), f"U+FFFD 替换符（该处字符已不可读，源文件编码损坏或转换丢字）×{counts['replacement_char']}")
    for m in _CID_MARKER_RE.finditer(markdown):
        counts["cid_extracted"] += 1
        if counts["cid_extracted"] <= 3:
            _add("cid_extracted", "error", m.start(), f"(cid:{m.group(0)[5:-1]}) PDF 提取残留——该处为字形编号而非真实文字（中文 CID 编码 PDF 常见），文本不可审计")
    for m in _MOJIBAKE_RE.finditer(markdown):
        counts["mojibake"] += 1
        if counts["mojibake"] <= 5:
            _add("mojibake", "warning", m.start(), f"疑似编码乱码 '{m.group(0)}'——UTF-8 被按 Latin-1 误读的特征序列，请核对源文件编码")
    for m in _CONTROL_CHAR_RE.finditer(markdown):
        counts["control_char"] += 1
        if counts["control_char"] <= 3:
            _add("control_char", "warning", m.start(), f"异常控制字符 U+{ord(m.group(0)):04X}——不可见但会破坏解析与排版")
    for m in re.finditer("\ufeff", markdown):
        if m.start() > 0:
            counts["bom_midfile"] += 1
            if counts["bom_midfile"] <= 2:
                _add("bom_midfile", "info", m.start(), "文中部 BOM（U+FEFF）——拼接文件常见残留，建议清除")

    total = sum(counts.values())
    if total > len(issues):
        issues.append({"type": "encoding_suppressed", "severity": "info", "detail": f"编码问题共 {total} 处，已按类型限量展示；计数见 summary"})
    return {"ok": not issues, "issues": issues[:10], "summary": counts, "note": "替换符/CID 为 error（文本不可读），乱码/控制字符为 warning；只报告字符事实，不猜测成因"}


# P 合法前提层：投稿资格声明存在性。工具只查"写了没有"，声明真伪归作者与机构。
_ETHICS_STATEMENTS = [
    ("ethics_approval", "伦理审批/知情同意", r"伦理(?:审查|批准|委员会)|知情同意|informed consent|ethics (?:approval|committee|review)|IRB|institutional review board"),
    ("conflict_of_interest", "利益冲突披露", r"利益冲突|conflicts? of interest|competing (?:interests|financial)|declarations? of interest"),
    ("ai_disclosure", "AI 使用披露（AIGC 合规）", r"(?:人工智能|AI|AIGC|生成式(?:人工智能)?|ChatGPT|GPT|大语言模型|大模型)[^。；;\n]{0,24}(?:披露|声明|辅助写作|辅助完成|使用情况|未使用|不涉及)|(?:未使用|不涉及|未借助)[^。；;\n]{0,16}(?:人工智能|AI|AIGC|生成式|ChatGPT|大语言模型|大模型)|(?:AI[- ]assisted|generative AI|large language model|\bLLM\b)[^.\n]{0,30}(?:disclos|declar|assist|use)|\bno\s+AI\b"),
    ("data_availability", "数据可用性声明", r"数据可用性|数据获得|数据获取|data availability|availability of (?:the )?data|data sharing"),
]
_HUMAN_SUBJECTS_RE = re.compile(r"患者|病人|受试者|被试|参与者|受访者|访谈对象|participants|patients|subjects|interviewees|respondents", re.I)


def check_ethics_statements(markdown: str, genre: str = "empirical") -> dict:
    """合法前提检查：伦理审批/知情同意、利益冲突、AI 使用披露、数据可用性声明是否在场。

    缺伦理声明且正文提及人类受试者 = 桌拒级红线（error）；其余缺失为 warning。
    本检查只验证声明存在性与非空，不判断声明真伪——真实性由作者与机构负责。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    body, _refs = _split_body_references(markdown)
    body = _blank_fences(body)
    starts = _line_starts(body)
    found = {}
    for key, label, pat in _ETHICS_STATEMENTS:
        m = re.search(pat, body, flags=re.I)
        if m:
            found[key] = _pos_to_line(m.start(), starts)
    issues = []
    human_subjects = bool(_HUMAN_SUBJECTS_RE.search(body))
    is_empirical = (genre or "empirical").lower() in ("empirical", "thesis")
    if "ethics_approval" not in found:
        if human_subjects:
            issues.append({"type": "ethics_missing_human_subjects", "severity": "error", "detail": "正文提及人类受试者（患者/参与者/被试等）但未见伦理审批或知情同意声明——期刊合规桌拒级红线"})
        elif is_empirical:
            issues.append({"type": "ethics_missing", "severity": "warning", "detail": "实证论文未见伦理声明（如确不涉人类/动物实验，请在方法中显式说明豁免依据）"})
    if "conflict_of_interest" not in found:
        issues.append({"type": "coi_missing", "severity": "warning", "detail": "未见利益冲突披露声明（conflict of interest / 利益冲突）——多数期刊为必备声明"})
    if "ai_disclosure" not in found:
        issues.append({"type": "ai_disclosure_missing", "severity": "warning", "detail": "未见 AI 使用披露（AIGC 合规：使用/未使用均需显式声明）——国内学位与期刊规范趋严"})
    if "data_availability" not in found and is_empirical:
        issues.append({"type": "data_availability_missing", "severity": "warning", "detail": "实证论文未见数据可用性声明（data availability statement）——可复现性基本要求"})
    summary = {"found": {k: v for k, v in found.items()}, "missing": [k for k, _, _ in _ETHICS_STATEMENTS if k not in found], "humanSubjectsDetected": human_subjects, "genre": genre}
    return {"ok": not issues, "issues": issues, "summary": summary, "note": "声明存在性检查：工具查'写了没有'，真伪归人；涉人研究缺伦理声明为 error"}


# L1 存在层：撤稿筛查。撤稿是 Crossref/S2 记录的客观事实，但基础设施失败
# 沿用 X 级纪律——无法核验永不触发门禁，只有"确认被撤稿"才是 error。
_RETRACT_NOTICE_TITLE_RE = re.compile(r"retrac|withdrawn|撤稿", re.I)


def _retraction_probe(doi: str = "", title: str = "") -> dict:
    """查询单条文献的撤稿状态。

    信号源（命中任一即判定）：Crossref 的 update-to（type 含 retraction）、
    relation.is-retracted-by、标题本身为撤稿声明（Retraction Notice）。
    返回 {status: ok|retracted|notice|unverifiable|unmatched, ...}。
    """
    raw = None
    if doi.strip():
        url = f"{CROSSREF_API}/{urllib.parse.quote(doi.strip(), safe='')}"
        try:
            raw = _fetch_json(url, headers=_crossref_headers()).get("message", {})
        except urllib.error.HTTPError as e:
            if e.code in RETRYABLE_HTTP_CODES:
                return {"status": "unverifiable", "note": f"Crossref 暂不可达 (HTTP {e.code})"}
            return {"status": "unverifiable", "note": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"status": "unverifiable", "note": f"网络不可达：{e}"}
    else:
        matched = _crossref_by_title(title)
        resolved_doi = str(matched.get("doi", "") or "")
        if not matched.get("verified") or not resolved_doi:
            return {"status": "unmatched", "note": str(matched.get("note", "未命中，跳过撤稿核查"))}
        url = f"{CROSSREF_API}/{urllib.parse.quote(resolved_doi, safe='')}"
        try:
            raw = _fetch_json(url, headers=_crossref_headers()).get("message", {})
        except Exception as e:
            return {"status": "unverifiable", "note": f"网络不可达：{e}"}
        doi = resolved_doi
    title0 = ((raw.get("title") or [""]) or [""])[0]
    relation = raw.get("relation") or {}
    update_to = raw.get("update-to") or []
    retract_updates = [u for u in update_to if "retract" in str(u.get("type", "")).lower()]
    evidence = []
    if relation.get("is-retracted-by"):
        evidence.append(f"relation.is-retracted-by → {relation['is-retracted-by']}")
    if retract_updates:
        evidence.append(f"update-to(type=retraction) → {[u.get('DOI') for u in retract_updates]}")
    if evidence:
        return {"status": "retracted", "doi": doi, "title": title0, "evidence": evidence}
    if _RETRACT_NOTICE_TITLE_RE.search(title0):
        return {"status": "notice", "doi": doi, "title": title0, "note": "该条目本身是撤稿声明（Retraction Notice）——综述引用属正常，实证引用请人工确认意图"}
    return {"status": "ok", "doi": doi, "title": title0}


def check_retraction(markdown: str, max_entries: int = 30) -> dict:
    """撤稿筛查（L1 存在层，联网）：逐条检查被引文献是否已被撤稿。

    引用已撤稿文献是学术诚信硬伤——稿件引用的结论若来自被撤成果，审稿人
    与编辑有权直接质疑。判定依据 Crossref 记录（update-to / relation /
    撤稿声明标题），属外部 API 事实而非启发式。基础设施失败按 X 级纪律
    记为 unverifiable（info），永不触发门禁。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    entries = _extract_reference_entries(markdown)
    if not entries:
        return {"ok": True, "issues": [], "summary": {"note": "未识别到含年份的文献条目"}, "checked": 0}
    truncated = len(entries) > max_entries
    issues = []
    stats = {"checked": 0, "retracted": 0, "notice": 0, "unverifiable": 0, "unmatched": 0}
    for idx, entry in enumerate(entries[:max_entries], 1):
        doi_m = DOI_PATTERN.search(entry)
        title_hint = _entry_title(entry)
        if not doi_m and not _title_hint_long_enough(title_hint):
            stats["unmatched"] += 1
            continue
        try:
            probe = _retraction_probe(doi=_clean_doi(doi_m.group(0)) if doi_m else "", title=title_hint)
        except Exception as e:
            probe = {"status": "unverifiable", "note": f"查询异常：{e}"}
        status = probe.get("status", "unverifiable")
        loc = f"第 {idx} 条"
        entry_short = entry[:44].replace("\n", " ")
        if status == "retracted":
            stats["retracted"] += 1
            issues.append({"type": "cited_retracted_work", "severity": "error", "line": idx, "detail": f"{loc}「{entry_short}…」已被撤稿（{'；'.join(probe.get('evidence', []))}）——引用撤稿成果是学术诚信硬伤，必须替换或删除"})
        elif status == "notice":
            stats["notice"] += 1
            issues.append({"type": "cited_retraction_notice", "severity": "info", "line": idx, "detail": f"{loc}「{entry_short}…」本身是撤稿声明，请确认引用意图"})
            stats["checked"] += 1
            continue
        elif status == "unverifiable":
            stats["unverifiable"] += 1
            issues.append({"type": "retraction_unverifiable", "severity": "info", "line": idx, "detail": f"{loc}撤稿状态无法核验（{probe.get('note', '')}）——不计入门禁失败"})
            stats["checked"] += 1
            continue
        elif status == "unmatched":
            stats["unmatched"] += 1
            continue
        stats["checked"] += 1
    note = f"已核 {stats['checked']}/{len(entries)} 条" + (f"（超过上限仅查前 {max_entries} 条）" if truncated else "")
    return {"ok": not any(i["severity"] == "error" for i in issues), "issues": issues, "summary": stats, "note": note + "；X 级纪律：无法核验永不触发门禁"}


# L2 契合层：引证契合。工具只做词汇级契合提示（stdlib 射程），
# "源文是否真支持该主张"的语义级判断需要模型推理，属明确不做（见 ARCHITECTURE.md）。
_FIT_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were", "which", "their",
    "have", "has", "had", "not", "but", "can", "may", "our", "its", "also", "than", "into", "such",
    "these", "those", "between", "among", "based", "using", "results", "result", "study", "paper",
    "we", "propose", "present", "show", "shown", "suggest", "suggests", "found",
}
_STRONG_CLAIM_RE = re.compile(
    r"significantly|substantially|proves? that|demonstrates? that|confirms? that|validates? that|establishes? that"
    r"|显著(?:地)?(?:表?明|证明|优于|提升|降低|高于|低于)|证明了|证实了|验证了|确立了|显著(?:改善|提高|增强)",
    re.I,
)
_AUTHORYEAR_CITE_RE = re.compile(
    r"\(\s*([A-Za-z\u4e00-\u9fff][^(),;]{0,30}?)\s*,\s*((?:19|20)\d{2})[a-z]?\s*\)|（\s*([^（）,；]{1,30}?)\s*，?\s*((?:19|20)\d{2})[a-z]?）"
)


def _fit_terms(text: str) -> set:
    """契合度词元：拉丁实词(≥3 字母，去停用词) + 中文二元组。"""
    low = text.lower()
    terms = {w for w in re.findall(r"[a-z]{3,}", low) if w not in _FIT_STOPWORDS}
    terms.update(re.findall(r"[\u4e00-\u9fff]{2}", low))
    return terms


def _citation_source_probe(doi: str, title: str) -> dict:
    """获取所引文献的标题与摘要（供契合度比对）；失败诚实降级。

    返回 {status: matched|unmatched|unverifiable, title, abstract}。
    """
    raw = None
    if doi.strip():
        url = f"{CROSSREF_API}/{urllib.parse.quote(doi.strip(), safe='')}"
        try:
            raw = _fetch_json(url, headers=_crossref_headers()).get("message", {})
        except Exception as e:
            return {"status": "unverifiable", "note": str(e), "title": "", "abstract": ""}
        src_title = ((raw.get("title") or [""]) or [""])[0]
        abstract = re.sub(r"<[^>]+>", " ", raw.get("abstract", "") or "")
        return {"status": "matched", "title": src_title, "abstract": abstract}
    if not _title_hint_long_enough(title):
        return {"status": "unmatched", "note": "标题线索不足", "title": "", "abstract": ""}
    try:
        matched = _crossref_by_title(title)
    except Exception as e:
        return {"status": "unverifiable", "note": str(e), "title": "", "abstract": ""}
    if not matched.get("verified"):
        return {"status": "unmatched", "note": str(matched.get("note", "未命中")), "title": "", "abstract": ""}
    resolved = str(matched.get("doi", "") or "")
    abstract = ""
    if resolved:
        try:
            raw = _fetch_json(f"{CROSSREF_API}/{urllib.parse.quote(resolved, safe='')}", headers=_crossref_headers()).get("message", {})
            abstract = re.sub(r"<[^>]+>", " ", raw.get("abstract", "") or "")
        except Exception:
            abstract = ""
    return {"status": "matched", "title": str(matched.get("title", "")), "abstract": abstract}


def check_claim_citation_fit(markdown: str, max_assessed: int = 15) -> dict:
    """引证契合检查（L2 契合层，联网+缓存）：强主张句与所引文献标题/摘要的词汇契合度。

    只检查"带强主张措辞 + 引注"的句子：主张句词元与所引文献标题/摘要词元的
    重叠率过低时提示人工复核——词汇契合度低 ≠ 引文错误，但 polished-but-unsupported
    的主张是审稿人"source?"质疑的高发点。无法获取所引文献元数据时诚实降级，
    不参与评估也不计入门禁失败。severity=warning（准门禁，需人工复核）。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    body, _refs = _split_body_references(markdown)
    entries = _extract_reference_entries(markdown)
    if not entries:
        return {"ok": True, "issues": [], "summary": {"note": "未识别到文献条目，无法建立引用映射"}}
    issues = []
    stats = {"strongClaimCitations": 0, "assessed": 0, "weak": 0, "unassessed": 0}
    starts = _line_starts(body)
    for pos, sent in iter_sentences(body):
        if stats["assessed"] >= max_assessed:
            break
        num_m = re.search(r"\[(\d{1,3})\]", sent)
        entry = None
        if num_m and 1 <= int(num_m.group(1)) <= len(entries):
            entry = entries[int(num_m.group(1)) - 1]
        else:
            ay = _AUTHORYEAR_CITE_RE.search(sent)
            if ay:
                author = (ay.group(1) or ay.group(3) or "").strip().split()[0]
                year = ay.group(2) or ay.group(4)
                for e in entries:
                    if author in e and year in e:
                        entry = e
                        break
        if entry is None or not _STRONG_CLAIM_RE.search(sent):
            continue
        stats["strongClaimCitations"] += 1
        doi_m = DOI_PATTERN.search(entry)
        title_hint = _entry_title(entry)
        if not doi_m and not _title_hint_long_enough(title_hint):
            stats["unassessed"] += 1
            continue
        probe = _citation_source_probe(doi=_clean_doi(doi_m.group(0)) if doi_m else "", title=title_hint)
        if probe["status"] != "matched":
            stats["unassessed"] += 1
            continue
        stats["assessed"] += 1
        claim_terms = _fit_terms(sent)
        src_terms = _fit_terms(probe["title"] + " " + probe["abstract"])
        if len(claim_terms) < 4 or len(src_terms) < 4:
            continue
        overlap = claim_terms & src_terms
        ratio = len(overlap) / min(len(claim_terms), len(src_terms))
        if ratio < 0.10:
            stats["weak"] += 1
            line = _pos_to_line(pos, starts)
            shared = "、".join(sorted(overlap)[:5]) if overlap else "无"
            issues.append({
                "type": "weak_citation_support",
                "severity": "warning",
                "line": line,
                "detail": f"强主张句与所引文献《{probe['title'][:36]}…》词汇契合度仅 {ratio:.0%}（共同词元：{shared}）——请人工确认引文是否支撑该主张",
            })
    if stats["unassessed"]:
        issues.append({"type": "fit_unassessed", "severity": "info", "detail": f"{stats['unassessed']} 处引用无法获取所引文献元数据（网络/未命中），未参与契合评估——不计入门禁失败"})
    note = f"强主张引用句 {stats['strongClaimCitations']} 处，已评估 {stats['assessed']} 处（上限 {max_assessed}）"
    return {"ok": not issues, "issues": issues, "summary": stats, "note": note + "；契合度低≠引文错误，warning 级提示人工复核"}


# L2 契合层：预印本-正式版错配。引用 arXiv 版而正式发表版已存在，
# 是审稿人常见 nitpick（引用元数据过时），确定性可查。
_ARXIV_ID_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})(?:v\d+)?|arxiv\s*preprint", re.I)


def check_version_mismatch(markdown: str, max_entries: int = 30) -> dict:
    """预印本-正式版错配检查（L2 契合层，联网）：引用 arXiv 预印本但正式发表版已存在。

    文献表条目含 arXiv 标识时，按标题在 Crossref 检索正式版本（相似度阈值防误配，
    复用 citation_verify 同一检索管线）；命中且非预印本自身（10.48550 DOI / report
    类型）即提示更新。仅存在预印本的文献不受影响。severity=warning。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    entries = _extract_reference_entries(markdown)
    if not entries:
        return {"ok": True, "issues": [], "summary": {"note": "未识别到文献条目"}}
    issues = []
    stats = {"arxivEntries": 0, "publishedFound": 0, "unassessed": 0}
    for idx, entry in enumerate(entries[:max_entries], 1):
        if not _ARXIV_ID_RE.search(entry):
            continue
        stats["arxivEntries"] += 1
        title_hint = _entry_title(entry)
        if not _title_hint_long_enough(title_hint):
            stats["unassessed"] += 1
            continue
        try:
            matched = _crossref_by_title(title_hint)
        except Exception:
            stats["unassessed"] += 1
            continue
        if not matched.get("verified"):
            stats["unassessed"] += 1
            continue
        doi = str(matched.get("doi", "") or "")
        mtype = str(matched.get("type", "") or "")
        if doi.startswith("10.48550/") or "report" in mtype.lower() or "arxiv" in doi.lower():
            continue  # 命中的是预印本自身记录，不算错配
        stats["publishedFound"] += 1
        entry_short = entry[:44].replace("\n", " ")
        issues.append({
            "type": "preprint_published_mismatch",
            "severity": "warning",
            "line": idx,
            "detail": f"第 {idx} 条「{entry_short}…」引用 arXiv 预印本，但已存在正式发表版《{str(matched.get('title', ''))[:40]}》(DOI: {doi or '未知'})——建议更新引用（部分文献可能仅有预印本，请核实）",
        })
    if stats["unassessed"]:
        issues.append({"type": "version_unassessed", "severity": "info", "detail": f"{stats['unassessed']} 条 arXiv 条目无法核验正式版（网络/标题线索不足），不计入门禁失败"})
    return {"ok": not issues, "issues": issues, "summary": stats, "note": "warning 级：预印本引用并非错误，但正式版已存在时应更新引用元数据"}


# 样本量数字支持千分位逗号（"1,500 名参与者"），解析时去逗号——英文论文常见写法
ZH_SAMPLE_PATTERN = re.compile(r"(样本量|样本数|样本|被试|受试者|参与者)\s*(?:量|数)?\s*[为约是=:]?\s*(\d{1,3}(?:,\d{3})+|\d{2,6})\s*([名份个人])?")
EN_SAMPLE_PATTERN = re.compile(r"\b([Nn])\s*=\s*(\d{1,3}(?:,\d{3})+|\d{2,6})\b")
# 英文 "a sample of 250 employees / a cohort of 1,200 patients" 口径（此前整段隐形）
EN_SAMPLE_OF_PATTERN = re.compile(r"\b(?:sample|cohort|population)\s+(?:size\s+)?of\s+(\d{1,3}(?:,\d{3})+|\d{2,6})\b", re.I)
EN_SAMPLE_CONTEXT = re.compile(r"sample|participant|subject|respondent|observation", re.I)


def check_numbers(markdown: str) -> dict:
    """全文数字一致性检查：同类样本口径矛盾、百分比加和越界、比例>100%。"""
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": []}
    body, _refs = _split_body_references(markdown)
    body = _blank_fences(body)  # 代码块中的数字（示例/注释）不是论文数据
    starts = _line_starts(body)
    issues = []

    # 1) 样本口径一致性：按关键词分组比较（发放/回收/有效等限定词单独成桶）
    buckets = {}
    for m in ZH_SAMPLE_PATTERN.finditer(body):
        keyword = m.group(1).lower()
        value = int(m.group(2).replace(",", ""))
        prefix_start = max(0, m.start() - 8)
        context = body[prefix_start : m.start()]
        qualifier = ""
        for q in ("发放", "回收", "有效", "无效"):
            if q in context:
                qualifier = q
                break
        buckets.setdefault(("zh:" + keyword, qualifier), []).append((value, _pos_to_line(m.start(), starts)))
    for m in EN_SAMPLE_PATTERN.finditer(body):
        window = body[max(0, m.start() - 80) : m.end() + 80]
        if not EN_SAMPLE_CONTEXT.search(window):
            continue  # 数学/公式中的 N=… 无样本语义，豁免（佩雷尔曼案例）
        buckets.setdefault(("en:N", ""), []).append((int(m.group(2).replace(",", "")), _pos_to_line(m.start(), starts)))
    for m in EN_SAMPLE_OF_PATTERN.finditer(body):
        buckets.setdefault(("en:N", ""), []).append((int(m.group(1).replace(",", "")), _pos_to_line(m.start(), starts)))
    for (keyword, qualifier), hits in sorted(buckets.items()):
        values = sorted({v for v, _ in hits})
        label = keyword + (f"-{qualifier}" if qualifier else "")
        if len(values) > 1 and (max(values) - min(values)) > max(2, max(values) * 0.02):
            locs = ", ".join(f"L{ln}:{v}" for v, ln in hits)
            issues.append({"type": "sample_size_conflict", "severity": "error", "detail": f"'{label}' 口径出现多个不同数值: {locs}"})

    # 2) 单行百分比加和 > 100.5%（排除含"发放/回收/留存"等非互斥场景）
    for i, line in enumerate(body.splitlines(), 1):
        if any(q in line for q in ("发放", "回收", "同比", "环比", "增长率")):
            continue
        # 置信区间的 95%/90% 不是分类占比，先剔除再统计
        scan = re.sub(r"\d+(?:\.\d+)?\s*%\s*CI\b", "", line, flags=re.I)
        scan = re.sub(r"\d+(?:\.\d+)?%\s*置信区间", "", scan)
        # 全角％与半角%统一捕获（旧写法 '...%|％' 的 ％ 分支无捕获组，float('') 崩溃）
        percents = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*[％%]", scan)]
        percents = [x for x in percents if x <= 100]
        if len(percents) >= 2 and sum(percents) > 100.5:
            issues.append({"type": "percent_overflow", "severity": "error", "line": i, "detail": f"同行百分比加和 {sum(percents):.1f}% > 100%，若为互斥分类则存在数据矛盾"})

    # 3) 孤立比例越界：单独出现 >100% 的占比类数字
    for line, snip in _find_pattern(body, r"(?:占|比例[为约]?|占比)\s*(\d{3,}(?:\.\d+)?)\s*[％%]"):
        issues.append({"type": "ratio_over_100", "severity": "error", "line": line, "detail": f"占比数值异常: {snip}（>100%）"})

    # 4) 分桶加和一致性："总样本N，其中a…另外b…"（互斥分组标记在场）时分桶加和
    #    或任一分桶超过总量，即为结构性数据矛盾（经典造假信号）。段落级扫描：
    #    容器与分桶常被句号分隔（"调查了300名学生。其中180名…另外200名…"），
    #    故不依赖"样本"关键词取数，而用"数字+单位"并叠加三重防误报守卫：
    #    ① 发放/回收/有效等嵌套流量口径（前缀含关键词）不入桶；
    #    ② 某项≈其余各项之和视为合法的总分层写法，放行；
    #    ③ 仅两处计数时，只有容器带"样本/被试"类关键词且分桶更大才报警。
    partition_marker = re.compile(r"其中|另外|其余|剩下")
    unit_number = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{2,6})\s*(?:名|人|份)")
    flow_qualifier = re.compile(r"发放|回收|有效|无效|回收率")
    sample_keyword = re.compile(r"样本|被试|受试者|参与者")
    for para in re.split(r"\n\s*\n", body):
        if not partition_marker.search(para):
            continue
        hits = []
        for m in unit_number.finditer(para):
            prefix = para[max(0, m.start() - 6) : m.start()]
            if flow_qualifier.search(prefix):
                continue
            hits.append((int(m.group(1).replace(",", "")), _pos_to_line(m.start(), starts), prefix))
        if len(hits) < 2:
            continue
        values = [v for v, _, _ in hits]
        total = sum(values)
        if any(abs(v - (total - v)) <= 2 for v in values):
            continue  # 某项即总体（如"…共630人"收尾），加和自洽
        if len(hits) == 2:
            (container, container_line, prefix0), (bucket, bucket_line, _) = hits[0], hits[1]
            if not (sample_keyword.search(prefix0) and bucket > container):
                continue
            buckets = [(bucket, bucket_line)]
        else:
            container, container_line = hits[0][0], hits[0][1]
            buckets = [(v, ln) for v, ln, _ in hits[1:]]
        bucket_sum = sum(v for v, _ in buckets)
        max_bucket = max(v for v, _ in buckets)
        if bucket_sum > container or max_bucket > container:
            worst_line = min(ln for _, ln in buckets)
            issues.append(
                {
                    "type": "partition_sum_overflow",
                    "severity": "error",
                    "line": worst_line,
                    "detail": (
                        f"分桶加和 {' + '.join(str(v) for v, _ in buckets)} = {bucket_sum}，"
                        f"超出总样本口径 {container}（L{container_line}）；"
                        "'其中/另外' 表述为互斥分组，各组之和不应超过总量"
                    ),
                }
            )

    # 5) 英文互斥分桶："We surveyed 320 patients, of whom 180 received X, while 200 received Y."
    #    锚点 of whom/which/these 之后同句的数字为分桶，锚点前最后一个数字为总口径。
    en_anchor = re.compile(r"\bof (?:whom|which|these)\b", re.I)
    en_number = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{2,6})\b(?![%％])")
    for para in re.split(r"\n\s*\n", body):
        if not en_anchor.search(para):
            continue
        for sent in re.split(r"(?<=[.!?])\s*", para):
            am = en_anchor.search(sent)
            if not am:
                continue
            nums = [(int(x.group(1).replace(",", "")), x.start()) for x in en_number.finditer(sent)]
            if len(nums) < 3:
                continue
            before = [v for v, pos in nums if pos < am.start()]
            after = [v for v, pos in nums if pos > am.start()]
            if not before or len(after) < 2:
                continue
            container = before[-1]
            total = sum(after) + container
            if any(abs(v - (total - v)) <= 2 for v in (*after, container)):
                continue  # 某项即总体（总分层写法），加和自洽
            bucket_sum = sum(after)
            if bucket_sum > container or max(after) > container:
                issues.append(
                    {
                        "type": "partition_sum_overflow",
                        "severity": "error",
                        "detail": (
                            f"分桶加和 {' + '.join(map(str, after))} = {bucket_sum}，"
                            f"超出总样本口径 {container}；'of whom/which' 表述为互斥分组，各组之和不应超过总量"
                        ),
                    }
                )

    # 6) 摘要 vs 正文样本口径：摘要声明的样本数必须在正文中再次出现。
    #    "摘要说 200 人、方法说 300 人"是编辑与审稿人都抓的经典不一致。
    #    摘要内用"数字+单位"取数（不依赖"样本"关键词——"调查了250名"同样成立）。
    try:
        blocks = _split_h2_blocks(body)
    except NameError:
        blocks = []
    abstract_text = next((t for title, t in blocks if re.search(r"摘要|abstract", title, re.I)), "")
    if abstract_text:
        abstract_unit = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{2,6})\s*(?:名|人|份)", re.I)
        abstract_en_unit = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{2,6})\s+(?:participants|students|employees|respondents|patients|subjects|firms|households)\b", re.I)
        claimed = set()
        for m in abstract_unit.finditer(abstract_text):
            claimed.add(int(m.group(1).replace(",", "")))
        for m in abstract_en_unit.finditer(abstract_text):
            claimed.add(int(m.group(1).replace(",", "")))
        rest = body.replace(abstract_text, "", 1)
        for v in sorted(claimed):
            # 不能用 \b：汉字与数字之间无词边界（"了300名"），改用数字否定环视
            if not re.search(rf"(?<!\d){v}(?!\d)", rest):
                issues.append({"type": "abstract_number_mismatch", "severity": "warning", "detail": f"摘要声明的样本数 {v} 未在正文中出现——摘要与正文口径可能不一致"})
    return {"ok": not issues, "issues": issues, "note": "发放/回收/有效等非互斥场景已自动豁免"}


# ---------------------------------------------------------------------------
# 统计诚信红线 + 一键全量审计
# ---------------------------------------------------------------------------

STAT_TEST_PATTERN = re.compile(
    r"t\s*检验|t[-\s]?test|ANOVA|方差分析|卡方|χ\s*²?|chi-square|Wilcoxon|Mann-Whitney|"
    r"Fisher|Kruskal|回归分析?|regression|Pearson|Spearman|相关分析|F\s*检验|U\s*检验",
    re.I,
)
# 注意不能用 \b 定位 p：中文论文常把 p 紧贴汉字书写（"表明p=0.000"），
# 汉字与 p 之间在 Python re 里不存在词边界，\b 会整体漏检。
# 改用否定环视：p 前不能是 ASCII 字母/数字（排除 map= 等误配），
# 数值后不能紧跟数字（避免 "p=0.000显著" 被截断成 p=0）。
P_VALUE_PATTERN = re.compile(r"(?<![A-Za-z0-9])p\s*[=<>≤≥]\s*(\d+(?:\.\d+)?)(?![0-9])", re.I)
EFFECT_SIZE_PATTERN = re.compile(r"效应量|Cohen'?s?\s*d|η\s*2?|η²|r\s*=|odds\s*ratio|OR\s*=|f²|Hedges?", re.I)
CI_PATTERN = re.compile(r"95%\s*CI|置信区间|可信区间|confidence interval", re.I)
SIGNIFICANT_CLAIM = re.compile(r"显著(?:性)?(?:差异|提升|降低|高于|低于|优于)|significantly|statistical significance", re.I)


def check_stats(markdown: str) -> dict:
    """统计报告红线检查（源自 statistical-analysis.md 知识的代码化）：

    1. 每个 p 值附近应有检验方法名（±200 字符窗口）；
    2. p 值必须在 [0,1]；p=0.000 提示改写为 p<0.001；
    3. 全文出现显著性结论时，应能找到效应量与置信区间报告（全局级）。
    """
    if not markdown or not markdown.strip():
        return {"ok": True, "issues": [], "summary": {}}
    body, _refs = _split_body_references(markdown)
    body = _blank_fences(body)  # 代码块中的 p 值（示例代码/注释）不是统计报告
    issues = []
    p_hits = list(P_VALUE_PATTERN.finditer(body))
    starts = _line_starts(body)
    missing_test = 0
    out_of_range = 0
    zero_p = 0
    for m in p_hits:
        line_no = _pos_to_line(m.start(), starts)
        value = float(m.group(1))
        tail = body[m.end() : m.end() + 4]
        if value == 10 and tail.lstrip().startswith(("^", "{")):
            continue  # p<10^{-7} 等科学计数写法，合法的小 p 值（必须在越界判定之前豁免）
        if value < 0 or value > 1:
            out_of_range += 1
            issues.append({"type": "p_out_of_range", "severity": "error", "line": line_no, "detail": f"p 值越界: {m.group(0).strip()}（p 必须在 [0,1]）"})
            continue
        if value == 0.0:
            zero_p += 1
            issues.append({"type": "p_zero", "severity": "warning", "line": line_no, "detail": f"'{m.group(0).strip()}' 应写作 p<0.001（p 不可能为 0）"})
        window = body[max(0, m.start() - 200) : m.end() + 200]
        if not STAT_TEST_PATTERN.search(window):
            missing_test += 1
            issues.append({"type": "p_without_test", "severity": "warning", "line": line_no, "detail": f"'{m.group(0).strip()}' 附近未识别检验方法名（t 检验/ANOVA/卡方/回归…），统计三要素缺检验名称"})
    significant = bool(SIGNIFICANT_CLAIM.search(body))
    has_effect = bool(EFFECT_SIZE_PATTERN.search(body))
    has_ci = bool(CI_PATTERN.search(body))
    # 不可能值：相关系数越界（|r|>1）与异常巨大效应量（d>5）——编造数据的常见形态
    for m in re.finditer(r"\br\s*[=＝]\s*(-?\d+(?:\.\d+)?)\b", body):
        v = float(m.group(1))
        if v > 1 or v < -1:
            issues.append({"type": "r_out_of_range", "severity": "error", "line": _pos_to_line(m.start(), starts), "detail": f"相关系数越界: r={v}（相关系数必须在 [-1,1]）"})
    for m in re.finditer(r"\b[Cc]ohen'?s?\s*[dD]\s*[=＝]\s*(\d+(?:\.\d+)?)\b", body):
        v = float(m.group(1))
        if v > 5:
            issues.append({"type": "implausible_effect_size", "severity": "warning", "line": _pos_to_line(m.start(), starts), "detail": f"Cohen's d={v} 大得不寻常（行为科学常见 |d|<2），请核对原始数据"})
    if significant and not has_effect:
        issues.append({"type": "missing_effect_size", "severity": "warning", "detail": "全文有显著性结论但未见效应量（Cohen d / η² / r / OR…）——仅有 p 值不足以支撑'显著'的实践意义"})
    if significant and not has_ci:
        issues.append({"type": "missing_ci", "severity": "info", "detail": "全文有显著性结论但未见置信区间报告，建议补充 95% CI"})
    summary = {
        "pValues": len(p_hits),
        "pMissingTestName": missing_test,
        "pOutOfRange": out_of_range,
        "pZero": zero_p,
        "significantClaims": int(significant),
        "effectSizeReported": int(has_effect),
        "ciReported": int(has_ci),
    }
    return {"ok": not issues, "issues": issues, "summary": summary}


def audit_paper(markdown: str, genre: str = "empirical", journal: str = "", allow_common_acronyms: bool = True, fmt: str = "markdown", source_format: str = "markdown", brief: bool = False) -> str:
    """一键全量审计：运行全部校对器 + AI 痕迹画像 + 防篡改痕迹 + 章节完整性 + 统计诚信，
    可选词数预算对照。输出带启发式总分的结构化审计报告。

    扣分制：error -6 / warning -2（INFO 为建议级不扣分），AI 相似度高中档再扣。
    总分仅代表待人工复核密度，不是论文质量判决。
    brief=True（仅 fmt=json）：智能体上下文经济模式——只返回 ERROR 项与计数，
    完整报告细节省略，适合迭代循环中反复调用。
    """
    if not markdown or not markdown.strip():
        return "输入为空：未提供论文文本。"

    # 复用 proofread 的全部检查
    proof_json = json.loads(proofread(markdown, allow_common_acronyms, fmt="json", source_format=source_format, genre=genre))
    is_empirical = (genre or "empirical").lower() == "empirical"
    stats = check_stats(markdown) if is_empirical else {"ok": True, "issues": [], "summary": {"note": f"体裁 [{genre}] 非实证类，统计红线已跳过"}}
    signature = check_ai_signature(markdown)
    sections_check = check_sections(markdown, genre)
    budget = word_budget(markdown, journal) if journal else None

    # proofread 的 JSON 结果在 empirical 体裁下已含"统计诚信"一节，
    # 此处去重后统一以全量文本重算的 stats 为准——否则该节会重复渲染，
    # 且 ERROR/WARNING/INFO 总数被双倍计入
    all_sections = [s for s in proof_json["sections"] if s.get("name") != "统计诚信"]
    all_sections.append({"name": "统计诚信", "ok": stats["ok"], "issues": stats["issues"]})
    ai_band_severity = "warning" if signature.get("band") in ("中", "高") else "info"
    ai_section = {
        "name": "AI 痕迹画像",
        "ok": ai_band_severity == "info",
        "issues": (
            [{"type": "ai_band", "severity": ai_band_severity, "detail": f"AI 相似度 {signature.get('score', '?')}/100 ({signature.get('band')} 档)"}]
            if "score" in signature
            else [{"type": "ai_too_short", "severity": "info", "detail": signature.get("note", "")}]
        ),
    }
    all_sections.append(ai_section)
    tamper = check_tamper_traces(markdown)
    all_sections.append({"name": "防篡改痕迹", "ok": tamper["ok"], "issues": tamper["issues"]})
    sec_issues = sections_check.get("issues", [])
    if sec_issues:
        all_sections.append({"name": "章节完整性", "ok": False, "issues": sec_issues})

    total_error = sum(1 for s in all_sections for i in s["issues"] if i["severity"] == "error")
    total_warn = sum(1 for s in all_sections for i in s["issues"] if i["severity"] == "warning")
    total_info = sum(1 for s in all_sections for i in s["issues"] if i["severity"] == "info")

    # INFO 为建议级提示（绝对化用词、模板短语等），不计入扣分；
    # 否则长文会因提示堆积被系统性压分
    score = 100 - total_error * 6 - total_warn * 2
    band = signature.get("band")
    if band == "高":
        score -= 10
    elif band == "中":
        score -= 5
    score = max(0, min(100, round(score)))

    result = {
        "score": score,
        "scoreNote": "启发式审计分：反映待复核问题密度，非论文质量判决",
        "summary": {"errors": total_error, "warnings": total_warn, "infos": total_info},
        "statsSummary": stats["summary"],
        "aiSignature": {"score": signature.get("score"), "band": band, "metrics": signature.get("metrics")},
        "sectionsCompleteness": {"genre": genre, "missing": [i["detail"] for i in sec_issues if i["type"] == "missing_sections"]},
        "budget": budget,
        "sections": all_sections,
    }

    if (fmt or "markdown").lower() == "json":
        if brief:
            # 智能体上下文经济模式：只回 blocking（ERROR 项）+ 计数，省 token
            blocking = [
                {"section": s.get("name"), "type": it.get("type"), "detail": it.get("detail")}
                for s in all_sections
                for it in s.get("issues", [])
                if it.get("severity") == "error"
            ]
            compact = {
                "score": result["score"],
                "pass": total_error == 0,
                "errors": total_error,
                "warnings": total_warn,
                "infos": total_info,
                "aiBand": band,
                "blocking": blocking[:10],
                "note": "brief 模式：仅 ERROR 项与计数；完整报告请用 brief=false。",
            }
            return json.dumps(compact, ensure_ascii=False, indent=2)
        return json.dumps(result, ensure_ascii=False, indent=2)

    headline = f"ERROR {total_error} · WARNING {total_warn} · INFO {total_info}　|　AI 相似度 {signature.get('score', '—')}/100（{band or '—'} 档）　|　体裁 [{genre}]"
    lines = [
        "# 论文全量审计报告（audit_paper）",
        "",
        f"## 审计总分：**{score} / 100**",
        "",
        headline,
        "",
        "> 总分为规则启发式扣分制，反映待人工复核的问题密度；不构成论文质量判决。",
        "",
    ]
    if result["sectionsCompleteness"]["missing"]:
        lines.append(f"- 章节完整性提示：{result['sectionsCompleteness']['missing'][0]}")
        lines.append("")
    if budget:
        lines.append(f"## 词数预算对照（{budget['label']}，目标 {budget['total']}）")
        lines.append("")
        lines.append("| 章节 | 实际 | 目标 |")
        lines.append("|------|------|------|")
        for row in budget["rows"]:
            actual = row["actual"] if row["actual"] is not None else "—"
            lines.append(f"| {row['section']} | {actual} | {row['target']} |")
        lines.append("")
    for s in all_sections:
        status = "通过" if s["ok"] else f"{len(s['issues'])} 项"
        lines.append(f"## {s['name']}：{status}")
        seen = set()
        for issue in s["issues"]:
            key = (issue.get("type"), issue.get("detail"))
            if key in seen:
                continue
            seen.add(key)
            loc = f"L{issue['line']} " if issue.get("line") is not None else ""
            lines.append(f"- [{issue['severity'].upper()}] {loc}{issue['detail']}")
        if not s["issues"]:
            lines.append("- （无问题）")
        lines.append("")
    return "\n".join(lines)


def _natural_file_key(p: Path) -> list:
    """按文件名自然排序：'02-method.md' 排在 '10-appendix.md' 前。"""
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", p.name)]


def audit_project(project_dir: str, genre: str = "thesis", journal: str = "", fmt: str = "markdown", max_files: int = 30, allow_common_acronyms: bool = True) -> str:
    """多文件工程审计（学位论文/书章场景）：按文件名自然序合并章节后跑全量检查。

    跨章节问题只有合并全文才能暴露：第 1 章定义的缩写第 5 章未定义先用、
    章节间整句自我重复、术语写法漂移（GPT-4 vs GPT4）。输出分章字数表 + 合并审计报告。
    """
    d = Path(project_dir) if project_dir else None
    if d is None or not d.is_dir():
        return json.dumps({"ok": False, "note": f"目录不存在: {project_dir}"}, ensure_ascii=False)
    files = sorted((f for f in d.iterdir() if f.is_file() and f.suffix.lower() in {".md", ".markdown", ".txt"}), key=_natural_file_key)[:max_files]
    if not files:
        return json.dumps({"ok": False, "note": "目录下没有 .md/.txt 章节文件"}, ensure_ascii=False)
    parts = []
    file_rows = []
    ref_entries = []
    had_ref_section = False
    for f in files:
        try:
            text = f.read_text(encoding="utf-8-sig")  # -sig 兼容 Windows BOM 文件
        except (OSError, ValueError) as e:
            file_rows.append({"file": f.name, "error": str(e)})
            continue
        cjk = _count_cjk(text)
        en = _count_words_en(text)
        file_rows.append({"file": f.name, "cjkChars": cjk, "enWords": en})
        # 章节各自携带的参考文献段剥离收集——否则合并后第一个'参考文献'标题
        # 会把后续所有章节误判为文献段而跳过正文检查
        body_part, refs_part = _split_body_references(text)
        if refs_part.strip():
            had_ref_section = True
            ref_entries.extend(_extract_reference_entries(refs_part))
        parts.append(f"<!-- ScholarSeed:file:{f.name} -->\n\n{body_part}")
    merged = "\n\n".join(parts)
    if had_ref_section:
        merged += "\n\n## 参考文献\n\n" + ("\n".join(ref_entries) if ref_entries else "（各章节未提供条目）")

    proof_json = json.loads(proofread(merged, allow_common_acronyms, fmt="json", genre=genre))
    signature = check_ai_signature(merged)
    budget = word_budget(merged, journal) if journal else None
    total_cjk = sum(r.get("cjkChars", 0) for r in file_rows)
    total_en = sum(r.get("enWords", 0) for r in file_rows)

    result = {
        "ok": True,
        "files": file_rows,
        "totals": {"files": len(file_rows), "cjkChars": total_cjk, "enWords": total_en},
        "aiSignature": {"score": signature.get("score"), "band": signature.get("band")},
        "proofreadSummary": proof_json["summary"],
        "sections": proof_json["sections"],
        "referencesFormat": proof_json["referencesFormat"],
        "note": "跨章节缩写/重复/引用核对基于合并全文——单章通过不代表工程级一致",
    }
    if budget and budget.get("ok"):
        result["budget"] = budget

    if (fmt or "markdown").lower() == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    lines = [
        "# 多文件工程审计报告（audit_project）",
        "",
        f"目录 `{project_dir}` · {len(file_rows)} 个章节文件 · 合计中文 {total_cjk} 字 / 英文 {total_en} 词",
        "",
        "## 分章字数",
        "",
        "| # | 文件 | 中文字 | 英文词 |",
        "|---|------|--------|--------|",
    ]
    for i, r in enumerate(file_rows, 1):
        if "error" in r:
            lines.append(f"| {i} | {r['file']} | 读取失败 | {r['error'][:30]} |")
        else:
            lines.append(f"| {i} | {r['file']} | {r['cjkChars']} | {r['enWords']} |")
    band = signature.get("band") or "—"
    score = signature.get("score", "?")
    s = proof_json["summary"]
    if score == "?":
        ai_line = f"**AI 痕迹**: 未评估（{signature.get('note', '样本过短')}）"
    else:
        ai_line = f"**AI 痕迹**: {score}/100（{band} 档）"
    lines += [
        "",
        f"{ai_line} · **合并审计**: ERROR {s['errors']} / WARNING {s['warnings']} / INFO {s['infos']}",
        "",
        "> 缩写一致、跨章重复、正文引用核对均为合并全文结果；逐项修复前请人工复核。",
        "",
    ]
    for sec in result["sections"]:
        status = "通过" if sec["ok"] else f"{len(sec['issues'])} 项"
        lines.append(f"## {sec['name']}：{status}")
        seen = set()
        for issue in sec["issues"]:
            key = (issue.get("type"), issue.get("detail"))
            if key in seen:
                continue
            seen.add(key)
            loc = f"L{issue['line']} " if issue.get("line") else ""
            lines.append(f"- [{issue['severity'].upper()}] {loc}{issue['detail']}")
        if not sec["issues"]:
            lines.append("- （无问题）")
        lines.append("")
    return "\n".join(lines)


def proofread(markdown: str, allow_common_acronyms: bool = True, fmt: str = "markdown", source_format: str = "markdown", genre: str = "empirical") -> str:
    """组合校对报告：结构 + 文风 + 标点 + 图表 + 术语 + 重复 + 文献格式 + 正文引用核对，一次输出。

    文风/标点/术语/重复只查正文——参考文献条目的半角点号等属格式特征，不作为正文标点问题。
    所有检查均为规则启发式，结论是"提示"而非"判决"；最终判断由作者/Agent 复核。
    fmt="json" 时返回结构化 JSON（供 Agent 程序化消费）。
    """
    if not markdown or not markdown.strip():
        return "输入为空：未提供论文文本。"
    raw_source = markdown
    markdown = _maybe_latex(markdown, source_format)
    body, _refs_section = _split_body_references(markdown)
    structure = check_structure(markdown)
    style = check_style(body)
    punct = check_punctuation(body)
    figures = check_figures_tables(markdown)
    terms = check_terms(body, allow_common_acronyms)
    dupes = check_duplicates(body)
    refs_fmt = check_references_format(markdown)
    if (source_format or "markdown").lower() == "latex":
        intext = _check_cite_keys(raw_source)
    else:
        intext = check_intext_citations(markdown)
    if (genre or "empirical").lower() == "empirical":
        stats = check_stats(body)
    else:
        stats = None
    numbers = check_numbers(body)
    hedging = check_hedging(markdown)

    sections = [
        ("标题结构", structure),
        ("文风", style),
        ("标点规范", punct),
        ("图表完整", figures),
        ("术语一致", terms),
        ("重复内容", dupes),
        ("正文引用核对", intext),
        ("数字一致性", numbers),
        ("断言强度对冲", hedging),
    ]
    if stats is not None:
        sections.append(("统计诚信", stats))
    total_error = sum(1 for _, r in sections for i in r["issues"] if i["severity"] == "error")
    total_warn = sum(1 for _, r in sections for i in r["issues"] if i["severity"] == "warning")
    total_info = sum(1 for _, r in sections for i in r["issues"] if i["severity"] == "info")
    refs_issues = refs_fmt["issues"]
    total_error += sum(1 for i in refs_issues if i["severity"] == "error")
    total_warn += sum(1 for i in refs_issues if i["severity"] == "warning")

    if (fmt or "markdown").lower() == "json":
        return json.dumps(
            {
                "summary": {"errors": total_error, "warnings": total_warn, "infos": total_info, "referenceEntries": refs_fmt.get("entries", 0)},
                "sections": [{"name": name, "ok": r.get("ok"), "issues": r.get("issues", [])} for name, r in sections],
                "referencesFormat": {"issues": refs_issues, "styles": refs_fmt.get("styles", {})},
            },
            ensure_ascii=False,
            indent=2,
        )

    total_line = (
        f"**总计：ERROR {total_error} / WARNING {total_warn} / INFO {total_info}**"
        f"　文献条目 {refs_fmt.get('entries', 0)} 条"
        f"（{', '.join(k + '×' + str(v) for k, v in refs_fmt.get('styles', {}).items()) or '无'}）"
    )
    lines = [
        "# 全文校对报告（proofread）",
        "",
        total_line,
        "",
        "> 本报告为规则启发式检查，结论是提示而非判决；每项修复前请人工复核。",
        "",
    ]
    for title, result in sections:
        lines.append(f"## {title}：{'通过' if result['ok'] else str(len(result['issues'])) + ' 项'}")
        for issue in result["issues"]:
            loc = f"L{issue['line']} " if issue.get("line") else ""
            sev = issue["severity"].upper()
            lines.append(f"- [{sev}] {loc}{issue['detail']}")
        if not result["issues"]:
            lines.append("- （无问题）")
        lines.append("")
    lines.append(f"## 参考文献格式：{'通过' if not refs_issues else str(len(refs_issues)) + ' 项'}")
    for issue in refs_issues:
        sev = issue["severity"].upper()
        lines.append(f"- [{sev}] {issue['detail']}")
    if not refs_issues:
        lines.append("- （无问题）")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 智能体动力原语（agent-native dynamics）：让智能体可以 计划→组合门禁→验证增量
# 地迭代修复，而不是逐个调用被动问答式工具。全部离线确定性、零依赖不变。
# ---------------------------------------------------------------------------

# 离线确定性门禁注册表：gate 名 -> (检查器, 说明)。核验类（citation_verify 等）
# 需要真实网络，不进默认套件——智能体可用 verify_references 单独作硬门禁。
_GATE_REGISTRY = [
    ("structure", "标题层级连续性", lambda md, genre: check_structure(md)),
    ("style", "文风（AI 腔/口语化/超长）", lambda md, genre: check_style(md)),
    ("punctuation", "中英标点混用", lambda md, genre: check_punctuation(md)),
    ("figures", "图表编号与题注", lambda md, genre: check_figures_tables(md)),
    ("terms", "缩写定义与术语变体", lambda md, genre: check_terms(md)),
    ("duplicates", "整句重复", lambda md, genre: check_duplicates(md)),
    ("intext", "正文引用↔文献表双向核对", lambda md, genre: check_intext_citations(md)),
    ("references_format", "参考文献格式（重复/未来年份/混用）", lambda md, genre: check_references_format(md)),
    ("references_completeness", "文献完整性（年份/来源/卷期页/类型标识/DOI 语法）", lambda md, genre: check_references_completeness(md)),
    ("references_recency", "文献时效性（陈旧综述信号）", lambda md, genre: check_references_recency(md)),
    ("placeholders", "占位符/未完成痕迹", lambda md, genre: check_placeholders(md)),
    ("encoding", "文件底座：编码损坏/乱码/CID 残留", lambda md, genre: check_encoding(md)),
    ("ethics", "P 前提：伦理/利益冲突/AI 披露/数据声明", lambda md, genre: check_ethics_statements(md, genre)),
    ("links", "链接可信（离线语法与虚假特征）", lambda md, genre: check_links(md)),
    ("vague_attribution", "模糊归因（无引注的'研究表明/专家认为'）", lambda md, genre: check_vague_attribution(md)),
    ("numbers", "数字一致性（口径/加和/百分比）", lambda md, genre: check_numbers(md)),
    ("stats", "统计红线（p值/效应量/CI）", lambda md, genre: check_stats(md)),
    ("hedging", "断言对冲", lambda md, genre: check_hedging(md)),
    ("sections", "体裁必备章节", lambda md, genre: check_sections(md, genre)),
    ("abstract", "摘要四要素", lambda md, genre: check_abstract(md, genre)),
    ("title", "标题质量", lambda md, genre: check_title(md)),
]


def _run_gate_bundle(markdown: str, gates: str, genre: str, allow_common_acronyms: bool) -> list:
    """按注册表跑一组门禁，返回 [{gate, label, errors, warnings, infos, issues}]。

    check_terms 是唯一带 allow_common_acronyms 语义的检查器，此处透传。
    """
    wanted = [g.strip() for g in gates.split(",") if g.strip()] if gates else []
    results = []
    for name, label, fn in _GATE_REGISTRY:
        if wanted and name not in wanted:
            continue
        try:
            if name == "terms":
                res = check_terms(markdown, allow_common=allow_common_acronyms)
            else:
                res = fn(markdown, genre)
        except Exception as e:  # 单门禁异常不拖垮套件：如实标注 skipped
            results.append({"gate": name, "label": label, "errors": 0, "warnings": 0, "infos": 0,
                            "skipped": True, "note": f"门禁异常跳过: {e}", "issues": []})
            continue
        issues = res.get("issues", []) if isinstance(res, dict) else []
        counts = {"error": 0, "warning": 0, "info": 0}
        for it in issues:
            counts[it.get("severity", "info")] = counts.get(it.get("severity", "info"), 0) + 1
        results.append({
            "gate": name, "label": label,
            "errors": counts["error"], "warnings": counts["warning"], "infos": counts["info"],
            "issues": issues[:8],
        })
    return results


def gate_suite(markdown: str, gates: str = "", genre: str = "empirical", allow_common_acronyms: bool = True) -> str:
    """组合门禁套件：一次运行选定的离线确定性检查器，输出统一 JSON 判定。

    为智能体迭代修复设计：返回 {"pass", "blocking", "gates":[...]}——智能体读取
    verdict 后自动修复再重跑，直到 pass=true。默认跑全部 18 道门禁；
    gates 参数传逗号分隔子集（如 "style,numbers,stats"）。统计门禁仅实证体裁生效。
    通过判定与 proofread 纪律一致：ERROR 计数为 0。
    """
    if not markdown or not markdown.strip():
        return json.dumps({"pass": True, "note": "输入为空"}, ensure_ascii=False)
    results = _run_gate_bundle(markdown, gates, genre, allow_common_acronyms)
    blocking = []
    total_errors = 0
    for g in results:
        total_errors += g["errors"]
        for it in g["issues"]:
            if it.get("severity") == "error":
                blocking.append({"gate": g["gate"], "type": it.get("type"), "detail": it.get("detail")})
    verdict = {
        "pass": total_errors == 0,
        "totalErrors": total_errors,
        "totalWarnings": sum(g["warnings"] for g in results),
        "totalInfos": sum(g["infos"] for g in results),
        "blocking": blocking[:10],
        "gates": results,
        "note": "pass 判定 = ERROR 计数为 0（与 proofread 纪律一致）；warning/info 是提示不拦门禁。核验类检查（引用真实性）请单独用 verify_references。",
    }
    return json.dumps(verdict, ensure_ascii=False, indent=2)


def audit_delta(before: str, after: str, genre: str = "empirical", allow_common_acronyms: bool = True) -> str:
    """修复增量对比：对修改前后两版稿件跑同一门禁束，报告 哪些问题已修复/新引入/仍存在。

    智能体迭代修复的核心回路原语——改完一稿后一次调用即可知道这轮改动
    是净改善还是引入了新问题。行号会随编辑漂移，故签名用 (类型, 去行号详情)。
    """
    if not before or not before.strip() or not after or not after.strip():
        return json.dumps({"ok": False, "note": "请提供 before 与 after 两版文本"}, ensure_ascii=False)

    def _signature_set(text: str) -> set:
        sig = set()
        for g in _run_gate_bundle(text, "", genre, allow_common_acronyms):
            for it in g["issues"]:
                detail = re.sub(r"L\d+[:：，,]?\s*", "", str(it.get("detail", "")))
                sig.add((g["gate"], it.get("type"), detail))
        return sig

    before_sig = _signature_set(before)
    after_sig = _signature_set(after)
    fixed = sorted(before_sig - after_sig)
    introduced = sorted(after_sig - before_sig)
    persisted = sorted(before_sig & after_sig)

    def _err_count(text: str) -> int:
        return sum(g["errors"] for g in _run_gate_bundle(text, "", genre, allow_common_acronyms))

    errors_before, errors_after = _err_count(before), _err_count(after)
    return json.dumps({
        "fixed": [{"gate": g, "type": t, "detail": d[:80]} for g, t, d in fixed[:15]],
        "introduced": [{"gate": g, "type": t, "detail": d[:80]} for g, t, d in introduced[:15]],
        "persistedCount": len(persisted),
        "fixedCount": len(fixed),
        "introducedCount": len(introduced),
        "errorsBefore": errors_before,
        "errorsAfter": errors_after,
        "verdict": "净改善" if len(fixed) > len(introduced) and errors_after <= errors_before else ("持平" if len(fixed) == len(introduced) else "净退步——新引入问题多于修复"),
        "note": "签名=(门禁,类型,去行号详情)；行号随编辑漂移属正常。建议循环：修改→audit_delta→verdict 为'净改善'且 errorsAfter=0 时停止。",
    }, ensure_ascii=False, indent=2)


_AGENT_PLAN = {
    "submission": [
        {"stage": "定目标", "tool": "journal_matcher", "params": "按主题关键词取候选，人工锁定唯一优先目标", "pass": "目标期刊已锁定"},
        {"stage": "定篇幅", "tool": "render_template", "params": "genre=论文体裁, journal=目标期刊档", "pass": "分章词数基准已写入稿头"},
        {"stage": "文献", "tool": "verify_references", "params": "全文", "pass": "C 级清零（X 级联网重跑）"},
        {"stage": "初检", "tool": "gate_suite", "params": "genre=论文体裁", "pass": "pass=true（ERROR=0）"},
        {"stage": "统计", "tool": "check_stats", "params": "全文（实证体裁）", "pass": "无 p_zero/p_out_of_range"},
        {"stage": "精修", "tool": "check_style + check_ai_signature", "params": "全文，逐处重写模板腔", "pass": "warning 级 AI 高频词清零"},
        {"stage": "摘要标题", "tool": "check_abstract + check_title", "params": "全文", "pass": "四要素齐全且标题无空泛词"},
        {"stage": "终审", "tool": "audit_paper", "params": "genre=论文体裁, brief=true", "pass": "errors=0"},
    ],
    "thesis": [
        {"stage": "合并", "tool": "audit_project", "params": "project_dir=分章目录", "pass": "跨章缩写/重复/引用问题清零"},
        {"stage": "文献", "tool": "verify_references", "params": "合并全文 --fail-on C", "pass": "C 级清零"},
        {"stage": "自查重", "tool": "check_self_plagiarism", "params": "corpus_dir=历史稿目录", "pass": "命中项已人工裁决"},
        {"stage": "终审", "tool": "audit_paper", "params": "genre=thesis", "pass": "errors=0"},
    ],
    "polish": [
        {"stage": "定位", "tool": "check_style", "params": "全文", "pass": "已逐处过目"},
        {"stage": "画像", "tool": "check_ai_signature", "params": "全文", "pass": "模板腔段落已重写"},
        {"stage": "残留", "tool": "check_tamper_traces", "params": "全文", "pass": "无零宽/同形字/异常空白"},
        {"stage": "增量", "tool": "audit_delta", "params": "before=修改前, after=修改后", "pass": "verdict=净改善"},
    ],
}


def next_actions(goal: str = "submission", genre: str = "empirical") -> str:
    """返回面向智能体的有序行动计划（JSON）：每步含 工具/参数模板/通过条件。

    把技能层的工作流知识编译成机器可执行的计划——智能体不必通读技能文档，
    按计划逐步调用工具、逐步校验通过条件，即可完成一条完整的论文交付流水线。
    goal: submission(期刊投稿) | thesis(学位论文) | polish(润色自检)。
    """
    g = (goal or "submission").strip().lower()
    if g not in _AGENT_PLAN:
        return json.dumps({"ok": False, "note": f"未知 goal: {g}，可选 submission | thesis | polish"}, ensure_ascii=False)
    steps = []
    for i, s in enumerate(_AGENT_PLAN[g], 1):
        steps.append({"order": i, **s})
    return json.dumps({
        "goal": g,
        "genre": genre,
        "steps": steps,
        "loop_rule": "任何一步未过通过条件：修复后重跑该步工具；涉及全文修改时用 audit_delta 验证净改善。",
        "evidence_chain": "每步的机器输出（报告原文）随稿留档，作为交付证据链；禁止口头声称已通过。",
    }, ensure_ascii=False, indent=2)


TOOLS = [
    {
        "name": "render_template",
        "description": "按体裁生成文章 Markdown 模板，可指定目标期刊类型附加篇幅规划。体裁: survey(综述)/empirical(实证)/tech(技术)/thesis(学位论文)/argumentative(人文论证)，缺省 survey；期刊类型: top_conceptual(顶刊概念)/top_empirical(顶刊实证)/general(一般)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis | argumentative", "default": "survey"},
                "journal": {"type": "string", "description": "top_conceptual | top_empirical | general（可选，指定则附加目标篇幅规划）", "default": ""},
            },
            "required": [],
        },
    },
    {
        "name": "word_count",
        "description": "统计 Markdown 正文去除标记后的中文字符数与词数。口径约定：统计的是传入全文；论文成稿校验时先截取到 ## References / ## 参考文献 之前再统计，报告词数一律标注'不含参考文献'。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "source_format": {"type": "string", "description": "markdown | latex，默认 markdown", "default": "markdown"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_structure",
        "description": "校验标题层级是否连续（不跳级）。支持 markdown / latex 两种源格式。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "source_format": {"type": "string", "description": "markdown | latex，默认 markdown", "default": "markdown"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "generate_outline",
        "description": "基于研究问题与体裁生成结构化论文大纲。体裁: survey(综述)/empirical(实证)/tech(技术)/thesis(学位论文)/argumentative(人文论证)，默认 empirical。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "研究主题或研究问题"},
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis | argumentative", "default": "empirical"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "literature_checklist",
        "description": "从论文文本的参考文献段生成逐条核验清单（A/B/C 分级、DOI 状态占位与引用铁律提醒），防止未核实文献混入投稿。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string", "description": "含 References/参考文献 段的论文全文"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "submission_checklist",
        "description": "生成投稿前检查清单：目标期刊五维匹配、ICMJE 署名、Cover Letter、伦理与 AI 披露、文献 DOI 最终核验、投稿系统执行步骤。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "journal": {"type": "string", "description": "目标期刊名（可选）", "default": ""},
                "topic": {"type": "string", "description": "论文主题（可选）", "default": ""},
            },
            "required": [],
        },
    },
    {
        "name": "journal_matcher",
        "description": "按论文主题关键词与类型（conceptual/empirical/review）推荐候选投稿期刊，输出匹配度评分、主题命中、篇幅参考与投稿提示。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "论文主题或关键词，如 'algorithmic recruitment and talent management'"},
                "paper_type": {"type": "string", "description": "conceptual | empirical | review", "default": "conceptual"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "citation_verify",
        "description": "通过 Crossref API 核验文献真实性：优先按 DOI 精确核验，无 DOI 时按标题检索（归一化标题相似度阈值防误配，取最相似候选）。提供 authors/year 时执行字段级交叉验证。返回存在性判定 + 元数据 + fieldChecks + A/B/C 分级（A=存在且期望字段全匹配，B=存在但字段不匹配，C=未确认；与 literature_checklist 口径一致）。用于杜绝参考文献幻觉——写进论文的每条文献都必须先核验。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doi": {"type": "string", "description": "DOI 如 10.1038/nature12373（与 title 至少提供一项）", "default": ""},
                "title": {"type": "string", "description": "文献标题（无 DOI 时按标题检索）", "default": ""},
                "authors": {"type": "string", "description": "期望作者（可选，逗号分隔姓氏，如 'Barney' 或 'Fickler, Raithel'），提供则交叉验证", "default": ""},
                "year": {"type": "integer", "description": "期望年份（可选，如 2013），提供则交叉验证", "default": 0},
            },
            "required": [],
        },
    },
    {
        "name": "lit_search",
        "description": "通过 Semantic Scholar API 真实检索学术文献，返回标题/作者/年份/摘要/被引数/DOI/链接。用于文献调研阶段真实搜库而非凭知识编造文献。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索式，如 'algorithmic recruitment fairness'"},
                "limit": {"type": "integer", "description": "返回结果数 1-20，默认 5", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "journal_search_openalex",
        "description": "通过 OpenAlex API 按主题实时检索学术期刊（任意学科），返回期刊名/出版方/发文量/被引/h 指数/ISSN/OA 状态。弥补内置期刊库领域覆盖不足——内置库匹配不到时用本工具真实搜库。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "主题关键词，如 'machine learning medical imaging'"},
                "limit": {"type": "integer", "description": "返回结果数 1-10，默认 5", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_references",
        "description": "批量核验论文参考文献段中每条文献的真实性：逐条按 DOI 精确核验（无 DOI 按标题检索），输出 Markdown 汇总报告与 A/B/C 统计。成稿交付/投稿前的强制门禁——C 级条目必须补来源。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string", "description": "含 References/参考文献 段的论文全文或文献表"},
                "max_entries": {"type": "integer", "description": "单次核验条数上限，默认 30", "default": 30},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_style",
        "description": "文风检查（规则启发式）：AI 高频词、口语化表达、凑字数短语、过度声明词、超长段落与超长句。返回逐项问题列表（含行号）。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_punctuation",
        "description": "标点规范检查：CJK 语境半角标点、英文间全角句号等中英文混用问题（忽略代码块与行内代码）。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_figures_tables",
        "description": "图表完整性检查：编号连续性、caption 与正文引用双向对应（有图未引用/引用了不存在的图）。忽略代码块。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_terms",
        "description": "术语一致性检查：缩写未定义先用、定义了未使用、同词异写变体（如 GPT-4 vs GPT4）。通用缩写（AI/API 等）默认豁免，可用 allow_common=false 关闭豁免。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "allow_common": {"type": "boolean", "description": "是否豁免通用缩写，默认 true", "default": True},
                "source_format": {"type": "string", "description": "markdown | latex，默认 markdown", "default": "markdown"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_duplicates",
        "description": "重复内容检测：规范化后完全相同的句子多次出现（自查复用/复读机式生成）。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_references_format",
        "description": "参考文献格式检查：重复条目、未来年份（幻觉信号）、APA/GB-T/IEEE 多风格混用。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_intext_citations",
        "description": "正文引用与文献表双向核对：数字式 [1]/[2,5]/[3-7] 与文献表编号比对（幽灵引用/未引用条目/编号重复），作者-年份式 (Smith, 2020) 与条目首作者+年份比对，风格混用告警。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_sections",
        "description": "按体裁检查必备章节是否齐全（empirical/survey/tech/thesis 各有章节清单）+ 关键词行存在性与数量规范。缺章为提示而非硬性错误——非常规结构可忽略。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis | argumentative，默认 empirical", "default": "empirical"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "word_budget",
        "description": "分章词数对照目标期刊篇幅规划：按 H2 章节统计实际字数（CJK 字符 + 英文单词），与 render_template 同源的期刊篇幅目标逐项对照，超配额章节一目了然。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "journal": {"type": "string", "description": "top_conceptual | top_empirical | general"},
            },
            "required": ["markdown", "journal"],
        },
    },
    {
        "name": "check_ai_signature",
        "description": "AI 痕迹统计画像（启发式参考，非判决）：句长突发性 CV、词汇丰富度 TTR、模板短语密度、句首转折词占比、em-dash 密度、'不仅…更…'句式。输出 0-100 相似度分值区间 + 逐条证据。文本过短时拒绝评估。style=stem（默认）：按 STEM/定量文体全指标计分；style=humanities：人文阐释性文体模式，剥离分布项（句长 CV/TTR），只保留跨学科词汇证据——文科术语密集与均匀句长不扣分。两种模式分数均仅作语言层参考。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "min_sentences": {"type": "integer", "description": "最少句数门槛，默认 8", "default": 8},
                "style": {"type": "string", "description": "stem（默认）| humanities（人文阐释性文体）", "default": "stem"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_tamper_traces",
        "description": "防篡改痕迹取证（客观字符级证据，非 AI 判决）：检测降AI服务与规避检测攻击留下的痕迹——零宽/不可见字符(U+200B/200C/200D/2060/FEFF、软连字符)、西里尔/希腊同形字混入拉丁单词(RAID homoglyph 攻击特征，正常俄文/希腊文段落自动豁免)、行内异常空白串。检测的是'处理痕迹'而非'是否AI所写'，不误伤写作风格。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_numbers",
        "description": "全文数字一致性检查：同类样本口径矛盾（N/样本量/被试，发放-回收-有效等非互斥场景自动豁免）、单行百分比加和越界、占比数值>100%。数字前后矛盾是编造数据的典型信号。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_hedging",
        "description": "逐节断言强度对冲画像：统计各章绝对化表述（显然/必然/首次实现/proves that 等）与对冲措辞（可能/约/suggest 等）数量；绝对化密集且零对冲的章节告警。绝对化本身非错误，逐项确认证据后可保留。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "check_stats",
        "description": "统计报告红线：每个 p 值附近应有检验方法名（t 检验/ANOVA/卡方/回归…），p 值越界与 p=0.000 写法纠错，全文显著性结论需配套效应量与置信区间（全局级）。源自 statistical-analysis.md 红线的代码化。",
        "inputSchema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "audit_pdf",
        "description": "对 PDF 投稿做尽力级审计：纯标准库提取文本（FlateDecode/未压缩流的 Tj/TJ 算子），运行文风/重复/对冲/数字一致性与统计红线子集。不解析 CID/CJK 复杂编码；结构/标点/图表/引用核对在 PDF 上不可靠故跳过并如实标注。中文 PDF 提取可能不完整。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdf_path": {"type": "string", "description": "PDF 文件路径"},
                "genre": {"type": "string", "description": "empirical 时启用统计红线，默认 empirical", "default": "empirical"},
                "format": {"type": "string", "description": "markdown（默认）| json", "default": "markdown"},
                "min_chars": {"type": "integer", "description": "提取文本最短字符数（低于则拒绝审计），默认 200", "default": 200},
            },
            "required": ["pdf_path"],
        },
    },
    {
        "name": "check_self_plagiarism",
        "description": "跨文档自查重：当前稿与语料库目录中历史稿件(.md/.txt/.tex)的 n-gram 重叠率。适用学位论文章节复用、系列论文模板句复用等场景。合理复用也会命中——结果为提示，需人工判断是否改写或引用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "corpus_dir": {"type": "string", "description": "历史稿件目录（绝对路径）"},
                "min_gram": {"type": "integer", "description": "n-gram 长度，默认 8", "default": 8},
                "threshold": {"type": "number", "description": "重叠率告警阈值(0-1)，默认 0.05", "default": 0.05},
            },
            "required": ["markdown", "corpus_dir"],
        },
    },
    {
        "name": "audit_paper",
        "description": "一键全量审计：全部校对器 + AI 痕迹画像 + 防篡改痕迹取证 + 章节完整性 + 统计诚信 + 可选词数预算，输出带启发式总分(0-100)的审计报告。总分反映待人工复核问题密度，非论文质量判决。fmt=json 返回结构化结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis | argumentative，默认 empirical", "default": "empirical"},
                "journal": {"type": "string", "description": "可选 top_conceptual | top_empirical | general，提供则附词数预算对照", "default": ""},
                "allow_common_acronyms": {"type": "boolean", "default": True},
                "format": {"type": "string", "description": "markdown（默认）| json", "default": "markdown"},
                "source_format": {"type": "string", "description": "markdown | latex，默认 markdown", "default": "markdown"},
                "brief": {"type": "boolean", "description": "智能体经济模式：fmt=json 时只返回 ERROR 项与计数", "default": False},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "proofread",
        "description": "组合校对报告：一次运行结构+文风+标点+图表+术语+重复+文献格式+正文引用核对+数字一致性+断言强度对冲全部检查（empirical 体裁含统计诚信红线），输出带 ERROR/WARNING/INFO 分级的汇总报告。成稿交付前的全文质检入口。format=json 时返回结构化结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "allow_common_acronyms": {"type": "boolean", "description": "术语检查是否豁免通用缩写，默认 true", "default": True},
                "format": {"type": "string", "description": "markdown（默认）| json", "default": "markdown"},
                "source_format": {"type": "string", "description": "markdown | latex，默认 markdown；latex 时正文引用核对走键级比对", "default": "markdown"},
                "genre": {"type": "string", "description": "empirical 时启用统计诚信检查，默认 empirical", "default": "empirical"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "format_citation",
        "description": "按 DOI 或标题核验文献后生成规范引用条目：APA 7 / GB/T 7714-2015 / IEEE / MLA 9 / Chicago（书目格式）/ BibTeX。真实 Crossref 元数据（作者结构化姓名、卷期页码、DOI），杜绝手打引用格式错误与字段编造；未核验通过不产出条目。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doi": {"type": "string", "description": "DOI 如 10.1038/nature14539（与 title 至少一项）", "default": ""},
                "title": {"type": "string", "description": "文献标题（无 DOI 时按标题检索，相似度阈值防误配）", "default": ""},
                "style": {"type": "string", "description": "apa | gbt | ieee | bibtex | mla(MLA 9) | chicago(书目格式)，默认 apa", "default": "apa"},
                "authors": {"type": "string", "description": "期望作者（可选，提供则交叉验证）", "default": ""},
                "year": {"type": "integer", "description": "期望年份（可选，提供则交叉验证）", "default": 0},
            },
            "required": [],
        },
    },
    {
        "name": "check_abstract",
        "description": "摘要质量检查：定位摘要段（标题级或标签行），检查结构化四要素覆盖（目的/方法/结果/结论）、篇幅带（过短/过长）、实证体裁是否含量化数字——缺结果的摘要是高频拒稿点。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "genre": {"type": "string", "description": "empirical 时追加'须含量化数字'检查，默认 empirical", "default": "empirical"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_title",
        "description": "标题质量检查：长度带（中文>25 字/英文>20 词告警）、空泛措辞（浅析/试论/A Study of）、英文全大写或全小写规范、问句式与主副标题结构提示。可直接传 title 或从 markdown 首个 H1 提取。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string", "description": "论文全文（取首个 H1 作为标题）", "default": ""},
                "title": {"type": "string", "description": "直接传入标题（优先于 markdown）", "default": ""},
            },
            "required": [],
        },
    },
    {
        "name": "audit_project",
        "description": "多文件工程审计（学位论文/书章）：按文件名自然序合并目录下 .md/.txt 章节文件，输出分章字数表 + 合并全文的 proofread 全套检查（跨章节缩写一致、整句自我重复、正文引用核对只有合并后才能暴露）+ AI 痕迹画像 + 可选词数预算。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "章节文件目录（绝对路径），按文件名自然序合并如 01-intro.md, 02-method.md"},
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis，默认 thesis", "default": "thesis"},
                "journal": {"type": "string", "description": "可选 top_conceptual | top_empirical | general，提供则附词数预算对照", "default": ""},
                "format": {"type": "string", "description": "markdown（默认）| json", "default": "markdown"},
                "max_files": {"type": "integer", "description": "单次合并章节数上限，默认 30", "default": 30},
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "next_actions",
        "description": "智能体计划路由：按目标（submission/thesis/polish）返回有序 JSON 行动计划，每步含 工具/参数模板/通过条件，供智能体按步推进论文流水线并逐步校验。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "submission（期刊投稿）| thesis（学位论文）| polish（润色自检）", "default": "submission"},
                "genre": {"type": "string", "description": "论文体裁，透传给计划中的门禁步骤", "default": "empirical"},
            },
            "required": [],
        },
    },
    {
        "name": "gate_suite",
        "description": "组合门禁套件：一次调用运行全部（或选定）离线确定性检查器，输出统一 JSON 判定（pass = ERROR 计数为 0 + blocking 清单），供智能体 修复→重跑→直到通过 的自动迭代。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "gates": {"type": "string", "description": "逗号分隔子集: structure,style,punctuation,figures,terms,duplicates,intext,numbers,stats,hedging,sections,abstract,title；缺省全部", "default": ""},
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis | argumentative", "default": "empirical"},
                "allow_common_acronyms": {"type": "boolean", "description": "豁免常用缩写，默认 true", "default": True},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_references_completeness",
        "description": "逐条文献完整性检查：缺年份、缺来源、缺卷期页码、中文条目缺 GB/T 7714 类型标识（[J]/[M] 等）、DOI 语法异常（注册符长度/含空格/标点截断）。文献表不完整是编辑部第一道退回理由。",
        "inputSchema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
    {
        "name": "check_references_recency",
        "description": "文献时效性信号：可识别年份的文献达到 4 条以上时，统计中位文献年龄与过时占比，全部或七成以上早于 10 年即提示综述可能陈旧。",
        "inputSchema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
    {
        "name": "check_placeholders",
        "description": "占位符/未完成痕迹检查：TODO、FIXME、???、[citation needed]、待补充/待填写 等——投稿前必须清零，遗留占位符是低级但致命的印象伤害。",
        "inputSchema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
    {
        "name": "check_links",
        "description": "链接可信检查：离线检出占位域名（example.com/localhost）、非法 TLD（.example/.invalid）、无主机名链接；live=true 时逐个 HEAD 验活（404/410 死链，403/405 反爬按无法核验处理，最多验 20 条）。",
        "inputSchema": {"type": "object", "properties": {"markdown": {"type": "string"}, "live": {"type": "boolean", "description": "联网验活，默认仅离线检查", "default": False}}, "required": ["markdown"]},
    },
    {
        "name": "check_vague_attribution",
        "description": "模糊归因检查：句子向不具名的'研究表明/experts say/人们普遍认为'借权威却同句无任何引注（AI 文本'光润但空洞'的核心特征）。同句含 [1]/(Smith, 2020)/et al 即豁免；命中项需补引文或改为具体表述。",
        "inputSchema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
    {
        "name": "check_encoding",
        "description": "编码健康检查（文件底座层）：U+FFFD 替换符与 (cid:NN) PDF 提取残留（文本不可读，error 级）、UTF-8 被按 Latin-1 误读的乱码特征、异常控制字符、文中部 BOM。底座损坏时上层所有行号证据不可信——交付前必须清零。",
        "inputSchema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
    {
        "name": "check_ethics_statements",
        "description": "合法前提检查（门禁塔 P 层）：伦理审批/知情同意、利益冲突披露、AI 使用披露（AIGC 合规）、数据可用性声明的存在性。正文提及人类受试者而缺伦理声明为 error（桌拒红线），其余缺失为 warning。工具只查声明在场，真伪归作者与机构。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "genre": {"type": "string", "description": "survey | empirical | tech | thesis | argumentative，默认 empirical（empirical/thesis 要求伦理与数据声明）", "default": "empirical"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_retraction",
        "description": "撤稿筛查（联网，L1 存在层）：逐条查被引文献是否已被撤稿——Crossref update-to/relation.is-retracted-by 记录与撤稿声明标题特征，属外部 API 事实。引用撤稿成果为 error（诚信硬伤）；网络失败按 X 级纪律记 unverifiable（info），永不触发门禁。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string", "description": "含 References/参考文献 段的论文全文"},
                "max_entries": {"type": "integer", "description": "单次核查条数上限，默认 30", "default": 30},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_claim_citation_fit",
        "description": "引证契合检查（联网+缓存，L2 契合层）：对'带强主张措辞+引注'的句子，比对其词元与所引文献标题/摘要词元的重叠率，过低时提示人工复核。词汇契合度低≠引文错误（warning 级，需人工判断）；无法获取所引文献元数据时诚实降级不计入失败。语义级'源文是否真支持主张'不做（需模型推理）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
                "max_assessed": {"type": "integer", "description": "单次评估句数上限（API 礼貌），默认 15", "default": 15},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "check_version_mismatch",
        "description": "预印本-正式版错配检查（联网，L2 契合层）：文献条目含 arXiv 标识时，按标题在 Crossref 检索正式发表版（相似度阈值防误配）；命中且非预印本自身即提示更新引用。warning 级——预印本引用并非错误，但正式版已存在时应更新元数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string", "description": "含 References/参考文献 段的论文全文"},
                "max_entries": {"type": "integer", "description": "单次核查条数上限，默认 30", "default": 30},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "audit_delta",
        "description": "修复增量对比：对修改前后两版跑同一门禁束，输出 已修复/新引入/仍存在 的差集与净改善判定——智能体每轮修改后调用一次即可验证改动质量，避免按下葫芦浮起瓢。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "string", "description": "修改前全文"},
                "after": {"type": "string", "description": "修改后全文"},
                "genre": {"type": "string", "default": "empirical"},
            },
            "required": ["before", "after"],
        },
    },
]


# --- Trilingual tool descriptions (en primary / zh / ja) ---------------------
# Papers are written in English, so English is the authoritative description
# language; the original Chinese text is preserved in description_zh and a
# concise Japanese summary is provided in description_ja. MCP clients that
# only read `description` get precise English; trilingual-aware surfaces can
# render all three.

_TOOL_DESC_EN = {
    "render_template": "Generate a genre-based Markdown paper template: survey / empirical / tech / thesis / argumentative, with optional journal length planning.",
    "word_count": "Count Chinese characters, English words and code blocks after stripping Markdown; body-only caliber excludes the references section.",
    "check_structure": "Validate heading-level continuity (no skipped levels); ignores fenced code blocks; supports Markdown and LaTeX sources.",
    "generate_outline": "Produce a structured paper outline by genre from a research topic or question.",
    "literature_checklist": "Build a per-entry verification checklist from the reference list (A/B/C grading, DOI status placeholders) to keep unverified citations out of submissions.",
    "submission_checklist": "Pre-submission checklist: journal fit, ICMJE authorship, cover letter, ethics and AI disclosure, final DOI verification.",
    "journal_matcher": "Heuristic journal recommendations by topic keywords and paper type against a curated 20-journal database.",
    "citation_verify": "Verify citation existence via Crossref: DOI exact match first, else normalized-title similarity search with field cross-checks; returns A/B/C grade. Anti-hallucination gate for references.",
    "lit_search": "Real literature search via Semantic Scholar API with backoff retry on rate limits.",
    "journal_search_openalex": "Live journal discovery via OpenAlex across all disciplines: publisher, works count, citations, h-index, ISSN, OA status.",
    "verify_references": "Batch reference verification with per-entry DOI-first lookup and title fallback; emits a Markdown A/B/C summary report suitable as a mandatory pre-delivery gate.",
    "check_style": "Style check: AI-flavor words, colloquialisms, filler phrases, overclaims, over-long paragraphs and sentences with line numbers.",
    "check_punctuation": "Punctuation audit for CJK/Latin half-full-width mixing; fenced code blocks ignored.",
    "check_figures_tables": "Figure/table integrity: numbering gaps and caption vs in-text reference mismatches.",
    "check_terms": "Terminology hygiene: undefined acronyms, unused definitions, inconsistent variants; common acronyms exempt by default.",
    "check_duplicates": "Duplicate-content check: identical normalized sentences appearing more than once in the body.",
    "check_references_format": "Reference format audit: duplicate entries, future years (hallucination signal), mixed APA/GB-T/IEEE styles.",
    "proofread": "Composite proofreading report running all structural and textual checkers at once with ERROR/WARNING/INFO severities; format=json for structured output.",
    "check_intext_citations": "Bidirectional in-text vs reference-list cross-check: numeric [1]/[2,5]/[3-7] patterns (phantom citations, orphan entries, duplicate numbers), author-year matching, style-mix warnings.",
    "check_sections": "Genre-aware required-section completeness plus keywords-line presence and count.",
    "word_budget": "Per-section word counts compared with journal length targets (same source as render_template).",
    "check_ai_signature": "AI-writing statistical signature (heuristic hint, not a verdict): sentence-length burstiness CV, MATTR lexical richness, template-phrase density, transition openers, em-dash dash density; outputs a 0-100 score plus per-item evidence; refuses texts shorter than the sentence floor. style=stem applies full quantitative-calibrated metrics; style=humanities strips distribution terms for humanities prose.",
    "check_tamper_traces": "Tamper-trace forensics (objective character-level evidence): zero-width/invisible characters, Cyrillic/Greek homoglyphs injected inside Latin words (RAID homoglyph signature; genuine Russian/Greek passages naturally exempt), in-line whitespace runs. Detects processing traces, not whether text is AI-written.",
    "check_numbers": "Numeric-consistency engine: conflicting sample-size claims (non-exclusive buckets exempt), percent-sum overflow, ratios above 100% - classic fabrication signals.",
    "check_hedging": "Per-section assertion-strength profile: absolute terms vs hedges; dense unhedged sections are flagged.",
    "check_stats": "Statistical reporting redlines: test name near every p-value, out-of-range and p=0.000 fixes, significance claims require effect size and confidence interval.",
    "audit_paper": "One-shot full audit: all checkers + AI signature + tamper-trace forensics + section completeness + statistical integrity + optional word budget, returning a heuristic 0-100 score. The score reflects issue density pending human review, not a quality verdict.",
    "check_self_plagiarism": "Cross-document self-overlap: n-gram overlap against a corpus directory of past manuscripts (.md/.txt/.tex).",
    "audit_pdf": "Best-effort PDF submission audit via stdlib-only text extraction; unreliable checks are honestly reported as skipped.",
    "format_citation": "Citation entry formatter: verify via Crossref then emit APA 7 / GB-T 7714 / IEEE / MLA 9 / Chicago / BibTeX; no entry unless verified.",
    "check_abstract": "Abstract four-element check: locates the abstract, verifies purpose/methods/results/conclusion coverage, length band, and quantified numbers for empirical papers.",
    "check_title": "Title quality: length band, vague wording (A Study of / 浅析), capitalization conventions, question-form and subtitle hints.",
    "audit_project": "Multi-file thesis audit: merges chapter files in natural order, then runs per-chapter word tables, the full proofread suite on merged text, and AI signature analysis.",
    "next_actions": "Agent plan router: returns an ordered JSON plan (tool / params template / pass condition per step) for a chosen goal — submission, thesis, or polish — so the agent can drive the full delivery pipeline step by step.",
    "gate_suite": "Composite gate suite: runs all (or selected) offline deterministic checkers in one call and returns a unified JSON verdict (pass = zero errors) with blocking issues, designed for agent fix-then-rerun loops.",
    "check_vague_attribution": "Vague-attribution check: sentences appealing to unnamed authorities ('studies show', 'experts agree', 'people generally believe') with no citation in the same sentence — the polished-but-vague hallmark of AI text. Exempt when a citation appears in the sentence.",
    "check_references_completeness": "Per-entry reference completeness: missing year, missing source, missing volume/pages, CJK entries without GB/T 7714 type markers, and malformed DOIs (bad registrant length, embedded spaces, trailing punctuation).",
    "check_references_recency": "Literature-recency signal: with four or more dated entries, reports median reference age; flags when all or 70%+ of references are older than 10 years as a stale-review signal.",
    "check_placeholders": "Placeholder and unfinished-work traces: TODO, FIXME, ???, [citation needed], and Chinese equivalents — must be zero before delivery.",
    "check_links": "Link trustworthiness: offline checks for placeholder domains (example.com/localhost), reserved/invalid TLDs, and hostless URLs; with live=true, HEAD-verifies each URL (404/410 dead links; blocked requests reported honestly as unverifiable).",
    "check_encoding": "Encoding health check (document substrate): U+FFFD replacement chars and (cid:N) PDF-extraction artifacts (unreadable text, error-level), UTF-8-read-as-Latin-1 mojibake signatures, stray control characters, and mid-file BOM. A broken substrate invalidates every line-numbered finding above it.",
    "check_ethics_statements": "Legitimacy-precondition check (gate tower layer P): presence of ethics approval / informed consent, conflict-of-interest disclosure, AI-use disclosure (AIGC compliance), and data availability statements. Missing ethics with human subjects in the text is an error (desk-reject redline); other absences are warnings. Presence only — statement truth is the authors' responsibility.",
    "check_retraction": "Retraction screening (live, gate tower layer L1): checks each cited work against Crossref update-to / relation.is-retracted-by records and retraction-notice title signatures — external API facts, not heuristics. Citing a retracted work is an error (integrity hardline); network failures are reported as unverifiable (info) per the X-grade discipline and never trip the gate.",
    "check_claim_citation_fit": "Claim-citation fit check (live+cache, gate tower layer L2): for sentences carrying strong-claim wording plus a citation, compares lexical overlap between the claim and the cited source's title/abstract; low overlap suggests manual review. Low fit does not mean a wrong citation (warning-level); sources that cannot be fetched are honestly skipped. Semantic support verification is out of scope (would require model inference).",
    "check_version_mismatch": "Preprint-to-published version mismatch check (live, gate tower layer L2): when a reference entry carries an arXiv identifier, searches Crossref by title for a formally published version (similarity threshold guards against false matches); a hit that is not the preprint itself suggests updating the citation. Warning-level — citing a preprint is not wrong, but the citation should be refreshed when a published version exists.",
    "audit_delta": "Fix-delta comparison: runs the same gate bundle on before/after manuscripts and reports fixed vs introduced vs persisted findings with a net-improvement verdict, so every agent edit round is verified.",
}

_TOOL_DESC_JA = {
    "render_template": "論文体裁別のMarkdownテンプレートを生成（survey/empirical/tech/thesis/argumentative、誌面分量プラン任意）。",
    "word_count": "Markdownを除去した上で中国語字数・英語語数・コードブロック数を集計（参考文献除外の本文基準）。",
    "check_structure": "見出しレベルの連続性（飛び級）を検証。コードブロックは無視、Markdown/LaTeX両対応。",
    "generate_outline": "研究テーマから体裁別の構造化アウトラインを生成。",
    "literature_checklist": "参考文献リストから項目ごとの検証チェックリスト（A/B/C評価・DOI状態）を作成。",
    "submission_checklist": "投稿前チェックリスト：誌性適合・ICMJE著者基準・カバーレター・倫理とAI開示・最終DOI検証。",
    "journal_matcher": "トピックキーワードと論文タイプから厳選20誌のデータベースにより候補誌を推奨。",
    "citation_verify": "Crossrefで文献の実在を検証：DOI完全一致優先、無ければタイトル類似検索＋フィールド照合、A/B/C判定を返す。",
    "lit_search": "Semantic Scholar APIによる実際の文献検索（レート制限時は自動バックオフ）。",
    "journal_search_openalex": "OpenAlex APIによる全分野のジャーナル実時検索（発行元・論文数・被引・h指数・ISSN・OA状況）。",
    "verify_references": "参考文献の一括検証（DOI優先→タイトルフォールバック）、A/B/C集計のMarkdown報告書を生成。納品前ゲートに使用可。",
    "check_style": "文体検査：AI特有語・口語・水増し表現・過剰主張・長文段落/長文（行番号付き）。",
    "check_punctuation": "CJK/ラテン文字の全角半角混用を検査（コードブロック除外）。",
    "check_figures_tables": "図表の整合性：番号欠落とキャプション↔本文参照の不一致。",
    "check_terms": "用語衛生：未定義略語・未使用定義・表記ゆれ（一般略語は既定で免除）。",
    "check_duplicates": "重複検査：正規化後に同一となる文の複数出現。",
    "check_references_format": "文献形式監査：重複エントリ・未来年（ハルシネーション兆候）・APA/GB-T/IEEE形式の混在。",
    "proofread": "全チェッカーを一括実行する組合せ校閲レポート（ERROR/WARNING/INFO）。format=jsonで構造化出力。",
    "check_intext_citations": "本文引用↔文献リストの双方向照合：数字式[1]/[2,5]/[3-7]（幽霊引用・孤立項目・番号重複）、著者-年式照合、様式混用警告。",
    "check_sections": "体裁別の必須セクション充足性＋キーワード行の有無と数量。",
    "word_budget": "セクション別語数を誌面分量目標と対比（render_templateと同一ソース）。",
    "check_ai_signature": "AI執筆統計シグネチャ（ヒューリスティック参考、判定ではない）：文長バースト性CV・MATTR・テンプレート句密度・文頭転換語・em-dash密度→0-100点＋根拠一覧。短文は拒否。style=stemは定量校正済み全指標、style=humanitiesは分布指標を除外。",
    "check_tamper_traces": "改ざん痕跡フォレンジクス（客観的な文字レベル証拠）：ゼロ幅/不可視文字、ラテン単語内へのキリル/ギリシャ同形字注入（RAID homoglyph署名、本来のロシア語/ギリシャ語段落は自然免除）、行内異常空白。AI執筆の判定ではなく処理痕跡の検出。",
    "check_numbers": "数値整合性エンジン：サンプル数の矛盾（非排他区分は免除）、百分比合計超過、100%超の比率——捏造の典型的信号。",
    "check_hedging": "セクション別の断言強度プロファイル：絶対表現vsヘッジ、ヘッジなしの密集セクションを警告。",
    "check_stats": "統計報告のレッドライン：p値近傍の検定名、範囲外およびp=0.000の修正、有意な主張には効果量と信頼区間が必要。",
    "audit_paper": "ワンクリック全文監査：全チェッカー＋AI署名＋改ざん痕跡フォレンジクス＋セクション充足性＋統計整合性＋任意語数予算→ヒューリスティック0-100点。総合点は人による確認待ちの問題密度を反映し、品質判定ではない。",
    "check_self_plagiarism": "自己重複の文書横断検査：過去原稿ディレクトリ(.md/.txt/.tex)とのn-gram重複率。",
    "audit_pdf": "PDF投稿監査（ベストエフォート）：標準ライブラリのみでテキスト抽出し、信頼できない検査は正直にスキップ表示。",
    "format_citation": "引用エントリ整形：Crossref検証後にAPA 7/GB-T 7714/IEEE/MLA 9/Chicago/BibTeXで出力。未検証なら出力しない。",
    "check_abstract": "抄録四要素検査：目的/方法/結果/結論の網羅・長さ帯・実証論文の量化数字の有無。",
    "check_title": "タイトル品質：長さ帯・曖昧語（A Study of/浅析など）・大文字小文字慣行・疑問形とサブタイトル構造。",
    "audit_project": "複数ファイル学位論文監査：章ファイルを自然順にマージし、章別語数表＋全文校閲＋AI署名分析を実行。",
    "next_actions": "エージェント計画ルータ：目標（submission/thesis/polish）に応じ、工具・パラメータ雛形・合格条件を含む順序付きJSON計画を返す。",
    "gate_suite": "複合ゲートスイート：オフライン決定論的検査器を一括実行し、統一JSON判定（pass＝エラー0）と遮断項目を返す。修正→再実行ループ向け。",
    "check_vague_attribution": "曖昧な帰属：同文に出典のない'研究表明/experts say/人々が一般に考えている'的な権威への訴えを検出。同文に引用があれば免除。",
    "check_references_completeness": "文献の完全性：年・出典・巻頁の欠落、中国語文献のGB/T 7714タイプ標識欠落、DOI構文異常を検査。",
    "check_references_recency": "文献の鮮度：特定可能な年が4件以上のとき、中央値文献年齢と古い割合を報告し、陳腐化シグナルを提示。",
    "check_placeholders": "プレースホルダ痕跡：TODO、FIXME、???、[citation needed]、待补充など、提出前に必ず除去。",
    "check_links": "リンク信頼性：プレースホルダドメイン・無効TLD・ホストなしURLをオフライン検査；live=trueでHEAD検証（404/410は死リンク）。",
    "check_encoding": "エンコーディング健全性検査（文書基盤）：U+FFFD置換文字と(cid:N) PDF抽出残骸（読めない文字、error）、UTF-8をLatin-1誤読した文字化けシグネチャ、異常制御文字、文中BOMを検出。基盤が壊れると行番号証拠は無効化される。",
    "check_ethics_statements": "適法性前提検査（ゲート塔P層）：倫理承認/インフォームド・コンセント、利益相反開示、AI利用開示（AIGC準拠）、データ利用可能性声明の存在確認。人間被験者に言及しつつ倫理声明が欠落の場合はerror（デスクリジェクト級）、その他の欠落はwarning。存在確認のみで真偽は著者の責任。",
    "check_retraction": "撤稿スクリーニング（オンライン、ゲート塔L1層）：Crossref の update-to / relation.is-retracted-by 記録と撤稿声明タイトルにより、引用文献の撤稿状態を確認（外部APIの事実）。撤稿済み文献の引用はerror（誠信の要警戒事項）、ネットワーク失敗はX級規律に従い unverifiable（info）としてゲートを発動しない。",
    "check_claim_citation_fit": "主張-引用適合検査（オンライン+キャッシュ、ゲート塔L2層）：強い主張表現+引用を含む文について、主張文と被引用文献のタイトル/抄録との語彙重複率を比較し、低過ぎる場合は手動確認を提示。適合度が低い≠引用が誤り（warning）。意味レベルの裏付け検証は対象外（モデル推論が必要）。",
    "check_version_mismatch": "プレプリント-正式版不一致検査（オンライン、ゲート塔L2層）：arXiv識別子を含む文献について、タイトルでCrossref検索し正式発表版が存在すれば引用更新を提示（warning）。プレプリント引用自体は誤りではない。",
    "audit_delta": "修正差分比較：修正前後の原稿に同一ゲート束を実行し、解決/新規/残存を差集合で報告し、純改善判定を返す。",
}


def _localize_tool_descriptions() -> None:
    """Promote English to the primary description; keep zh/ja as siblings."""
    for tool in TOOLS:
        name = tool.get("name", "")
        en = _TOOL_DESC_EN.get(name)
        if en:
            tool["description_zh"] = tool["description"]
            tool["description"] = en
        ja = _TOOL_DESC_JA.get(name)
        if ja:
            tool["description_ja"] = ja


_localize_tool_descriptions()


def _result_text(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


# Windows 编辑器常写入 BOM/零宽字符，会让 ^ 锚定的标题/引用正则在首行失配
_LEADING_INVISIBLE_RE = re.compile("^[\ufeff\u200b\u200e\u200f]+")


def _md(args: dict, key: str = "markdown") -> str:
    """取并清洗文本参数：剥离首部 BOM 与零宽字符。"""
    return _LEADING_INVISIBLE_RE.sub("", str(args.get(key, "")))


def _call_tool(name: str, arguments: dict) -> dict:
    args = arguments or {}
    if name == "render_template":
        return _result_text(render_template(str(args.get("genre", "survey")), str(args.get("journal", "") or None)))
    if name == "word_count":
        return _result_text(json.dumps(word_count(_md(args), str(args.get("source_format", "markdown"))), ensure_ascii=False))
    if name == "check_structure":
        return _result_text(json.dumps(check_structure(_md(args), str(args.get("source_format", "markdown"))), ensure_ascii=False))
    if name == "generate_outline":
        return _result_text(generate_outline(str(args.get("topic", "")), str(args.get("genre", "empirical"))))
    if name == "literature_checklist":
        return _result_text(literature_checklist(_md(args)))
    if name == "submission_checklist":
        return _result_text(submission_checklist(str(args.get("journal", "")), str(args.get("topic", ""))))
    if name == "journal_matcher":
        return _result_text(journal_matcher(str(args.get("topic", "")), str(args.get("paper_type", "conceptual"))))
    if name == "citation_verify":
        return _result_text(
            citation_verify(
                str(args.get("doi", "")),
                str(args.get("title", "")),
                str(args.get("authors", "")),
                int(args.get("year", 0) or 0),
            )
        )
    if name == "lit_search":
        return _result_text(
            lit_search(
                str(args.get("query", "")),
                int(args.get("limit", 5)),
            )
        )
    if name == "journal_search_openalex":
        return _result_text(
            journal_search_openalex(
                str(args.get("query", "")),
                int(args.get("limit", 5)),
            )
        )
    if name == "verify_references":
        return _result_text(
            verify_references(
                _md(args),
                int(args.get("max_entries", 30)),
            )
        )
    if name == "check_style":
        return _result_text(json.dumps(check_style(_md(args)), ensure_ascii=False))
    if name == "check_punctuation":
        return _result_text(json.dumps(check_punctuation(_md(args)), ensure_ascii=False))
    if name == "check_figures_tables":
        return _result_text(json.dumps(check_figures_tables(_md(args)), ensure_ascii=False))
    if name == "check_terms":
        return _result_text(json.dumps(check_terms(_md(args), bool(args.get("allow_common", True)), str(args.get("source_format", "markdown"))), ensure_ascii=False))
    if name == "check_duplicates":
        return _result_text(json.dumps(check_duplicates(_md(args)), ensure_ascii=False))
    if name == "check_references_format":
        return _result_text(json.dumps(check_references_format(_md(args)), ensure_ascii=False))
    if name == "check_intext_citations":
        return _result_text(json.dumps(check_intext_citations(_md(args)), ensure_ascii=False))
    if name == "check_sections":
        return _result_text(json.dumps(check_sections(_md(args), str(args.get("genre", "empirical"))), ensure_ascii=False))
    if name == "word_budget":
        return _result_text(json.dumps(word_budget(_md(args), str(args.get("journal", ""))), ensure_ascii=False))
    if name == "check_ai_signature":
        return _result_text(json.dumps(check_ai_signature(_md(args), int(args.get("min_sentences", 8)), str(args.get("style", "stem"))), ensure_ascii=False))
    if name == "check_tamper_traces":
        return _result_text(json.dumps(check_tamper_traces(_md(args)), ensure_ascii=False))
    if name == "check_numbers":
        return _result_text(json.dumps(check_numbers(_md(args)), ensure_ascii=False))
    if name == "check_hedging":
        return _result_text(json.dumps(check_hedging(_md(args)), ensure_ascii=False))
    if name == "check_stats":
        return _result_text(json.dumps(check_stats(_md(args)), ensure_ascii=False))
    if name == "audit_pdf":
        return _result_text(
            audit_pdf(
                str(args.get("pdf_path", "")),
                str(args.get("genre", "empirical")),
                str(args.get("format", "markdown")),
                int(args.get("min_chars", 200)),
            )
        )
    if name == "check_self_plagiarism":
        return _result_text(
            json.dumps(
                check_self_plagiarism(
                    _md(args),
                    str(args.get("corpus_dir", "")),
                    int(args.get("min_gram", 8)),
                    float(args.get("threshold", 0.05)),
                ),
                ensure_ascii=False,
            )
        )
    if name == "audit_paper":
        return _result_text(
            audit_paper(
                _md(args),
                str(args.get("genre", "empirical")),
                str(args.get("journal", "")),
                bool(args.get("allow_common_acronyms", True)),
                str(args.get("format", "markdown")),
                str(args.get("source_format", "markdown")),
                bool(args.get("brief", False)),
            )
        )
    if name == "proofread":
        return _result_text(
            proofread(
                _md(args),
                bool(args.get("allow_common_acronyms", True)),
                str(args.get("format", "markdown")),
                str(args.get("source_format", "markdown")),
                str(args.get("genre", "empirical")),
            )
        )
    if name == "format_citation":
        return _result_text(
            format_citation(
                str(args.get("doi", "")),
                str(args.get("title", "")),
                str(args.get("style", "apa")),
                str(args.get("authors", "")),
                int(args.get("year", 0) or 0),
            )
        )
    if name == "check_abstract":
        return _result_text(json.dumps(check_abstract(_md(args), str(args.get("genre", "empirical"))), ensure_ascii=False))
    if name == "check_title":
        return _result_text(json.dumps(check_title(_md(args), str(args.get("title", ""))), ensure_ascii=False))
    if name == "audit_project":
        return _result_text(
            audit_project(
                str(args.get("project_dir", "")),
                str(args.get("genre", "thesis")),
                str(args.get("journal", "")),
                str(args.get("format", "markdown")),
                int(args.get("max_files", 30)),
            )
        )
    if name == "next_actions":
        return _result_text(next_actions(str(args.get("goal", "submission")), str(args.get("genre", "empirical"))))
    if name == "gate_suite":
        return _result_text(
            gate_suite(
                str(args.get("markdown", "")),
                str(args.get("gates", "")),
                str(args.get("genre", "empirical")),
                bool(args.get("allow_common_acronyms", True)),
            )
        )
    if name == "check_vague_attribution":
        return _result_text(json.dumps(check_vague_attribution(_md(args)), ensure_ascii=False))
    if name == "check_references_completeness":
        return _result_text(json.dumps(check_references_completeness(_md(args)), ensure_ascii=False))
    if name == "check_references_recency":
        return _result_text(json.dumps(check_references_recency(_md(args)), ensure_ascii=False))
    if name == "check_placeholders":
        return _result_text(json.dumps(check_placeholders(_md(args)), ensure_ascii=False))
    if name == "check_links":
        return _result_text(json.dumps(check_links(_md(args), bool(args.get("live", False))), ensure_ascii=False))
    if name == "check_encoding":
        return _result_text(json.dumps(check_encoding(_md(args)), ensure_ascii=False))
    if name == "check_ethics_statements":
        return _result_text(json.dumps(check_ethics_statements(_md(args), str(args.get("genre", "empirical"))), ensure_ascii=False))
    if name == "check_retraction":
        return _result_text(json.dumps(check_retraction(_md(args), int(args.get("max_entries", 30))), ensure_ascii=False))
    if name == "check_claim_citation_fit":
        return _result_text(json.dumps(check_claim_citation_fit(_md(args), int(args.get("max_assessed", 15))), ensure_ascii=False))
    if name == "check_version_mismatch":
        return _result_text(json.dumps(check_version_mismatch(_md(args), int(args.get("max_entries", 30))), ensure_ascii=False))
    if name == "audit_delta":
        return _result_text(
            audit_delta(
                str(args.get("before", "")),
                str(args.get("after", "")),
                str(args.get("genre", "empirical")),
            )
        )
    return {"isError": True, "content": [{"type": "text", "text": f"未知工具: {name}"}]}


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": VERSION},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        try:
            result = _call_tool(params.get("name", ""), params.get("arguments", {}))
        except Exception as exc:
            result = {"isError": True, "content": [{"type": "text", "text": f"工具执行失败: {exc}"}]}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if method.startswith("notifications/"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"未知方法: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            # JSON-RPC 2.0 规范：解析失败必须返回 -32700，静默丢弃会让客户端超时等待
            sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {e}"},
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            sys.stdout.flush()
            continue
        if not isinstance(msg, dict) or "method" not in msg:
            continue
        response = handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
