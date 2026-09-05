"""v1.30.0 三语描述接口 + 英文词表扩充 回归测试。

运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import paper_tools


class TestTrilingualDescriptions(unittest.TestCase):
    """description=英语主描述，description_zh=中文，description_ja=日语。"""

    def test_all_tools_have_en_and_ja(self):
        names = {t["name"] for t in paper_tools.TOOLS}
        self.assertEqual(set(paper_tools._TOOL_DESC_EN), names, "_TOOL_DESC_EN 必须覆盖全部工具")
        self.assertEqual(set(paper_tools._TOOL_DESC_JA), names, "_TOOL_DESC_JA 必须覆盖全部工具")

    def test_localization_applied_to_every_tool(self):
        for tool in paper_tools.TOOLS:
            self.assertIn("description_zh", tool, f"{tool['name']} 缺少 description_zh")
            self.assertIn("description_ja", tool, f"{tool['name']} 缺少 description_ja")
            self.assertNotEqual(tool["description"], tool["description_zh"], f"{tool['name']} 主描述未本地化为英语")

    def test_primary_description_is_english(self):
        # 英文主描述应基本由拉丁字符构成（允许少量例外如 浅析 引用）
        import re

        for tool in paper_tools.TOOLS:
            latin = len(re.findall(r"[A-Za-z]", tool["description"]))
            cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]", tool["description"]))
            self.assertGreater(latin, cjk * 3, f"{tool['name']} 的主描述不是以英文为主")

    def test_tools_list_names_unchanged(self):
        # 协议契约：三语化不得改变 tools/list 的工具名集合
        expected = {
            "render_template",
            "word_count",
            "check_structure",
            "generate_outline",
            "literature_checklist",
            "submission_checklist",
            "journal_matcher",
            "citation_verify",
            "lit_search",
            "journal_search_openalex",
            "verify_references",
            "check_style",
            "check_punctuation",
            "check_figures_tables",
            "check_terms",
            "check_duplicates",
            "check_references_format",
            "proofread",
            "check_intext_citations",
            "check_sections",
            "word_budget",
            "check_ai_signature",
            "check_tamper_traces",
            "check_numbers",
            "check_hedging",
            "check_stats",
            "audit_paper",
            "check_self_plagiarism",
            "audit_pdf",
            "format_citation",
            "check_abstract",
            "check_title",
            "audit_project",
                "next_actions",
                "gate_suite",
                "audit_delta",
"check_links",
                "check_vague_attribution",
                "check_placeholders",
                "check_references_completeness",
                "check_references_recency",
                "check_encoding",
                "check_ethics_statements",
                "check_retraction",
                "check_claim_citation_fit",
                "check_version_mismatch",
                "check_symbol_consistency",
                "check_abstract_promises",
        }
        self.assertEqual({t["name"] for t in paper_tools.TOOLS}, expected)


class TestEnLexiconExpansion(unittest.TestCase):
    """v1.30.0 英文 AI 模板短语扩充（Liang et al. 2024, arXiv:2403.07183）。"""

    def test_new_phrases_hit(self):
        md = (
            "# The Ever-Evolving Landscape of Research\n\n"
            "This study underscores the importance of timely feedback in education today.\n"
            "The multifaceted nature of learning requires a holistic approach from teachers.\n"
            "It represents a paradigm shift that may bridge the gap between theory practice.\n"
            "The tapestry of methods offers actionable insights and opens up new avenues.\n"
            "Researchers have long sought to navigate the complexities of classroom dynamics.\n"
            "Prior work highlights the need for longitudinal designs across varied contexts.\n"
            "Our findings underscore the need for careful interpretation of effect sizes.\n"
            "The intricate relationship between motivation and achievement merits attention.\n"
            "Seamless integration of technology remains a central challenge for schools now.\n"
            "Future studies should examine these cutting-edge techniques in greater depth.\n"
        )
        r = paper_tools.check_ai_signature(md)
        hits = " ".join(i["detail"] for i in r["issues"] if i["type"] == "template_phrase")
        for phrase in (
            "underscores the importance",
            "multifaceted nature",
            "holistic approach",
            "paradigm shift",
            "bridge the gap between",
            "actionable insights",
            "opens up new avenues",
        ):
            self.assertIn(phrase, hits, phrase)

    def test_new_transition_openers_counted(self):
        md = (
            "# T\n\n"
            "Ultimately the results confirm the hypothesis stated in the introduction section.\n"
            "Consequently future work should examine the limitations noted above in detail.\n"
            "Moreover additional experiments could strengthen the evidence presented here.\n"
            "Furthermore replication across sites would improve generalizability claims made.\n"
            "In essence the framework offers a practical path forward for practitioners now.\n"
            "Additionally the dataset will be released to support further research efforts soon.\n"
            "Finally we thank the reviewers for their constructive comments on earlier drafts.\n"
            "Notably this is among the first studies to examine this question in this context.\n"
        )
        r = paper_tools.check_ai_signature(md)
        metrics = r["metrics"]
        self.assertGreaterEqual(metrics["sentences"], 8)
        self.assertGreater(metrics["transitionRatio"], 0.25)


if __name__ == "__main__":
    unittest.main()
