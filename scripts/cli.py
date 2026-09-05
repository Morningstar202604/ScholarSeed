#!/usr/bin/env python3
# Copyright 2026 ScholarSeed contributors
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE.
# Commercial use requires a separate license from the maintainers.
"""ScholarSeed CLI：同一引擎的人用入口（无 Agent 场景 / CI 门禁）。

用法示例（仓库根目录）：
    python scripts/cli.py --version
    python scripts/cli.py proofread paper.md --genre empirical
    python scripts/cli.py verify-refs paper.md --fail-on C      # CI：有 C 级未核验文献则退出码 1
    python scripts/cli.py citation 10.1038/nature14539 --style gbt
    python scripts/cli.py check abstract paper.md
    python scripts/cli.py project ./thesis-chapters

退出码约定：0 正常；1 门禁未过（--fail-on 命中）；2 输入错误（文件/目录不存在等）。
纯标准库，零第三方依赖。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paper_tools as pt

EXIT_OK = 0
EXIT_GATE_FAIL = 1
EXIT_INPUT_ERROR = 2


def _read(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")
    return p.read_text(encoding="utf-8-sig")


def _emit(value) -> None:
    if isinstance(value, str):
        print(value)
        return
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _load_json(text: str):
    """JSON 字符串→对象；非 JSON（如 Markdown 报告）原样返回，避免二次编码。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _add_genre(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--genre", default="empirical", choices=["empirical", "survey", "tech", "thesis"])


# --- 各子命令实现：返回 (payload, exit_code) -------------------------------


def cmd_version(args) -> tuple:
    return f"ScholarSeed {pt.VERSION} (engine {pt.SERVER_NAME}, Agent Plugins 1.0)", EXIT_OK


def cmd_template(args) -> tuple:
    return pt.render_template(args.genre, args.journal or None), EXIT_OK


def cmd_outline(args) -> tuple:
    return pt.generate_outline(args.topic, args.genre), EXIT_OK


def cmd_word_count(args) -> tuple:
    return pt.word_count(_read(args.file), args.source_format), EXIT_OK


def cmd_structure(args) -> tuple:
    return pt.check_structure(_read(args.file), args.source_format), EXIT_OK


CHECKERS = {
    "style": lambda a: pt.check_style(pt._md({"markdown": _read(a.file)})),
    "punctuation": lambda a: pt.check_punctuation(pt._md({"markdown": _read(a.file)})),
    "figures": lambda a: pt.check_figures_tables(pt._md({"markdown": _read(a.file)})),
    "terms": lambda a: pt.check_terms(pt._md({"markdown": _read(a.file)}), allow_common=not a.no_common),
    "duplicates": lambda a: pt.check_duplicates(pt._md({"markdown": _read(a.file)})),
    "refs-format": lambda a: pt.check_references_format(pt._md({"markdown": _read(a.file)})),
    "intext": lambda a: pt.check_intext_citations(pt._md({"markdown": _read(a.file)})),
    "abstract": lambda a: pt.check_abstract(pt._md({"markdown": _read(a.file)}), a.genre),
    "title": lambda a: pt.check_title(pt._md({"markdown": _read(a.file)}), a.title or ""),
    "numbers": lambda a: pt.check_numbers(pt._md({"markdown": _read(a.file)})),
    "hedging": lambda a: pt.check_hedging(pt._md({"markdown": _read(a.file)})),
    "stats": lambda a: pt.check_stats(pt._md({"markdown": _read(a.file)})),
    "ai-signature": lambda a: pt.check_ai_signature(pt._md({"markdown": _read(a.file)})),
    "tamper": lambda a: pt.check_tamper_traces(pt._md({"markdown": _read(a.file)})),
    "encoding": lambda a: pt.check_encoding(pt._md({"markdown": _read(a.file)})),
}


def cmd_check(args) -> tuple:
    if args.checker not in CHECKERS:
        valid = ", ".join(sorted(CHECKERS))
        print(f"未知检查器: {args.checker}（可用: {valid}）", file=sys.stderr)
        return None, EXIT_INPUT_ERROR
    return CHECKERS[args.checker](args), EXIT_OK


def cmd_citation(args) -> tuple:
    doi = args.doi_or_title if args.doi_or_title.startswith("10.") else ""
    title = "" if doi else args.doi_or_title
    out = _load_json(pt.format_citation(doi=doi, title=title, style=args.style, authors=args.authors or "", year=args.year))
    if isinstance(out, dict) and out.get("ok") is False:
        return out, EXIT_INPUT_ERROR
    return (out.get("text") if isinstance(out, dict) else out), EXIT_OK


def cmd_lit_search(args) -> tuple:
    return _load_json(pt.lit_search(args.query, args.limit)), EXIT_OK


def cmd_journal_search(args) -> tuple:
    return _load_json(pt.journal_search_openalex(args.query, args.limit)), EXIT_OK


def cmd_verify_refs(args) -> tuple:
    md = _read(args.file)
    graded, truncated = pt._grade_reference_entries(md, args.max_entries)
    if not graded:
        print("未在文本中识别到含年份的参考文献条目。", file=sys.stderr)
        return None, EXIT_INPUT_ERROR
    counts = {"A": 0, "B": 0, "C": 0, "X": 0}
    lines = ["| # | 条目 | 分级 | 说明 |", "|---|------|------|------|"]
    for i, g in enumerate(graded, 1):
        grade = g["result"].get("grade", "C")
        counts[grade] = counts.get(grade, 0) + 1
        note = str(g["result"].get("note", "") or ("命中" if g["result"].get("verified") else ""))[:60]
        entry_short = g["entry"][:50].replace("|", "\\|")
        lines.append(f"| {i} | {entry_short} | {grade}({g['method']}) | {note.replace('|', chr(92) + '|')} |")
    print("\n".join(lines))
    summary = f"共 {len(graded)} 条：A={counts.get('A', 0)} B={counts.get('B', 0)} C={counts.get('C', 0)}"
    if counts.get("X"):
        summary += f" X={counts['X']}(网络不可达，未计入失败)"
    if truncated:
        summary += f"（超过上限仅核验前 {args.max_entries} 条）"
    print(summary)
    threshold_rank = {"C": 0, "B": 1, "X": 99}  # X=无法核验：信息项，永不触发门禁
    fail = threshold_rank.get(args.fail_on.upper(), -1)
    bad = sum(v for k, v in counts.items() if threshold_rank.get(k, 99) <= fail)
    if bad > 0:
        print(f"门禁未过：{bad} 条分级不高于 {args.fail_on.upper()}", file=sys.stderr)
        return None, EXIT_GATE_FAIL
    return None, EXIT_OK


def cmd_proofread(args) -> tuple:
    return _load_json(
        pt.proofread(_read(args.file), allow_common_acronyms=not args.no_common_acronyms, fmt="json" if args.json else "markdown", source_format=args.source_format, genre=args.genre)
    ), EXIT_OK


def cmd_audit_paper(args) -> tuple:
    return _load_json(pt.audit_paper(_read(args.file), genre=args.genre, journal=args.journal, fmt="json" if args.json else "markdown", source_format=args.source_format)), EXIT_OK


def cmd_audit_pdf(args) -> tuple:
    out = _load_json(pt.audit_pdf(args.pdf_path, genre=args.genre, fmt="json" if args.json else "markdown", min_chars=args.min_chars))
    ok = not (isinstance(out, dict) and out.get("ok") is False)
    return out, (EXIT_OK if ok else EXIT_INPUT_ERROR)


def cmd_project(args) -> tuple:
    d = Path(args.project_dir)
    if not d.is_dir():
        print(f"目录不存在: {args.project_dir}", file=sys.stderr)
        return None, EXIT_INPUT_ERROR
    return _load_json(pt.audit_project(str(d), genre=args.genre, journal=args.journal, fmt="json" if args.json else "markdown", max_files=args.max_files)), EXIT_OK


def cmd_self_plagiarism(args) -> tuple:
    corpus = Path(args.corpus_dir)
    if not corpus.is_dir():
        print(f"语料目录不存在: {args.corpus_dir}", file=sys.stderr)
        return None, EXIT_INPUT_ERROR
    return pt.check_self_plagiarism(_read(args.file), str(corpus), min_gram=args.min_gram, threshold=args.threshold), EXIT_OK


def cmd_budget(args) -> tuple:
    return pt.word_budget(_read(args.file), args.journal), EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="scholarseed", description="ScholarSeed CLI — 学术防幻觉核验与全文质检（与 MCP Server 同一引擎）")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("version").set_defaults(func=cmd_version)

    sp = sub.add_parser("template", help="生成文章 Markdown 模板")
    sp.add_argument("--genre", default="survey", choices=["survey", "empirical", "tech", "thesis"])
    sp.add_argument("--journal", default="", choices=["", "top_conceptual", "top_empirical", "general"])
    sp.set_defaults(func=cmd_template)

    sp = sub.add_parser("outline", help="生成结构化大纲")
    sp.add_argument("topic")
    _add_genre(sp)
    sp.set_defaults(func=cmd_outline)

    sp = sub.add_parser("word-count", help="统计中文字数/英文词数/代码块数")
    sp.add_argument("file")
    sp.add_argument("--source-format", default="markdown", choices=["markdown", "latex"])
    sp.set_defaults(func=cmd_word_count)

    sp = sub.add_parser("structure", help="标题层级连续性检查")
    sp.add_argument("file")
    sp.add_argument("--source-format", default="markdown", choices=["markdown", "latex"])
    sp.set_defaults(func=cmd_structure)

    sp = sub.add_parser("check", help="单项检查器：" + "/".join(sorted(CHECKERS)))
    sp.add_argument("checker")
    sp.add_argument("file")
    _add_genre(sp)
    sp.add_argument("--no-common", action="store_true", help="terms 检查不豁免通用缩写")
    sp.add_argument("--title", default="", help="title 检查直接传标题")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("citation", help="DOI/标题 → 规范引用条目（Crossref 真实核验）")
    sp.add_argument("doi_or_title", help="DOI（10. 开头）或文献标题")
    sp.add_argument("--style", default="apa", choices=["apa", "gbt", "ieee", "bibtex", "mla", "chicago"])
    sp.add_argument("--authors", default="")
    sp.add_argument("--year", type=int, default=0)
    sp.set_defaults(func=cmd_citation)

    sp = sub.add_parser("lit-search", help="Semantic Scholar 真实检索文献")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=5)
    sp.set_defaults(func=cmd_lit_search)

    sp = sub.add_parser("journal-search", help="OpenAlex 实时搜期刊")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=5)
    sp.set_defaults(func=cmd_journal_search)

    sp = sub.add_parser("verify-refs", help="批量核验参考文献（CI 门禁）")
    sp.add_argument("file")
    sp.add_argument("--max-entries", type=int, default=pt.VERIFY_REFERENCES_MAX_ENTRIES)
    sp.add_argument("--fail-on", default="", help="存在分级不高于该值则退出码 1（如 C 或 B）")
    sp.set_defaults(func=cmd_verify_refs)

    sp = sub.add_parser("proofread", help="组合校对报告")
    sp.add_argument("file")
    _add_genre(sp)
    sp.add_argument("--no-common-acronyms", action="store_true")
    sp.add_argument("--source-format", default="markdown", choices=["markdown", "latex"])
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_proofread)

    sp = sub.add_parser("audit-paper", help="一键全量审计（含 AI 画像/章节完整性/统计诚信）")
    sp.add_argument("file")
    _add_genre(sp)
    sp.add_argument("--journal", default="", choices=["", "top_conceptual", "top_empirical", "general"])
    sp.add_argument("--source-format", default="markdown", choices=["markdown", "latex"])
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_audit_paper)

    sp = sub.add_parser("audit-pdf", help="PDF 尽力级审计")
    sp.add_argument("pdf_path")
    _add_genre(sp)
    sp.add_argument("--min-chars", type=int, default=200)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_audit_pdf)

    sp = sub.add_parser("project", help="多文件学位论文工程审计")
    sp.add_argument("project_dir")
    _add_genre(sp)
    sp.add_argument("--journal", default="", choices=["", "top_conceptual", "top_empirical", "general"])
    sp.add_argument("--max-files", type=int, default=30)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_project)

    sp = sub.add_parser("self-plagiarism", help="跨文档自查重")
    sp.add_argument("file")
    sp.add_argument("--corpus-dir", required=True)
    sp.add_argument("--min-gram", type=int, default=8)
    sp.add_argument("--threshold", type=float, default=0.05)
    sp.set_defaults(func=cmd_self_plagiarism)

    sp = sub.add_parser("budget", help="分章词数对照期刊篇幅规划")
    sp.add_argument("file")
    sp.add_argument("--journal", required=True, choices=["top_conceptual", "top_empirical", "general"])
    sp.set_defaults(func=cmd_budget)

    return ap


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload, code = args.func(args)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return EXIT_INPUT_ERROR
    except Exception as e:
        print(f"执行失败: {e}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if payload is not None:
        _emit(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())
