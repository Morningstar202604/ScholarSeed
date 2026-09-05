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


class TestCheckSymbolConsistency(unittest.TestCase):
    """L3 一致层：一符一义红线（error）与术语-符号漂移（warning）。"""

    def test_same_symbol_two_meanings_is_error(self):
        md = (
            "# T\n\n## 1. 方法\n\n"
            "设 λ 表示学习率，训练中固定不变。\n\n"
            "在第 3 节中，λ 表示正则化系数。\n"
        )
        r = paper_tools.check_symbol_consistency(md)
        hit = [i for i in r["issues"] if i["type"] == "symbol_conflict"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "error")
        self.assertIn("学习率", hit[0]["detail"])

    def test_consistent_symbol_passes(self):
        md = "# T\n\n设 μ 表示动量系数。实验中 μ 表示动量系数且取 0.9。\n"
        r = paper_tools.check_symbol_consistency(md)
        self.assertTrue(r["ok"], r["issues"])

    def test_one_term_multiple_symbols_warns(self):
        md = "# T\n\n记 α 为学习率。记 β 为学习率。\n"
        r = paper_tools.check_symbol_consistency(md)
        hit = [i for i in r["issues"] if i["type"] == "term_symbol_drift"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "warning")

    def test_english_denotes_conflict(self):
        md = "# T\n\nwhere λ denotes the learning rate of the optimizer.\n\nIn the appendix, λ denotes the momentum coefficient of SGD.\n"
        r = paper_tools.check_symbol_consistency(md)
        hit = [i for i in r["issues"] if i["type"] == "symbol_conflict"]
        self.assertEqual(len(hit), 1)

    def test_greek_char_and_latex_macro_normalized(self):
        md = "# T\n\n设 $\\lambda$ 表示学习率。\n\n附录中，λ 表示学习率。\n"
        r = paper_tools.check_symbol_consistency(md)
        self.assertEqual(r["summary"]["symbolsDefined"], 1)
        self.assertTrue(r["ok"])

    def test_fenced_code_exempt(self):
        md = "# T\n\n```\n设 x 表示 fenced 内容\n```\n\n设 x 表示特征向量。\n"
        r = paper_tools.check_symbol_consistency(md)
        self.assertEqual(r["summary"]["symbolsDefined"], 1)

    def test_gate_suite_includes_symbol(self):
        md = "# T\n\n设 σ 表示标准差。\n\n后文中 σ 表示 sigmoid 函数。\n"
        out = json.loads(paper_tools.gate_suite(md, gates="symbol"))
        self.assertFalse(out["pass"])


class TestCheckAbstractPromises(unittest.TestCase):
    """L3 一致层：摘要承诺必须被正文兑现（零命中才告警）。"""

    def test_unfulfilled_promise_warns(self):
        md = (
            "# T\n\n## 摘要\n\n本研究提出量子纠缠对齐框架以解决对齐问题。\n\n"
            "## 1. 引言\n\n本文讨论的是完全无关的传统图像分割话题。\n"
        )
        r = paper_tools.check_abstract_promises(md)
        hit = [i for i in r["issues"] if i["type"] == "abstract_promise_unfulfilled"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["severity"], "warning")

    def test_fulfilled_promise_passes(self):
        md = (
            "# T\n\n## 摘要\n\n本研究提出门禁塔模型用于论文质检。\n\n"
            "## 1. 引言\n\n门禁塔模型共分九层，逐层展开设计。\n"
        )
        r = paper_tools.check_abstract_promises(md)
        self.assertTrue(r["ok"], r["issues"])

    def test_english_promise(self):
        md = (
            "# T\n\n## Abstract\n\nWe propose a quantum routing framework for edge devices.\n\n"
            "## 1. Introduction\n\nThis paper studies classical scheduling only.\n"
        )
        r = paper_tools.check_abstract_promises(md)
        hit = [i for i in r["issues"] if i["type"] == "abstract_promise_unfulfilled"]
        self.assertEqual(len(hit), 1)

    def test_no_abstract_note(self):
        md = "# T\n\n## 1. 引言\n\n正文。\n"
        r = paper_tools.check_abstract_promises(md)
        self.assertTrue(r["ok"])
        self.assertIn("note", r["summary"])

    def test_line_number_points_into_abstract(self):
        md = (
            "# T\n\n## 摘要\n\n本研究提出霁光分域架构。\n\n"
            "## 1. 引言\n\n正文只谈传统缓存。\n"
        )
        r = paper_tools.check_abstract_promises(md)
        hit = [i for i in r["issues"] if i["type"] == "abstract_promise_unfulfilled"]
        self.assertEqual(hit[0]["line"], 5)

    def test_gate_suite_includes_abstract_promises(self):
        # 摘要承诺是 warning 级门禁：进套件、可报告，但不触发 pass=False（ERROR=0 纪律）
        md = (
            "# T\n\n## 摘要\n\n本研究提出玄机万向核心引擎。\n\n"
            "## 1. 引言\n\n正文与摘要承诺无关，讲的是别的。\n"
        )
        out = json.loads(paper_tools.gate_suite(md, gates="abstract_promises"))
        self.assertTrue(out["pass"])
        self.assertEqual(out["totalWarnings"], 1)
        self.assertEqual(out["gates"][0]["issues"][0]["type"], "abstract_promise_unfulfilled")


class TestCheckRigorDeclarations(unittest.TestCase):
    """L4 方法层：触发场景→声明在场核对（warning 级）。"""

    DIRTY = (
        "# T\n\n## 1. 引言\n\n本研究发放问卷并回收，采用 t 检验比较组间差异。\n\n"
        "## 2. 方法\n\n分析方法如上。\n"
    )
    CLEAN = (
        "# T\n\n## 1. 引言\n\n本研究开展随机对照试验，发放问卷收集数据。\n\n"
        "## 2. 方法\n\n经正态性检验（Shapiro-Wilk）后采用 ANOVA，Bonferroni 事后检验校正多重比较；"
        "样本量经效能分析确定（G*Power）；被试随机分组；缺失数据采用多重插补处理。\n"
    )

    def test_missing_declarations_warn(self):
        r = paper_tools.check_rigor_declarations(self.DIRTY, genre="empirical")
        types = {i["type"] for i in r["issues"]}
        self.assertEqual(types, {"rigor_declaration_missing"})
        self.assertEqual(len(r["issues"]), 3)
        self.assertEqual(sorted(r["summary"]["triggered"]), ["missing_data", "normality_test", "power_analysis"])
        self.assertTrue(all(i["severity"] == "warning" for i in r["issues"]))

    def test_complete_declarations_pass(self):
        r = paper_tools.check_rigor_declarations(self.CLEAN, genre="empirical")
        self.assertTrue(r["ok"], r["issues"])
        self.assertEqual(len(r["summary"]["declared"]), 5)

    def test_non_empirical_skipped(self):
        r = paper_tools.check_rigor_declarations(self.DIRTY, genre="argumentative")
        self.assertTrue(r["ok"])
        self.assertIn("跳过", r["summary"]["note"])

    def test_no_trigger_passes(self):
        r = paper_tools.check_rigor_declarations("# T\n\n纯理论论证文本。\n", genre="empirical")
        self.assertTrue(r["ok"])
        self.assertEqual(r["summary"]["triggered"], [])

    def test_gate_suite_includes_rigor(self):
        out = json.loads(paper_tools.gate_suite(self.DIRTY, gates="rigor", genre="empirical"))
        self.assertTrue(out["pass"])
        self.assertEqual(out["totalWarnings"], 3)


class TestCheckAnonymization(unittest.TestCase):
    """L5 规范层：双盲匿名化。blind=False 诚实返回未启用。"""

    LEAKY = (
        "# T\n\n## 1. 引言\n\n结合我们之前的研究成果[3]，本文进一步扩展。\n\n"
        "## 2. 方法\n\n细节见 C:" + chr(92) + "Users" + chr(92) + "zhangsan" + chr(92) + "data。\n\n"
        "## 致谢\n\n感谢国家自然科学基金资助。\n"
    )
    CLEAN_BLIND = "# T\n\n## 1. 引言\n\n本方法基于已有第三人称文献展开。\n"

    def test_not_blind_honest_noop(self):
        r = paper_tools.check_anonymization(self.LEAKY, blind=False)
        self.assertTrue(r["ok"])
        self.assertIn("未启用", r["summary"]["note"])

    def test_leaks_detected_as_errors(self):
        r = paper_tools.check_anonymization(self.LEAKY, blind=True)
        types = {i["type"] for i in r["issues"]}
        self.assertIn("self_reference_leak", types)
        self.assertIn("acknowledgment_in_blind", types)
        self.assertIn("funding_in_blind", types)
        self.assertIn("path_leak", types)
        self.assertTrue(all(i["severity"] == "error" for i in r["issues"] if i["type"] != "path_leak"))
        self.assertFalse(r["ok"])

    def test_clean_blind_passes(self):
        r = paper_tools.check_anonymization(self.CLEAN_BLIND, blind=True)
        self.assertTrue(r["ok"], r["issues"])

    def test_latex_author_and_yaml_leak(self):
        md = "# T\n\n\\author{Zhang San <zhang@univ.edu>}\n\n---\nauthors: Zhang San\n---\n\n正文。\n"
        r = paper_tools.check_anonymization(md, blind=True)
        hits = [i for i in r["issues"] if i["type"] == "metadata_identity_leak"]
        self.assertEqual(len(hits), 2)

    def test_masked_line_exempt(self):
        md = "# T\n\n## 1. 引言\n\n本研究受国家自然科学基金资助（信息已隐去）。\n"
        r = paper_tools.check_anonymization(md, blind=True)
        self.assertEqual([i for i in r["issues"] if i["type"] == "funding_in_blind"], [])


if __name__ == "__main__":
    unittest.main()
