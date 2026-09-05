"""门禁塔新检查器测试（docs/ARCHITECTURE.md 九层塔，v0.7.0）。

运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest
from unittest import mock
import urllib.error

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


def _crossref_work(doi_tail: str, **fields) -> dict:
    """构造 Crossref works/{doi} 响应，字段可覆盖。"""
    msg = {"title": ["Some paper title"], "DOI": f"10.1234/{doi_tail}"}
    msg.update(fields)
    return {"status": "ok", "message": msg}


class TestCheckRetraction(unittest.TestCase):
    """L1 存在层：撤稿筛查。API 事实判 error；网络失败按 X 级纪律不拦门禁。"""

    REFS = (
        "# T\n\n正文。\n\n## References\n\n"
        "[1] Bad, A. (2020). A retracted study. Nature. https://doi.org/10.1234/retracted\n"
        "[2] Good, B. (2021). A clean study. Science. https://doi.org/10.1234/clean\n"
        "[3] Notice, C. (2019). Retraction notice: A retracted study. Nature. https://doi.org/10.1234/notice\n"
        "[4] Lost, D. (2020). An unreachable entry. J. https://doi.org/10.1234/lost\n"
    )

    def _mock_fetch(self, url, headers=None, retries=1):
        if "retracted" in url:
            return _crossref_work("retracted", **{"update-to": [{"DOI": "10.1234/retraction-notice", "type": "retraction"}]})
        if "clean" in url:
            return _crossref_work("clean")
        if "notice" in url:
            return _crossref_work("notice", title=["Retraction notice: A retracted study"])
        raise urllib.error.URLError("connection refused")

    def test_retracted_is_error(self):
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=self._mock_fetch):
            r = paper_tools.check_retraction(self.REFS)
        hit = [i for i in r["issues"] if i["type"] == "cited_retracted_work"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "error")
        self.assertIn("retraction-notice", hit[0]["detail"])
        self.assertFalse(r["ok"])

    def test_relation_is_retracted_by_signal(self):
        with mock.patch.object(paper_tools, "_fetch_json", return_value=_crossref_work("x", relation={"is-retracted-by": [{"DOI": "10.1/notice"}]})):
            probe = paper_tools._retraction_probe(doi="10.1234/x")
        self.assertEqual(probe["status"], "retracted")

    def test_clean_reference_passes(self):
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=self._mock_fetch):
            r = paper_tools.check_retraction(self.REFS)
        self.assertEqual(r["summary"]["retracted"], 1)
        self.assertEqual(r["summary"]["notice"], 1)
        self.assertTrue(all(i["type"] != "cited_retracted_work" or "第 2 条" not in i["detail"] for i in r["issues"]))

    def test_unverifiable_never_blocks(self):
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=self._mock_fetch):
            r = paper_tools.check_retraction(self.REFS)
        unver = [i for i in r["issues"] if i["type"] == "retraction_unverifiable"]
        self.assertEqual(len(unver), 1)
        self.assertEqual(unver[0]["severity"], "info")

    def test_title_fallback_flow(self):
        md = "# T\n\n## References\n\n[1] Deep Learning, I. (2021). A very unique paper on retraction screening. Nature.\n"

        def fake(url, headers=None, retries=1):
            if "query.title" in url:
                return {"message": {"items": [{"title": ["A very unique paper on retraction screening"], "DOI": "10.1234/matched"}]}}
            return _crossref_work("matched", **{"update-to": [{"DOI": "10.1234/ret", "type": "retraction"}]})

        with mock.patch.object(paper_tools, "_fetch_json", side_effect=fake):
            r = paper_tools.check_retraction(md)
        hit = [i for i in r["issues"] if i["type"] == "cited_retracted_work"]
        self.assertEqual(len(hit), 1)

    def test_empty_and_no_entries(self):
        self.assertTrue(paper_tools.check_retraction("")["ok"])
        self.assertEqual(paper_tools.check_retraction("# T\n\n没有文献段。")["checked"], 0)


class TestCheckClaimCitationFit(unittest.TestCase):
    """L2 契合层：强主张句与所引文献的词汇契合度（warning 级，诚实降级）。"""

    MD = (
        "# T\n\n正文一句铺垫。\n\n"
        "我们的方法显著优于基线方法（accuracy 提升明显）[1]。"
        "另一句无关内容，不包含强主张措辞，只是普通描述[2]。\n\n"
        "## References\n\n"
        "[1] Ref, A. (2021). Deep neural architectures for protein folding prediction. Nature. https://doi.org/10.1234/folding\n"
        "[2] Other, B. (2020). Something else entirely different. J. https://doi.org/10.1234/other\n"
    )

    def _fetch(self, url, headers=None, retries=1):
        if "folding" in url:
            return {"message": {"title": ["Deep neural architectures for protein folding prediction"], "abstract": "<p>We study protein structure prediction with transformers.</p>"}}
        if "other" in url:
            return {"message": {"title": ["Something else entirely different"]}}
        raise urllib.error.URLError("no network")

    def test_weak_fit_warns(self):
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=self._fetch):
            r = paper_tools.check_claim_citation_fit(self.MD)
        hit = [i for i in r["issues"] if i["type"] == "weak_citation_support"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "warning")
        self.assertEqual(r["summary"]["weak"], 1)

    def test_strong_fit_passes(self):
        md = (
            "# T\n\n"
            "本文的卷积模块显著提升了图像分类的准确率（image classification accuracy）[1]。\n\n"
            "## References\n\n[1] Ref, A. (2021). Image classification accuracy improvement with convolution. https://doi.org/10.1234/img\n"
        )
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=self._fetch):
            r = paper_tools.check_claim_citation_fit(md)
        self.assertEqual([i for i in r["issues"] if i["type"] == "weak_citation_support"], [])

    def test_unfetchable_source_skipped_honestly(self):
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=urllib.error.URLError("down")):
            r = paper_tools.check_claim_citation_fit(self.MD)
        self.assertEqual(r["summary"]["assessed"], 0)
        self.assertEqual(r["summary"]["unassessed"], 1)
        self.assertTrue(any(i["type"] == "fit_unassessed" for i in r["issues"]))

    def test_no_strong_claims_passes(self):
        md = "# T\n\n这是普通句子[1]。\n\n## References\n\n[1] A. (2020). B. C.\n"
        r = paper_tools.check_claim_citation_fit(md)
        self.assertTrue(r["ok"])


class TestCheckVersionMismatch(unittest.TestCase):
    """L2 契合层：arXiv 预印本已有正式发表版时提示更新（warning）。"""

    MD = (
        "# T\n\n## References\n\n"
        "[1] Vaswani, A. (2017). Attention is all you need. arXiv preprint arXiv:1706.03762.\n"
        "[2] Author, B. (2019). Only ever a preprint study here. arXiv:1901.00001.\n"
    )

    def _fetch(self, url, headers=None, retries=1):
        if "query.title" in url:
            title = "attention is all you need" if "Attention" in url or "attention" in url.lower() else ""
            items = [{"title": ["Attention is all you need"], "DOI": "10.1234/neurips2017", "type": "proceedings-article"}]
            return {"message": {"items": items}}
        raise urllib.error.URLError("down")

    def test_published_version_found_warns(self):
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=self._fetch):
            r = paper_tools.check_version_mismatch(self.MD)
        hit = [i for i in r["issues"] if i["type"] == "preprint_published_mismatch"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "warning")
        self.assertEqual(r["summary"]["publishedFound"], 1)

    def test_arxiv_self_hit_not_flagged(self):
        def fetch(url, headers=None, retries=1):
            if "query.title" in url:
                return {"message": {"items": [{"title": ["Only ever a preprint study here"], "DOI": "10.48550/arXiv.1901.00001"}]}}
            raise urllib.error.URLError("down")

        md = "# T\n\n## References\n\n[1] Author, B. (2019). Only ever a preprint study here. arXiv:1901.00001.\n"
        with mock.patch.object(paper_tools, "_fetch_json", side_effect=fetch):
            r = paper_tools.check_version_mismatch(md)
        self.assertEqual([i for i in r["issues"] if i["type"] == "preprint_published_mismatch"], [])
        self.assertEqual(r["summary"]["publishedFound"], 0)

    def test_non_arxiv_references_ignored(self):
        md = "# T\n\n## References\n\n[1] Plain, C. (2020). A normal journal article. J. of Tests.\n"
        r = paper_tools.check_version_mismatch(md)
        self.assertEqual(r["summary"]["arxivEntries"], 0)

    def test_no_arxiv_entries(self):
        self.assertTrue(paper_tools.check_version_mismatch("")["ok"])


if __name__ == "__main__":
    unittest.main()
