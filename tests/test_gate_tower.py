"""门禁塔新检查器测试（docs/ARCHITECTURE.md 九层塔，v0.7.0）。

运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import paper_tools

# 测试禁用磁盘缓存：避免真实运行留下的缓存条目污染 mock 断言
paper_tools.CACHE_TTL = 0


class TestCheckEncoding(unittest.TestCase):
    """L0 文件底座：编码损坏检出，合法重音文本零误报。"""

    def test_clean_text_passes(self):
        md = "# 标题\n\n正文 café naïve résumé 与中文混排，一切正常。\n"
        r = paper_tools.check_encoding(md)
        self.assertTrue(r["ok"])
        self.assertEqual(r["issues"], [])

    def test_replacement_char_is_error(self):
        r = paper_tools.check_encoding("# T\n\n数据损坏\uFFFD无法读取。\n")
        hit = [i for i in r["issues"] if i["type"] == "replacement_char"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "error")
        self.assertEqual(hit[0]["line"], 3)

    def test_cid_marker_is_error(self):
        r = paper_tools.check_encoding("抽取文本 (cid:123) 之后继续。")
        hit = [i for i in r["issues"] if i["type"] == "cid_extracted"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "error")
        self.assertIn("(cid:123)", hit[0]["detail"])

    def test_mojibake_detected(self):
        r = paper_tools.check_encoding("中文乱码样例：ä¸­æ–‡ä»¶ 系统损坏。")
        hit = [i for i in r["issues"] if i["type"] == "mojibake"]
        self.assertGreaterEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "warning")

    def test_control_char_and_midfile_bom(self):
        r = paper_tools.check_encoding("第一段\x01继续。第二段\ufeff开始。")
        types = {i["type"] for i in r["issues"]}
        self.assertIn("control_char", types)
        self.assertIn("bom_midfile", types)

    def test_line_numbers_accurate(self):
        md = "# T\n\n正文一行。\n\n坏行 (cid:55) 在第五行。\n"
        r = paper_tools.check_encoding(md)
        hit = [i for i in r["issues"] if i["type"] == "cid_extracted"][0]
        self.assertEqual(hit["line"], 5)

    def test_mcp_registration_roundtrip(self):
        r = paper_tools.check_encoding("")
        self.assertTrue(r["ok"])

    def test_gate_suite_includes_encoding(self):
        md = "# T\n\n正文 (cid:9) 残留。\n"
        out = json.loads(paper_tools.gate_suite(md, gates="encoding"))
        self.assertFalse(out["pass"])
        gates = {g["gate"] for g in out["gates"]}
        self.assertEqual(gates, {"encoding"})


class TestCheckEthicsStatements(unittest.TestCase):
    """P 合法前提：声明存在性检查，涉人研究缺伦理声明为 error。"""

    EMPIRICAL_DIRTY = (
        "# 研究\n\n## 1. 引言\n\n我们对 250 名参与者的数据进行了分析。\n\n"
        "## 2. 方法\n\n采用问卷调查。\n\n## 3. 结果\n\n结果显著。\n\n## References\n\n[1] A. (2020). B. J.\n"
    )
    EMPIRICAL_CLEAN = (
        "# 研究\n\n## 摘要\n\n本研究使用 AI 辅助完成初稿整理，已如实披露。\n\n"
        "## 1. 引言\n\n我们对 250 名参与者的数据进行了分析。\n\n"
        "## 2. 方法\n\n本研究获伦理委员会批准，参与者均签署知情同意书；无利益冲突；数据可用性声明见附录。\n\n"
        "## References\n\n[1] A. (2020). B. J.\n"
    )

    def test_human_subjects_without_ethics_is_error(self):
        r = paper_tools.check_ethics_statements(self.EMPIRICAL_DIRTY, genre="empirical")
        hit = [i for i in r["issues"] if i["type"] == "ethics_missing_human_subjects"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "error")
        self.assertTrue(r["summary"]["humanSubjectsDetected"])

    def test_complete_statements_pass(self):
        r = paper_tools.check_ethics_statements(self.EMPIRICAL_CLEAN, genre="empirical")
        self.assertTrue(r["ok"], r["issues"])
        for key in ("ethics_approval", "conflict_of_interest", "ai_disclosure", "data_availability"):
            self.assertIn(key, r["summary"]["found"])

    def test_ai_nonuse_declaration_counts(self):
        md = "# 论文\n\n正文内容。\n\n## 声明\n\n本文未使用任何人工智能工具。无利益冲突。\n"
        r = paper_tools.check_ethics_statements(md, genre="survey")
        self.assertIn("ai_disclosure", r["summary"]["found"])

    def test_non_empirical_without_subjects_skips_ethics_and_data(self):
        md = "# 论文\n\n纯理论论证文本。\n"
        r = paper_tools.check_ethics_statements(md, genre="argumentative")
        types = {i["type"] for i in r["issues"]}
        self.assertNotIn("ethics_missing", types)
        self.assertNotIn("data_availability_missing", types)
        self.assertEqual(types, {"coi_missing", "ai_disclosure_missing"})

    def test_gate_suite_includes_ethics(self):
        out = json.loads(paper_tools.gate_suite(self.EMPIRICAL_DIRTY, gates="ethics", genre="empirical"))
        self.assertFalse(out["pass"])
        self.assertEqual(out["totalErrors"], 1)


if __name__ == "__main__":
    unittest.main()
