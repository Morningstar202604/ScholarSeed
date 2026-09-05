#!/usr/bin/env python3
# Copyright 2026 ScholarSeed contributors
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE.
# Commercial use requires a separate license from the maintainers.
"""PaperIR：论文文档中间表示（门禁塔 L0 层的地基）。

架构依据见 docs/ARCHITECTURE.md。此前每个检查器独立对全文做一遍解析，
围栏剥离/参考文献定位/句子切分各写一遍，曾集中产出"行号漂移"一类 bug
（v0.2.0 修复记录）。本模块把文档结构解析收敛为**一次解析、全塔共享**：

- 共享文本辅助函数（行号映射/围栏置空/句子切分等）集中于此，paper_tools.py
  以 `from paper_ir import ...` 复用，名称与语义完全不变；
- `parse_paper_ir()` 返回结构化文档模型（标题/摘要/章节树/句子流/文献段/围栏），
  新检查器优先基于 IR 编写，存量检查器按 ROADMAP 分批迁移（行为不变）。

纯标准库，零依赖。输入是"已规范化的 Markdown 文本"——LaTeX 由
paper_tools 的 source_format=latex 链路先转换，本模块不做格式识别。
"""

from __future__ import annotations

import re
from bisect import bisect_right

__all__ = [
    "_blank_fences",
    "_count_cjk",
    "_count_words_en",
    "_extract_abstract",
    "_find_pattern",
    "_find_reference_heading",
    "_line_starts",
    "_pos_to_line",
    "_split_body_references",
    "_split_sentences",
    "iter_sentences",
    "parse_paper_ir",
]


# ---------------------------------------------------------------------------
# 共享文本辅助函数（自 paper_tools.py 迁入，语义与名称保持不变）
# ---------------------------------------------------------------------------


def _line_starts(text: str) -> list:
    return [0] + [m.end() for m in re.finditer(r"\n", text)]


def _pos_to_line(pos: int, starts: list) -> int:
    return bisect_right(starts, pos)


def _find_pattern(text: str, pattern: str, flags: int = 0) -> list:
    """返回 [(行号, 命中片段)]，供各检查器复用。"""
    starts = _line_starts(text)
    out = []
    for m in re.finditer(pattern, text, flags):
        line = _pos_to_line(m.start(), starts)
        snippet = m.group(0).strip()
        out.append((line, snippet))
    return out


def _blank_fences(text: str) -> str:
    """将 ``` 围栏代码块内容置空但保留换行数量，使行号映射不漂移。"""

    def _repl(m):
        return "\n" * m.group(0).count("\n")

    return re.sub(r"```.*?```", _repl, text, flags=re.S)


def _count_cjk(text: str) -> int:
    """统计中文字符数（统一 CJK 区间，避免各处重写 [一-鿿] 字面量）。"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _count_words_en(text: str) -> int:
    """统计拉丁词数（统一正则，避免各处重写 [A-Za-z]+ 字面量）。"""
    return len(re.findall(r"[A-Za-z]+", text))


def _find_reference_heading(markdown: str) -> "re.Match | None":
    """定位参考文献小节标题（H1-H3，支持中英文），集中复用避免三处重复正则。"""
    return re.search(r"^#{1,3}\s*(?:References|参考文献)\s*$", markdown, flags=re.M)


def _split_sentences(text: str, keep_punct: bool = False) -> list:
    """按中英文句末标点切分正文；keep_punct=True 保留句末标点（check_style 需展示片段）。"""
    if keep_punct:
        parts = re.split(r"(?<=[。！？.!?])\s*", text)
    else:
        parts = re.split(r"[。！？.!?]\s*", text)
    return [p for p in parts if p.strip()]


def _split_body_references(markdown: str) -> tuple:
    """按参考文献标题切分为（正文, 文献段）。无文献标题时文献段为空。"""
    m = _find_reference_heading(markdown)
    if not m:
        return markdown, ""
    return markdown[: m.start()], markdown[m.end() :]


def _extract_abstract(markdown: str) -> str:
    """定位摘要段：优先标题级（## 摘要），其次加粗/标签行（**摘要**：…），取到下一个标题为止。"""
    hm = re.search(r"^#{1,3}\s*(?:摘要|abstract)\s*$", markdown, flags=re.M | re.I)
    if hm:
        rest = markdown[hm.end() :]
        stop = re.search(r"^#{1,3}\s*", rest, flags=re.M)
        return (rest[: stop.start()] if stop else rest).strip()
    lm = re.search(r"^(?:\*\*)?\s*(?:摘要|abstract)(?:\*\*)?\s*[:：]\s*(.*)$", markdown, flags=re.M | re.I)
    if lm:
        para_start = lm.end() - len(lm.group(1))
        rest = markdown[para_start:]
        stop = re.search(r"^#{1,3}\s*|\n\s*\n", rest.lstrip("\n"))
        return (rest[: stop.start()] if stop else rest).strip()
    return ""


# ---------------------------------------------------------------------------
# 文档模型：一次解析，全塔共享
# ---------------------------------------------------------------------------


def iter_sentences(text: str, blank_fences: bool = True) -> list:
    """带行号的句子迭代：返回 [(line, sentence)]，切分语义与 _split_sentences(keep_punct=True) 一致。

    blank_fences=True 时围栏代码块先置空（保留换行数）——_blank_fences 保证行数
    不变但字符位置漂移，故本函数返回**行号**而非字符偏移（行号是全项目的证据通货）。
    围栏代码内容置空后不产出句子。
    """
    s = _blank_fences(text) if blank_fences else text
    starts = _line_starts(s)
    out = []
    pos = 0
    for part in _split_sentences(s, keep_punct=True):
        idx = s.find(part, pos)
        if idx < 0:
            idx = pos
        pos = idx + len(part)
        if part.strip():
            out.append((_pos_to_line(idx, starts), part.strip()))
    return out


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", flags=re.M)
_YAML_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", flags=re.S)


def parse_paper_ir(markdown: str) -> dict:
    """把 Markdown 稿解析为结构化文档模型（IR），行号全保真（1 起始）。

    返回字段：
        title            首个 H1 标题文本（无则空串）
        title_line       标题行号（无则 0）
        yaml             YAML frontmatter 原文（无则空串）
        abstract         摘要段文本（无则空串）
        abstract_line    摘要起始行号（无则 0）
        sections         [{level, title, line, start, end, text}] 按文档顺序
        body             截去参考文献段后的正文（围栏保留原文）
        refs             参考文献段原文（无文献标题则空串）
        refs_start_line  文献段首行行号（无则 0）
        sentences        正文句子 [(line, sentence)]，围栏内容已置空
        fence_spans      围栏代码块 [(start, end)] 原文跨度
    """
    text = markdown or ""
    starts = _line_starts(text)

    yaml_m = _YAML_FRONTMATTER_RE.match(text)
    yaml_text = yaml_m.group(0) if yaml_m else ""

    title, title_line = "", 0
    sections = []
    headings = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in _HEADING_RE.finditer(text)]
    for i, (pos, level, htitle) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        sections.append({
            "level": level,
            "title": htitle,
            "line": _pos_to_line(pos, starts),
            "start": pos,
            "end": end,
            "text": text[pos:end],
        })
        if level == 1 and not title:
            title, title_line = htitle, _pos_to_line(pos, starts)

    body, refs = _split_body_references(text)
    refs_start = _pos_to_line(len(body), starts) if refs else 0
    abstract = _extract_abstract(text)
    abstract_line = 0
    if abstract:
        probe = abstract.strip()[:24]
        hit = text.find(probe)
        if hit >= 0:
            abstract_line = _pos_to_line(hit, starts)

    fence_spans = [(m.start(), m.end()) for m in re.finditer(r"```.*?```", text, flags=re.S)]

    return {
        "title": title,
        "title_line": title_line,
        "yaml": yaml_text,
        "abstract": abstract,
        "abstract_line": abstract_line,
        "sections": sections,
        "body": body,
        "refs": refs,
        "refs_start_line": refs_start,
        "sentences": iter_sentences(body),
        "fence_spans": fence_spans,
    }
