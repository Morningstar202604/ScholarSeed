"""PaperIR 文档中间表示测试（docs/ARCHITECTURE.md 门禁塔 L0 地基）。

运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import paper_ir
import paper_tools

SAMPLE = """---
title: Test Paper
---

# 面向交付质检的学术写作流水线研究

## 摘要

本研究提出一套确定性门禁塔模型，用于论文交付质检。

## 1. 引言

学术写作的瓶颈在交付环节。研究表明质量门禁有价值[1]。

```python
print("code block: TODO 应被置空，不产出句子")
```

## 2. 方法

设 λ 表示学习率，μ 表示动量系数。

## References

[1] Smith, J. (2021). A study. J. of Tests.
"""


class TestSharedHelpersMoved(unittest.TestCase):
    """共享辅助函数迁入 paper_ir 后，paper_tools 侧名称语义不变。"""

    def test_helpers_are_same_objects(self):
        for name in ("_line_starts", "_pos_to_line", "_blank_fences", "_count_cjk", "_split_sentences", "_extract_abstract"):
            self.assertIs(getattr(paper_tools, name), getattr(paper_ir, name), f"{name} 应为同一函数对象")

    def test_line_number_mapping_unchanged(self):
        text = "a\nbb\nccc"
        starts = paper_ir._line_starts(text)
        self.assertEqual(paper_ir._pos_to_line(0, starts), 1)
        self.assertEqual(paper_ir._pos_to_line(2, starts), 2)
        self.assertEqual(paper_ir._pos_to_line(5, starts), 3)

    def test_blank_fences_preserves_line_count(self):
        text = "前\n```py\nx=1\ny=2\n```\n后"
        blanked = paper_ir._blank_fences(text)
        self.assertEqual(blanked.count("\n"), text.count("\n"))
        self.assertNotIn("x=1", blanked)


class TestParsePaperIr(unittest.TestCase):
    def test_title_and_sections(self):
        ir = paper_ir.parse_paper_ir(SAMPLE)
        self.assertEqual(ir["title"], "面向交付质检的学术写作流水线研究")
        self.assertEqual(ir["title_line"], 5)
        titles = [s["title"] for s in ir["sections"]]
        self.assertIn("摘要", titles)
        self.assertIn("1. 引言", titles)
        self.assertIn("2. 方法", titles)
        self.assertEqual(ir["sections"][0]["level"], 1)

    def test_section_text_spans_cover_document(self):
        ir = paper_ir.parse_paper_ir(SAMPLE)
        intro = next(s for s in ir["sections"] if s["title"] == "1. 引言")
        self.assertIn("瓶颈在交付环节", intro["text"])
        self.assertGreater(intro["line"], 0)

    def test_abstract_extracted_with_line(self):
        ir = paper_ir.parse_paper_ir(SAMPLE)
        self.assertIn("门禁塔模型", ir["abstract"])
        self.assertEqual(ir["abstract_line"], 9)

    def test_yaml_frontmatter(self):
        ir = paper_ir.parse_paper_ir(SAMPLE)
        self.assertIn("title: Test Paper", ir["yaml"])

    def test_body_refs_split(self):
        ir = paper_ir.parse_paper_ir(SAMPLE)
        self.assertIn("引言", ir["body"])
        self.assertNotIn("Smith, J.", ir["body"])
        self.assertIn("Smith, J. (2021)", ir["refs"])
        self.assertGreater(ir["refs_start_line"], 0)

    def test_sentences_exclude_code_blocks_with_lines(self):
        ir = paper_ir.parse_paper_ir(SAMPLE)
        texts = [s for _, s in ir["sentences"]]
        self.assertTrue(any("瓶颈在交付环节" in s for s in texts))
        self.assertFalse(any("TODO" in s for s in texts), "围栏代码内容不得产出句子")

    def test_empty_input(self):
        ir = paper_ir.parse_paper_ir("")
        self.assertEqual(ir["title"], "")
        self.assertEqual(ir["sections"], [])
        self.assertEqual(ir["sentences"], [])

    def test_no_reference_heading(self):
        ir = paper_ir.parse_paper_ir("# T\n\n正文一句。")
        self.assertEqual(ir["refs"], "")
        self.assertEqual(ir["refs_start_line"], 0)

    def test_iter_sentences_lines_monotonic_and_accurate(self):
        lines = [ln for ln, _ in paper_ir.iter_sentences(SAMPLE)]
        self.assertEqual(lines, sorted(lines))
        sample_body = paper_ir.parse_paper_ir(SAMPLE)["body"]
        for ln, sent in paper_ir.iter_sentences(sample_body):
            source_line = sample_body.splitlines()[ln - 1]
            self.assertIn(sent.splitlines()[0][:12], source_line + "".join(sample_body.splitlines()[ln - 1 : ln]), f"句子行号定位失真: L{ln}")


if __name__ == "__main__":
    unittest.main()
