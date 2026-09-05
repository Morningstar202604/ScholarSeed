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


if __name__ == "__main__":
    unittest.main()
