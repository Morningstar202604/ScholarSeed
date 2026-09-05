# -*- coding: utf-8 -*-
"""v1.28.0 全面假实现排查：声明 vs 实现逐项核对。"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import paper_tools as pt

fail = []

print("=== 排查1: TOOLS 注册与分发层一一对应 ===")
names = [t["name"] for t in pt.TOOLS]
src = Path("scripts/paper_tools.py").read_text(encoding="utf-8")
dispatch_src = src.split("def _call_tool")[1].split("def handle")[0]
missing_dispatch = []
for n in names:
    if f'if name == "{n}"' not in dispatch_src:
        missing_dispatch.append(n)
print(f"注册工具数: {len(names)} | 缺分发的: {missing_dispatch or '无'}")
# 工具数量随版本演进（v1.25 时代硬编码 32 已过期），只校验"注册↔分发"一一对应
if missing_dispatch:
    fail.append("工具注册/分发不一致")

print("=== 排查2: skills 引用的文件全部存在 ===")
missing = []
for md in Path("skills").rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    for ref in re.findall(r"`((?:references/|\.\./[a-z-]+/references/|\.\./\.\./docs/)[A-Za-z\-]+\.md)`", text):
        # 相对引用可能以 references/ 所在目录或技能根为基准，双基准解析
        bases = [md.parent, md.parent.parent]
        if not any((b / ref).resolve().exists() for b in bases):
            missing.append(f"{md.name} -> {ref}")
print("缺失引用:", missing or "无")
if missing:
    fail.append(f"skills 引用缺失: {missing}")

print("=== 排查3: 六种引用风格逐一实测（mock 网络）===")
msg = {
    "DOI": "10.x/test",
    "title": ["T"],
    "author": [{"given": "A", "family": "B"}, {"given": "C", "family": "D"}],
    "container-title": ["J"],
    "volume": "1",
    "issue": "2",
    "page": "3-4",
    "issued": {"date-parts": [[2020]]},
}
orig = pt._fetch_json
pt._fetch_json = lambda url, headers=None, retries=1: {"message": msg}
style_marks = {"apa": "(2020)", "gbt": "[J]", "ieee": "vol. 1", "bibtex": "@article{", "mla": '. "T." J, vol. 1', "chicago": "(2020): 3\u20134"}
for s in ["apa", "gbt", "ieee", "bibtex", "mla", "chicago"]:
    out = pt.format_citation(doi="10.x/test", style=s)
    ok = ("分级 A" in out) and (style_marks[s] in out)
    print(f"  {s:9s} => {'OK' if ok else 'FAIL: ' + out[:100]}")
    if not ok:
        fail.append(f"format_citation[{s}]")
pt._fetch_json = orig

print("=== 排查4: ai_signature 双模式 ===")
r1 = pt.check_ai_signature("测试文本。" * 50)
r2 = pt.check_ai_signature("测试文本。" * 50, style="humanities")
r3 = pt.check_ai_signature("测试文本。" * 50, style="anything-else")
ok = r1["style"] == "stem" and r2["style"] == "humanities" and r3["style"] == "stem" and r2["score"] <= r1["score"]
print(f"  stem/humanities/fallback => {r1['style']}/{r2['style']}/{r3['style']} scores {r1['score']}/{r2['score']}/{r3['score']} => {'OK' if ok else 'FAIL'}")
if not ok:
    fail.append("ai_signature modes")

print("=== 排查5: argumentative 体裁四链路 ===")
md_arg = (
    "# 论文\n\n## 一、问题的提出\n\n内容足够长的正文。\n\n"
    "## 二、概念界定与分析框架\n\n内容足够长的正文。\n\n"
    "## 三、论证主体\n\n内容足够长的正文。\n\n"
    "## 四、对主要反驳的回应\n\n内容足够长的正文。\n\n"
    "## 五、结论与限度\n\n关键词：论证。\n"
)
sec = pt.check_sections(md_arg, genre="argumentative")
no_missing = not any(i["type"] == "missing_sections" for i in sec["issues"])
pr = json.loads(pt.proofread(md_arg, fmt="json", genre="argumentative"))
stats_absent = all(s["name"] != "统计诚信" for s in pr["sections"])
ap = pt.audit_paper(md_arg.replace("关键词：论证。", ""), genre="argumentative", journal="")
chain_ok = no_missing and stats_absent and ("审计总分" in ap) and ("反驳" in pt.render_template("argumentative")) and ("反驳" in pt.generate_outline("X", "argumentative"))
print(
    f"  sections无缺章={no_missing} proofread无统计节={stats_absent} "
    f"audit_paper={'OK' if '审计总分' in ap else 'FAIL'} 模板/大纲={'含反驳' if '反驳' in pt.render_template('argumentative') else 'FAIL'} => {'OK' if chain_ok else 'FAIL'}"
)
if not chain_ok:
    fail.append("argumentative 链路")

print("=== 排查6: 文档调用的工具名全部在注册表内 ===")
reg = set(names)
used_call = set()
used_bare = set()
call_pat = re.compile(
    r"\`(render_template|word_count|check_structure|generate_outline|literature_checklist|"
    r"submission_checklist|journal_matcher|citation_verify|lit_search|journal_search_openalex|"
    r"verify_references|check_style|check_punctuation|check_figures_tables|check_terms|"
    r"check_duplicates|check_references_format|proofread|check_intext_citations|check_sections|"
    r"word_budget|check_ai_signature|check_numbers|check_hedging|check_stats|audit_pdf|"
    r"check_self_plagiarism|audit_project|format_citation|check_abstract|check_title|audit_paper|check_retraction|check_claim_citation_fit|check_version_mismatch|check_symbol_consistency|check_abstract_promises|check_rigor_declarations|check_anonymization|check_encoding|check_ethics_statements|check_units)\("
)
bare_pat = re.compile(
    r"`(render_template|word_count|check_structure|generate_outline|literature_checklist|"
    r"submission_checklist|journal_matcher|citation_verify|lit_search|journal_search_openalex|"
    r"verify_references|check_style|check_punctuation|check_figures_tables|check_terms|"
    r"check_duplicates|check_references_format|proofread|check_intext_citations|check_sections|"
    r"word_budget|check_ai_signature|check_numbers|check_hedging|check_stats|audit_pdf|"
    r"check_self_plagiarism|audit_project|format_citation|check_abstract|check_title|audit_paper|check_retraction|check_claim_citation_fit|check_version_mismatch|check_symbol_consistency|check_abstract_promises|check_rigor_declarations|check_anonymization|check_encoding|check_ethics_statements|check_units)`"
)
for md in Path("skills").rglob("*.md"):
    t = md.read_text(encoding="utf-8")
    used_call |= set(call_pat.findall(t))
    used_bare |= set(bare_pat.findall(t))
bad = used_call - reg
print("文档调用但未注册:", bad or "无")
unbound = sorted(n for n in reg - used_call - used_bare)
print(f"注册但技能层完全未提及的: {unbound or '无'}")
if bad:
    fail.append(f"幽灵工具引用: {bad}")

print()
print("=" * 50)
print("排查结论:", "全部通过 ✅" if not fail else f"发现问题: {fail}")
sys.exit(0 if not fail else 1)
