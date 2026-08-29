# -*- coding: utf-8 -*-
"""Persona 评测器：对埋雷测试论文跑门禁套件，输出检测率矩阵与漏检清单。

可复现：同一批论文 + 同一 ground truth → 同一结果。用于发布前回归与能力盘点。
用法：python benchmarks/persona_eval/run_eval.py
联网核验（kind=citation）需要访问 Crossref；离线环境下自动标注 SKIPPED。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import paper_tools as pt  # noqa: E402


def collect_findings(verdict: dict) -> list:
    out = []
    for g in verdict.get("gates", []):
        for it in g.get("issues", []):
            out.append((g["gate"], it.get("type", ""), str(it.get("detail", ""))))
    return out


def matches(expect: dict, findings: list) -> bool:
    for gate, itype, detail in findings:
        if expect.get("gate") is not None and gate != expect["gate"]:
            continue
        if expect.get("type") is not None and itype != expect["type"]:
            continue
        kw = expect.get("detail_contains")
        if kw and kw.lower() not in detail.lower():
            continue
        return True
    return False


def main() -> None:
    gt = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
    total, hit, missed, skipped = 0, 0, [], []
    report = []

    for paper in gt["papers"]:
        md = (HERE / paper["file"]).read_text(encoding="utf-8")
        genre = paper.get("genre", "empirical")
        findings = collect_findings(json.loads(pt.gate_suite(md, genre=genre)))
        paper_hits = 0
        rows = []
        for exp in paper["expect"]:
            kind = exp.get("kind", "gate")
            total += 1
            if kind == "gate":
                ok = matches(exp, findings)
            elif kind == "citation":
                try:
                    grade = json.loads(pt.citation_verify(doi=exp["doi"])).get("grade")
                    ok = grade == exp.get("expect_grade", "C")
                except Exception as e:
                    rows.append(("SKIPPED", exp.get("label", ""), f"网络不可达: {e}"))
                    skipped.append((paper["file"], exp.get("label", "")))
                    continue
            elif kind == "ai_signature":
                sig = pt.check_ai_signature(md)
                if not isinstance(sig, dict):
                    sig = json.loads(sig)
                score = sig.get("score")
                ok = isinstance(score, int) and score >= exp.get("min_score", 60)
                rows.append(("PASS" if ok else "MISS", exp.get("label", f"AI 画像 {exp.get('min_score')}+"), f"实测 {score}"))
                if ok:
                    hit += 1
                    paper_hits += 1
                else:
                    missed.append((paper["file"], exp.get("label", "")))
                continue
            rows.append(("PASS" if ok else "MISS", exp.get("label", ""), f"{exp.get('gate')}/{exp.get('type')}"))
            if ok:
                hit += 1
                paper_hits += 1
            else:
                missed.append((paper["file"], exp.get("label", "")))
        report.append((paper["label"], paper_hits, len(paper["expect"]), rows))

    print("=" * 72)
    print("PERSONA EVAL — 埋雷检测率矩阵")
    print("=" * 72)
    for label, h, n, rows in report:
        print(f"\n【{label}】 {h}/{n}")
        for status, lab, extra in rows:
            mark = "✓" if status == "PASS" else ("~" if status == "SKIPPED" else "✗")
            print(f"  {mark} {status:<7} {lab}  ({extra})")

    print("\n" + "=" * 72)
    print(f"总计: {hit}/{total} 检出 ({hit * 100 // total if total else 0}%)")
    if missed:
        print("\n漏检清单（改进方向）:")
        for f, lab in missed:
            print(f"  ✗ {f}: {lab}")
    if skipped:
        print("\n跳过（离线）:")
        for f, lab in skipped:
            print(f"  ~ {f}: {lab}")


if __name__ == "__main__":
    main()
