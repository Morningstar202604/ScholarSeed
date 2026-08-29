"""check_tamper_traces 防篡改痕迹取证 + audit_paper 统计诚信去重 回归测试。

v1.29.0 新增。运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import cli
import paper_tools


class TestTamperTraces(unittest.TestCase):
    """零宽字符 / 同形字 / 异常空白 三类客观痕迹的检测与豁免。"""

    def test_zero_width_detected_with_lines(self):
        md = "# Title\n\nThe quick\u200b brown fox jumps over a lazy dog again today.\n" + "Filler sentence number two with enough words to pass along.\n"
        r = paper_tools.check_tamper_traces(md)
        self.assertFalse(r["ok"])
        types = {i["type"] for i in r["issues"]}
        self.assertIn("zero_width_chars", types)
        zw = next(i for i in r["issues"] if i["type"] == "zero_width_chars")
        self.assertEqual(zw["severity"], "warning")
        self.assertEqual(r["summary"]["zeroWidth"], 1)

    def test_all_invisible_char_classes(self):
        for ch in ("\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"):
            md = "# T\n\nWord " + ch + " joined here in a plain sentence of some length.\n"
            r = paper_tools.check_tamper_traces(md)
            self.assertFalse(r["ok"], f"{ch!r} 应被检出")
            self.assertGreaterEqual(r["summary"]["zeroWidth"], 1)

    def test_homoglyph_embedded_in_latin_word(self):
        # а(西里尔) 混入拉丁单词 approach；о(西里尔) 混入 methods
        md = "# Study\n\nThis аpproach uses novel methоds for analysis of data.\nMore sentences follow to give the document reasonable body text.\n"
        r = paper_tools.check_tamper_traces(md)
        self.assertFalse(r["ok"])
        hg = next(i for i in r["issues"] if i["type"] == "homoglyph_injection")
        self.assertEqual(hg["severity"], "warning")
        self.assertIn("аpproach", hg["detail"])
        self.assertGreaterEqual(r["summary"]["homoglyph"], 2)

    def test_cyrillic_paragraph_exempt(self):
        # 整段俄文属正常文字，不是同形字注入
        md = "# Заголовок\n\nТолстой написал роман про войну и мир в девятнадцатом веке давно.\n" * 3
        r = paper_tools.check_tamper_traces(md)
        self.assertTrue(r["ok"])
        self.assertEqual(r["summary"]["homoglyph"], 0)

    def test_full_text_homoglyph_translation_caught(self):
        # RAID homoglyph 攻击（θ=100% 字符级替换）：非拉丁占比会很高，
        # 回归——不得因占比门控放行（v1.29.0 设计修正的固化用例）
        table = str.maketrans({"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х", "y": "у"})
        md = "# Study\n\nWe compare the proposed method across datasets today.\n" * 3
        attacked = md.translate(table)
        r = paper_tools.check_tamper_traces(attacked)
        self.assertFalse(r["ok"], "全文级同形字替换必须被检出")
        self.assertIn("homoglyph_injection", {i["type"] for i in r["issues"]})

    def test_whitespace_run_flagged_indent_exempt(self):
        md = "# T\n\nResult   triple spaces inside this line should be flagged now.\n\n    indented = code like line is exempt here\n"
        r = paper_tools.check_tamper_traces(md)
        ws = [i for i in r["issues"] if i["type"] == "whitespace_anomaly"]
        self.assertEqual(len(ws), 1)
        self.assertEqual(ws[0]["severity"], "info")

    def test_fenced_code_block_exempt(self):
        md = "# T\n\n```\nx = 1\u200b  # zero width inside code\n```\n\nPlain closing sentence with ordinary words and length ok.\n"
        r = paper_tools.check_tamper_traces(md)
        self.assertTrue(r["ok"])

    def test_references_section_scanned_or_ignored_consistently(self):
        # 空输入安全返回
        self.assertTrue(paper_tools.check_tamper_traces("")["ok"])
        self.assertTrue(paper_tools.check_tamper_traces("   \n ")["ok"])

    def test_clean_text_passes(self):
        md = (
            "# What We Actually Learned Debugging Our Data Pipeline\n\n"
            "The pipeline broke on a Tuesday. Not metaphorically - it failed at 2am because someone had hardcoded a timezone offset years ago.\n"
            "We spent two days chasing it. The fix was one line. The lesson was not that simple though.\n"
        )
        r = paper_tools.check_tamper_traces(md)
        self.assertTrue(r["ok"])
        self.assertEqual(r["issues"], [])

    def test_mcp_tool_registered_and_dispatched(self):
        names = [t["name"] for t in paper_tools.TOOLS]
        self.assertIn("check_tamper_traces", names)
        result = call_tool("check_tamper_traces", {"markdown": "Clean plain text only, nothing hidden inside this short note."})
        self.assertIn("ok", result)


class TestAuditPaperStatsDedup(unittest.TestCase):
    """v1.28.x 回归：empirical 体裁下统计诚信节重复渲染且严重度双倍计入。"""

    PAPER = (
        "# 论文标题\n\n"
        "## Abstract\n本文研究检测方法，实验表明效果显著 (p=0.000)。\n"
        "## Introduction\n首先提出问题。其次综述现状。最后给出贡献。\n"
        "## Methods\n采用问卷调查法收集数据并进行分析处理得到结果。\n"
        "显然该方法完全有效。\n"
        "## Results\n数据显示准确率提升了百分之五十，p=0.000。\n"
        "## Discussion\n综上所述，本研究具有重要意义。\n"
        "## References\n[1] 张三. 某研究[J]. 某学报, 2023.\n"
    )

    def _audit_json(self):
        return json.loads(paper_tools.audit_paper(self.PAPER, genre="empirical", fmt="json"))

    def test_stats_section_appears_exactly_once(self):
        names = [s["name"] for s in self._audit_json()["sections"]]
        self.assertEqual(names.count("统计诚信"), 1)

    def test_severity_totals_not_double_counted(self):
        data = self._audit_json()
        sections = data["sections"]
        expect_e = sum(1 for s in sections for i in s["issues"] if i["severity"] == "error")
        expect_w = sum(1 for s in sections for i in s["issues"] if i["severity"] == "warning")
        expect_i = sum(1 for s in sections for i in s["issues"] if i["severity"] == "info")
        self.assertEqual(data["summary"]["errors"], expect_e)
        self.assertEqual(data["summary"]["warnings"], expect_w)
        self.assertEqual(data["summary"]["infos"], expect_i)

    def test_markdown_report_renders_stats_once(self):
        report = paper_tools.audit_paper(self.PAPER, genre="empirical")
        self.assertEqual(report.count("## 统计诚信"), 1)

    def test_tamper_section_present(self):
        names = [s["name"] for s in self._audit_json()["sections"]]
        self.assertIn("防篡改痕迹", names)


class TestZhTemplateLexiconExpanded(unittest.TestCase):
    """v1.29.0 中文模板短语词表扩充（证据扩展，评分权重不变）。"""

    def test_new_phrases_hit(self):
        md = (
            "# 标题\n\n"
            "众所周知，该领域发展迅速。毋庸置疑，方法有效。取得了显著成果。\n"
            "得到了广泛应用。具有广阔的应用前景。为后续研究提供了参考。\n"
            "随着科技的不断发展，问题日益突出。研究者提出了新框架并验证了假设。\n"
            "实验结果表明性能优于基线方法，在多个数据集上均有提升表现。\n"
        )
        r = paper_tools.check_ai_signature(md)
        hits = " ".join(i["detail"] for i in r["issues"] if i["type"] == "template_phrase")
        for phrase in ("众所周知", "毋庸置疑", "取得了显著成果", "具有广阔的应用前景"):
            self.assertIn(phrase, hits)

    def test_cli_checker_registered(self):
        self.assertIn("tamper", cli.CHECKERS)


def call_tool(name: str, arguments: dict) -> dict:
    import io
    from unittest import mock

    request = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    with mock.patch("sys.stdin", io.StringIO(request + "\n")), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
        paper_tools.main()
    out.seek(0)
    response = json.loads(out.read().strip())
    return json.loads(response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
