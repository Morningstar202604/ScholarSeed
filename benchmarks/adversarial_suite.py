#!/usr/bin/env python3
"""RAID 风格对抗回归套件（stdlib-only 子集）。

依据 Dugan et al., "RAID: A Shared Benchmark for Robust Evaluation of
Machine-Generated Text Detectors" (ACL 2024) 的黑盒攻击分类，对本仓库
check_tamper_traces / check_ai_signature 做**行为契约**级回归：

契约 A（留痕攻击必被抓）：homoglyph / zero_width_space / whitespace 三类
    攻击会在文本中留下客观字符级痕迹，check_tamper_traces 必须全部检出；
契约 B（无痕变换不误报）：article_deletion 类变换不留客观痕迹，
    tamper 检查必须保持静默（防篡改取证不冤枉正常编辑）；
契约 C（诚实边界）：paraphrase / synonym 等需要语言模型的攻击不在本套件
    范围内——表层统计启发式对它们天然盲，见 docs/CAPABILITY-ASSESSMENT.md。

用法：
    python benchmarks/adversarial_suite.py [textfile]
退出码：0 全部契约通过；1 有契约失败。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import paper_tools

# RAID homoglyph 攻击同源字符集（Wolff 2020）
_HOMOGLYPH_MAP = str.maketrans(
    {
        "a": "а",
        "A": "А",
        "B": "В",
        "c": "с",
        "e": "е",
        "E": "Е",
        "o": "о",
        "O": "О",
        "p": "р",
        "P": "Р",
        "x": "х",
        "X": "Х",
        "y": "у",
        "H": "Н",
        "K": "К",
        "M": "М",
        "T": "Т",
    }
)

DEFAULT_TEXT = (
    "# Attention Mechanisms Revisited\n\n"
    "Consider what attention actually computes in practice across models.\n"
    "A weighted sum forms the core of every transformer variant we tested.\n"
    "The entire architecture rests on learned weights plus enough hardware.\n"
    "Reviewers often ask why our variant works better than the baseline does.\n"
)


def attack_homoglyph(text: str) -> str:
    """RAID homoglyph：拉丁字母 → 西里尔同形字（肉眼不可辨）。"""
    return text.translate(_HOMOGLYPH_MAP)


def attack_zero_width_space(text: str) -> str:
    """RAID zero-width space：词间插入 U+200B。"""
    return text.replace(" ", "\u200b ", 40)


def attack_whitespace(text: str) -> str:
    """RAID whitespace：行内插入多余空白串。"""
    out = []
    for line in text.split("\n"):
        if line and not line.startswith("#"):
            line = line[: len(line) // 2] + "   " + line[len(line) // 2 :]
        out.append(line)
    return "\n".join(out)


def attack_article_deletion(text: str) -> str:
    """RAID article deletion：删英文冠词——语义受损但不留字符痕迹。"""
    import re

    return re.sub(r"\b(a|an|the)\s+", "", text, flags=re.I)


TRACE_ATTACKS = {
    "homoglyph": attack_homoglyph,
    "zero_width_space": attack_zero_width_space,
    "whitespace": attack_whitespace,
}
SILENT_ATTACKS = {"article_deletion": attack_article_deletion}


def _types(result: dict) -> set:
    return {i["type"] for i in result.get("issues", [])}


def run(base_text: str) -> list:
    failures = []
    base = paper_tools.check_tamper_traces(base_text)
    if not base["ok"]:
        failures.append(f"baseline 文本被误报: {_types(base)}")

    for name, fn in TRACE_ATTACKS.items():
        result = paper_tools.check_tamper_traces(fn(base_text))
        caught = _types(result)
        expect = {
            "homoglyph": ("homoglyph_injection", "warning"),
            "zero_width_space": ("zero_width_chars", "warning"),
            "whitespace": ("whitespace_anomaly", "info"),
        }[name]
        want_type, want_sev = expect
        hit = next((i for i in result.get("issues", []) if i["type"] == want_type), None)
        if hit is not None and hit["severity"] == want_sev:
            print(f"[PASS] 契约A {name}: 检出 {want_type}({want_sev})")
        else:
            failures.append(f"契约A {name}: 期望 {want_type}({want_sev})，实得 {sorted(caught)}")

    for name, fn in SILENT_ATTACKS.items():
        result = paper_tools.check_tamper_traces(fn(base_text))
        warnings = [i for i in result.get("issues", []) if i["severity"] == "warning"]
        if not warnings:
            print(f"[PASS] 契约B {name}: 无 warning 级误报")
        else:
            failures.append(f"契约B {name}: 不应触发 warning，实得 {[i['type'] for i in warnings]}")

    sig = paper_tools.check_ai_signature(base_text)
    if "score" in sig:
        print(f"[INFO] 契约C 边界声明: ai-signature 对基线文本评分 {sig['score']}（表层统计启发式，对 paraphrase/synonym 类攻击天然盲，属已知边界而非缺陷）")
    return failures


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    if path:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    else:
        text = DEFAULT_TEXT
    failures = run(text)
    if failures:
        print("\n== 对抗回归失败 ==")
        for f_ in failures:
            print(" -", f_)
        return 1
    print(f"\n== 对抗回归通过（{len(TRACE_ATTACKS)} 留痕攻击全检出 / {len(SILENT_ATTACKS)} 无痕变换零误报）==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
