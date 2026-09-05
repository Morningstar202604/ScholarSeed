"""paper-tools MCP Server 单元测试。

运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import io
import json
import os
import re
import shutil
import sys
import unittest
import urllib.error
import uuid
from typing import ClassVar
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import cli
import paper_tools

# 测试禁用磁盘缓存：避免真实运行留下的缓存条目污染 mock 断言
paper_tools.CACHE_TTL = 0


def _rpc(payload: str) -> dict:
    """向服务器发送一条 JSON-RPC 请求，返回响应 dict。"""
    with mock.patch("sys.stdin", io.StringIO(payload + "\n")), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
        paper_tools.main()
    out.seek(0)
    return json.loads(out.read().strip())


def call_tool(name: str, arguments: dict) -> dict:
    """调用工具，返回 result.content[0].text 的解析结果。"""
    request = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    response = _rpc(request)
    if "error" in response:
        return response
    text = response["result"]["content"][0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


class TestRenderTemplate(unittest.TestCase):
    def test_survey_genre(self):
        result = call_tool("render_template", {"genre": "survey"})
        self.assertIn("## 1. 引言", result["text"])
        self.assertIn("## 参考文献", result["text"])

    def test_empirical_genre(self):
        result = call_tool("render_template", {"genre": "empirical"})
        self.assertIn("## 2. 方法", result["text"])

    def test_unknown_genre_falls_back_to_survey(self):
        # 未知体裁回退到综述模板，不报错
        result = call_tool("render_template", {"genre": "nope"})
        self.assertIn("## 1. 引言", result["text"])

    def test_missing_genre_uses_default(self):
        result = call_tool("render_template", {})
        self.assertIn("## 1. 引言", result["text"])

    def test_thesis_genre(self):
        result = call_tool("render_template", {"genre": "thesis"})
        self.assertIn("## 第 1 章 绪论", result["text"])
        self.assertIn("## 第 6 章 总结与展望", result["text"])

    def test_journal_plan_appended_when_specified(self):
        # 指定顶刊概念型期刊类型时，模板应附带目标篇幅规划
        result = call_tool("render_template", {"genre": "survey", "journal": "top_conceptual"})
        self.assertIn("## 1. 引言", result["text"])
        self.assertIn("目标篇幅", result["text"])
        self.assertIn("8000-10000 词", result["text"])

    def test_journal_default_no_plan(self):
        # 未指定期刊类型时保持原行为，不附加篇幅规划
        result = call_tool("render_template", {"genre": "survey"})
        self.assertNotIn("目标篇幅", result["text"])

    def test_unknown_journal_returns_hint(self):
        result = call_tool("render_template", {"genre": "survey", "journal": "nope"})
        self.assertIn("未知期刊类型", result["text"])


class TestWordCount(unittest.TestCase):
    def test_counts(self):
        result = call_tool("word_count", {"markdown": "# 标题\n\n人工智能 Artificial Intelligence 2024。\n\n```\ncode block\n```\n"})
        self.assertGreater(result["chars"], 0)
        self.assertGreater(result["words"], 0)
        self.assertEqual(result["code_blocks"], 1)

    def test_empty(self):
        result = call_tool("word_count", {"markdown": ""})
        self.assertEqual(result["chars"], 0)
        self.assertEqual(result["words"], 0)


class TestCheckStructure(unittest.TestCase):
    def test_continuous_headings(self):
        result = call_tool("check_structure", {"markdown": "# A\n## B\n### C\n"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])

    def test_skipped_level(self):
        result = call_tool("check_structure", {"markdown": "# A\n### C\n"})
        self.assertFalse(result["ok"])
        self.assertTrue(any(i.get("type") == "skipped_level" for i in result["issues"]))

    def test_no_headings(self):
        result = call_tool("check_structure", {"markdown": "plain text\n"})
        self.assertFalse(result["ok"])
        self.assertTrue(any(i.get("type") == "no_headings" for i in result["issues"]))

    def test_headings_inside_code_fence_ignored(self):
        # 围栏代码块内的 "# comment" 是代码注释，不是标题，不应误报
        md = "# 真标题\n\n```python\n# 这是注释不是标题\nx = 1\n```\n"
        result = call_tool("check_structure", {"markdown": md})
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(len(result["headings"]), 1)


class TestGenerateOutline(unittest.TestCase):
    def test_empirical_outline_contains_picot_and_sections(self):
        result = call_tool("generate_outline", {"topic": "大语言模型辅助教学", "genre": "empirical"})
        self.assertIn("实证论文大纲", result["text"])
        self.assertIn("研究问题（PICOT 四要素）", result["text"])
        self.assertIn("## 3. 方法", result["text"])
        self.assertIn("## 4. 结果", result["text"])

    def test_survey_outline(self):
        result = call_tool("generate_outline", {"topic": "多模态大模型", "genre": "survey"})
        self.assertIn("综述大纲", result["text"])
        self.assertIn("## 7. 结论", result["text"])

    def test_default_genre_is_empirical(self):
        result = call_tool("generate_outline", {"topic": "某研究问题"})
        self.assertIn("实证论文大纲", result["text"])

    def test_thesis_outline(self):
        result = call_tool("generate_outline", {"topic": "某学位课题", "genre": "thesis"})
        self.assertIn("学位论文大纲", result["text"])
        self.assertIn("## 第 1 章 绪论", result["text"])


class TestLiteratureChecklist(unittest.TestCase):
    SAMPLE = """# 论文

正文内容。

## References

- Barney, J. (1991). Firm resources and sustained competitive advantage. Journal of Management, 17(1), 99-120.
- Acikgoz, Y. (2020). Justice perceptions of artificial intelligence in selection. IJSA, 28(4), 399-416.
"""

    def test_counts_and_status_placeholders(self):
        result = call_tool("literature_checklist", {"markdown": self.SAMPLE})
        self.assertIn("共识别到 2 条参考文献", result["text"])
        self.assertIn("A/B/C", result["text"])
        self.assertIn("铁律提醒", result["text"])
        self.assertIn("严禁伪造或美化参考文献", result["text"])

    def test_no_references_found(self):
        result = call_tool("literature_checklist", {"markdown": "# 只有正文\n没有参考文献\n"})
        self.assertIn("未在文本中识别到", result["text"])

    def test_empty_input(self):
        result = call_tool("literature_checklist", {"markdown": ""})
        self.assertIn("输入为空", result["text"])

    def test_pipe_in_entry_is_escaped(self):
        # 条目含竖线时必须转义，否则 Markdown 表格被破坏
        md = "# 论文\n\n## References\n\n- Smith, J. (2020). Pipes | in | title. Journal of Tests, 1(1), 1-2.\n"
        result = call_tool("literature_checklist", {"markdown": md})
        self.assertIn("\\|", result["text"])
        table_lines = [ln for ln in result["text"].splitlines() if ln.startswith("| ") and "Smith" in ln]
        self.assertEqual(len(table_lines), 1)
        # 按未转义的竖线切分：5 列表格 + 首尾空串 = 7 段
        cells = re.split(r"(?<!\\)\|", table_lines[0])
        self.assertEqual(len(cells), 7)


class TestSubmissionChecklist(unittest.TestCase):
    def test_core_items_present(self):
        result = call_tool("submission_checklist", {"journal": "Human Resource Management Review", "topic": "TCDR"})
        self.assertIn("投稿前检查清单", result["text"])
        self.assertIn("一稿多投红线", result["text"])
        self.assertIn("ICMJE", result["text"])
        self.assertIn("Cover Letter", result["text"])
        self.assertIn("AI 使用披露", result["text"])
        self.assertIn("Human Resource Management Review", result["text"])

    def test_defaults_when_empty(self):
        result = call_tool("submission_checklist", {})
        self.assertIn("（待定目标期刊）", result["text"])


class TestJournalMatcher(unittest.TestCase):
    def test_conceptual_talent_ai_ranks_hrmr_high(self):
        result = call_tool("journal_matcher", {"topic": "talent-centric digital recruitment and algorithmic HRM", "paper_type": "conceptual"})
        self.assertIn("Human Resource Management Review", result["text"])
        self.assertIn("匹配度", result["text"])
        self.assertIn("高", result["text"])

    def test_empirical_selection_ranks_psychology_journals(self):
        result = call_tool("journal_matcher", {"topic": "applicant perceptions of AI selection and fairness", "paper_type": "empirical"})
        self.assertIn("Personnel Psychology", result["text"])
        self.assertIn("International Journal of Selection and Assessment", result["text"])

    def test_requires_topic(self):
        result = call_tool("journal_matcher", {})
        self.assertIn("未提供论文主题", result["text"])

    def test_default_type_is_conceptual(self):
        result = call_tool("journal_matcher", {"topic": "algorithmic recruitment"})
        self.assertIn("论文类型: conceptual", result["text"])

    def test_substring_false_positive_eliminated(self):
        # 回归：旧的双向子串匹配会把 "training" 误命中领域 "ai"（t-r-AI-ning）
        result = call_tool("journal_matcher", {"topic": "employee training effectiveness", "paper_type": "empirical"})
        for line in result["text"].splitlines():
            if line.startswith("| ") and "ai" in line.split("|")[4].split(","):
                self.fail(f"'training' 不应命中领域 'ai'，但命中了: {line}")


class TestCitationVerify(unittest.TestCase):
    """citation_verify：Crossref API 存在性核验（mock 网络）。"""

    def _mock_crossref(self, message: dict):
        """返回一个 patch 用的 urlopen mock，返回 Crossref 风格的 message。"""
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": message}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        return mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx)

    def test_verify_by_doi_success(self):
        msg = {
            "DOI": "10.1038/nature12373",
            "title": ["Quantum entanglement of macroscopic objects"],
            "author": [{"given": "R.", "family": "Fickler"}],
            "container-title": ["Nature"],
            "volume": "497",
            "issue": "7448",
            "page": "330-333",
            "issued": {"date-parts": [[2013]]},
            "publisher": "Springer Science and Business Media LLC",
            "type": "journal-article",
        }
        with self._mock_crossref(msg):
            result = call_tool("citation_verify", {"doi": "10.1038/nature12373"})
        self.assertTrue(result["verified"])
        self.assertEqual(result["doi"], "10.1038/nature12373")
        self.assertEqual(result["title"], "Quantum entanglement of macroscopic objects")
        self.assertEqual(result["journal"], "Nature")
        self.assertEqual(result["volume"], "497")
        self.assertEqual(result["pages"], "330-333")
        self.assertEqual(result["year"], 2013)
        self.assertIn("doi.org", result["url"])

    def test_verify_by_title_success(self):
        msg = {
            "DOI": "10.1177/0149206311398160",
            "title": ["Human resource management systems"],
            "author": [{"given": "J.", "family": "Barney"}],
            "container-title": ["Journal of Management"],
            "year2": None,
            "issued": {"date-parts": [[2011]]},
            "type": "journal-article",
        }
        # 标题搜索接口返回 search 格式 {"message": {"items": [...]}}
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": {"items": [msg]}}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        with mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx):
            result = call_tool("citation_verify", {"title": "Human resource management systems"})
        self.assertTrue(result["verified"])
        self.assertEqual(result["doi"], "10.1177/0149206311398160")

    def test_verify_requires_doi_or_title(self):
        result = call_tool("citation_verify", {})
        self.assertFalse(result["verified"])
        self.assertIn("请提供 DOI 或标题", result["note"])

    def test_verify_http_404_returns_unverified(self):
        with mock.patch("paper_tools.urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 404, "Not Found", None, None)):
            result = call_tool("citation_verify", {"doi": "10.1000/not-a-real-doi"})
        self.assertFalse(result["verified"])
        self.assertIn("404", result["note"])

    def test_title_below_similarity_threshold_rejected(self):
        # 检索命中的候选与查询标题差异过大时，必须判未命中而非盲取第一条
        msg = {
            "DOI": "10.1000/unrelated",
            "title": ["Completely different paper about quantum chemistry"],
            "issued": {"date-parts": [[2010]]},
        }
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": {"items": [msg]}}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        with mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx):
            result = call_tool("citation_verify", {"title": "Algorithmic bias in hiring decisions"})
        self.assertFalse(result["verified"])
        self.assertEqual(result["grade"], "C")
        self.assertIn("相似度", result["note"])
        self.assertLess(result["similarity"], 0.85)

    def test_title_search_picks_most_similar_candidate(self):
        # 多候选时取相似度最高者，而非排序靠前的第一条
        far = {"DOI": "10.1000/far", "title": ["Notes on stochastic calculus"], "issued": {"date-parts": [[2001]]}}
        near = {"DOI": "10.1000/near", "title": ["Firm resources and sustained competitive advantage"], "issued": {"date-parts": [[1991]]}}
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": {"items": [far, near]}}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        with mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx):
            result = call_tool("citation_verify", {"title": "Firm resources and sustained competitive advantage"})
        self.assertTrue(result["verified"])
        self.assertEqual(result["doi"], "10.1000/near")

    def test_field_crosscheck_all_match_grades_a(self):
        msg = {
            "DOI": "10.1038/nature12373",
            "title": ["Quantum entanglement of macroscopic objects"],
            "author": [{"given": "R.", "family": "Fickler"}],
            "container-title": ["Nature"],
            "issued": {"date-parts": [[2013]]},
        }
        with self._mock_crossref(msg):
            result = call_tool(
                "citation_verify",
                {
                    "doi": "10.1038/nature12373",
                    "authors": "Fickler",
                    "year": 2013,
                },
            )
        self.assertTrue(result["verified"])
        self.assertEqual(result["grade"], "A")
        self.assertTrue(result["fieldChecks"]["authors"])
        self.assertTrue(result["fieldChecks"]["year"])

    def test_field_crosscheck_year_mismatch_grades_b(self):
        msg = {
            "DOI": "10.1038/nature12373",
            "title": ["Quantum entanglement of macroscopic objects"],
            "author": [{"given": "R.", "family": "Fickler"}],
            "issued": {"date-parts": [[2013]]},
        }
        with self._mock_crossref(msg):
            result = call_tool("citation_verify", {"doi": "10.1038/nature12373", "year": 2020})
        self.assertTrue(result["verified"])
        self.assertEqual(result["grade"], "B")
        self.assertFalse(result["fieldChecks"]["year"])


class TestLitSearch(unittest.TestCase):
    """lit_search：Semantic Scholar 真实检索（mock 网络）。"""

    def _mock_search(self, papers: list):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"total": len(papers), "data": papers}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        return mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx)

    def test_search_success(self):
        papers = [
            {
                "title": "Algorithmic recruitment and fairness",
                "authors": [{"name": "Alice"}, {"name": "Bob"}],
                "year": 2023,
                "abstract": "We study fairness in algorithmic recruitment.",
                "citationCount": 42,
                "externalIds": {"DOI": "10.1000/test"},
                "url": "https://example.com",
                "paperId": "abc123",
            }
        ]
        with self._mock_search(papers):
            result = call_tool("lit_search", {"query": "algorithmic recruitment fairness"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["title"], "Algorithmic recruitment and fairness")
        self.assertEqual(result["results"][0]["authors"], ["Alice", "Bob"])
        self.assertEqual(result["results"][0]["citationCount"], 42)
        self.assertEqual(result["results"][0]["doi"], "10.1000/test")
        self.assertEqual(result["results"][0]["year"], 2023)

    def test_search_empty_query(self):
        result = call_tool("lit_search", {"query": ""})
        self.assertEqual(result["total"], 0)
        self.assertIn("查询为空", result["note"])

    def test_search_retries_on_429_then_succeeds(self):
        # 前两次 429（限流），第三次成功——验证 _fetch_json 的退避重试
        papers = [{"title": "Retry works", "authors": [], "year": 2024, "abstract": None, "citationCount": 0, "externalIds": {}, "url": "", "paperId": "x"}]
        ok_resp = mock.MagicMock()
        ok_resp.read.return_value = json.dumps({"total": 1, "data": papers}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = ok_resp
        responses = [
            urllib.error.HTTPError("url", 429, "Too Many Requests", None, None),
            urllib.error.HTTPError("url", 429, "Too Many Requests", None, None),
            ctx,
        ]
        with mock.patch("paper_tools.urllib.request.urlopen", side_effect=responses), mock.patch("paper_tools.time.sleep"):
            result = call_tool("lit_search", {"query": "retry"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["title"], "Retry works")

    def test_search_429_exhausted_returns_actionable_note(self):
        responses = [
            urllib.error.HTTPError("url", 429, "Too Many Requests", None, None),
            urllib.error.HTTPError("url", 429, "Too Many Requests", None, None),
            urllib.error.HTTPError("url", 429, "Too Many Requests", None, None),
        ]
        with mock.patch("paper_tools.urllib.request.urlopen", side_effect=responses), mock.patch("paper_tools.time.sleep"):
            result = call_tool("lit_search", {"query": "limited"})
        self.assertEqual(result["total"], 0)
        self.assertIn("429", result["error"])
        self.assertIn("SEMANTIC_SCHOLAR_API_KEY", result["error"])


class TestJournalDataFile(unittest.TestCase):
    """data/journals.json 数据文件完整性（journal_matcher 的数据源）。"""

    def test_journal_db_loaded_from_data_file(self):
        self.assertGreaterEqual(len(paper_tools.JOURNAL_DB), 1)
        required = {"name", "type", "domains", "position", "length", "note"}
        for j in paper_tools.JOURNAL_DB:
            self.assertTrue(required.issubset(j), f"{j.get('name')} 缺字段")


class TestJournalSearchOpenAlex(unittest.TestCase):
    """journal_search_openalex：OpenAlex 期刊检索（mock 网络）。"""

    def _mock_openalex(self, payload: dict):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        return mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx)

    def test_search_success(self):
        payload = {
            "meta": {"count": 42},
            "results": [
                {
                    "id": "https://openalex.org/S123",
                    "display_name": "Journal of Testing",
                    "host_organization_name": "Test Press",
                    "works_count": 1000,
                    "cited_by_count": 50000,
                    "issn": ["1234-5678"],
                    "is_in_doaj": True,
                    "homepage_url": "https://example.com",
                    "summary_stats": {"h_index": 77, "i_index": 5, "2yr_mean_citedness": 3.2},
                }
            ],
        }
        with self._mock_openalex(payload):
            result = call_tool("journal_search_openalex", {"query": "testing"})
        self.assertEqual(result["total"], 42)
        r0 = result["results"][0]
        self.assertEqual(r0["name"], "Journal of Testing")
        self.assertEqual(r0["publisher"], "Test Press")
        self.assertEqual(r0["hIndex"], 77)
        self.assertTrue(r0["openAccess"])
        self.assertEqual(r0["openAlexId"], "S123")

    def test_search_empty_query(self):
        result = call_tool("journal_search_openalex", {"query": ""})
        self.assertEqual(result["total"], 0)
        self.assertIn("查询为空", result["note"])


class TestFetchJsonCache(unittest.TestCase):
    """_fetch_json 磁盘缓存：TTL 内第二次调用不发起网络请求。"""

    def setUp(self):
        paper_tools.CACHE_TTL = 3600
        shutil.rmtree(paper_tools.CACHE_DIR, ignore_errors=True)

    def tearDown(self):
        paper_tools.CACHE_TTL = 0
        shutil.rmtree(paper_tools.CACHE_DIR, ignore_errors=True)

    def test_second_call_served_from_cache(self):
        url = f"https://cache-test.example/unique-{uuid.uuid4()}"
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        with mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx) as m:
            first = paper_tools._fetch_json(url)
            second = paper_tools._fetch_json(url)
        self.assertEqual(m.call_count, 1)  # 第二次命中缓存，未再发请求
        self.assertEqual(first, second)

    def test_ttl_zero_bypasses_cache(self):
        paper_tools.CACHE_TTL = 0
        url = f"https://cache-test.example/unique-{uuid.uuid4()}"
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"n": 1}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        with mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx) as m:
            paper_tools._fetch_json(url)
            paper_tools._fetch_json(url)
        self.assertEqual(m.call_count, 2)


class TestVerifyReferences(unittest.TestCase):
    """verify_references：批量核验（mock 单条核验函数，不打真实网络）。"""

    SAMPLE = """# 论文

正文内容。

## References

- Barney, J. (1991). Firm resources and sustained competitive advantage. Journal of Management, 17(1), 99-120. https://doi.org/10.1000/known-doi
- Fake, F. (2099). A study that never existed anywhere at all. Journal of Nothing, 1(1), 1-2.
- Ambiguous (2020). Ab.
"""

    def test_report_with_grades_and_counts(self):
        with mock.patch("paper_tools._crossref_by_doi", return_value={"verified": True, "title": "Firm resources and sustained competitive advantage"}), self._patched_title():
            result = call_tool("verify_references", {"markdown": self.SAMPLE})
        text = result["text"]
        self.assertIn("批量核验报告", text)
        self.assertIn("A 级 1", text)
        self.assertIn("C 级 2", text)
        self.assertIn("DOI", text)  # 第一条按 DOI 核验
        self.assertIn("标题", text)  # 第二条按标题检索
        self.assertIn("严禁以当前形态写进投稿稿件", text)

    def _patched_title(self):
        return mock.patch("paper_tools._crossref_by_title", return_value={"verified": False, "similarity": 0.3, "note": "未找到匹配文献"})

    def test_empty_input(self):
        result = call_tool("verify_references", {"markdown": ""})
        self.assertIn("输入为空", result["text"])

    def test_no_entries(self):
        result = call_tool("verify_references", {"markdown": "# 只有正文\n没有参考文献\n"})
        self.assertIn("未在文本中识别到", result["text"])

    def test_doi_extraction_not_truncated(self):
        # 回归：惰性量词曾把 DOI 截断成斜杠后首字符（10.1038/nature12373 -> 10.1038/n），
        # 导致批量核验拿假 DOI 查询而误判 C 级。此测试锁定提取值本身。
        cases = [
            ("Barney, J. (1991). Firm resources. J, 1(1), 99-120. https://doi.org/10.1000/known-doi", "10.1000/known-doi"),
            ("A real entry with doi 10.1038/nature12373.", "10.1038/nature12373"),
            ("Nested (see doi.org/10.1000/j.journal.2023) done", "10.1000/j.journal.2023"),
        ]
        for text, expected in cases:
            m = paper_tools.DOI_PATTERN.search(text)
            self.assertIsNotNone(m, text)
            actual = paper_tools._clean_doi(m.group(0))
            self.assertEqual(actual, expected, text)

    def test_gbt_entry_title_extracted(self):
        # GB/T 条目（年份不在括号内）此前无法提取标题，永远判"无法提取"
        self.assertEqual(paper_tools._entry_title("[1] 王五. 一个国标格式的文献[J]. 期刊名, 2021, 5(2): 33-40."), "一个国标格式的文献")
        self.assertTrue(paper_tools._title_hint_long_enough("一个国标格式的文献"))
        self.assertFalse(paper_tools._title_hint_long_enough("深度学习综述"))  # 过短提示不检索

    def test_max_entries_truncation_notice(self):
        md = "# 论文\n\n## References\n\n" + "\n".join(f"- Author{i}, A. ({1990 + i}). Title number {i} of a long enough entry text here. J, 1(1), 1-2." for i in range(35))
        with self._patched_title(), mock.patch("paper_tools._crossref_by_doi", return_value={"verified": False}):
            result = call_tool("verify_references", {"markdown": md})
        self.assertIn("仅核验前 30 条", result["text"])


class TestProofreadSuite(unittest.TestCase):
    """全文质检校对套件（纯规则检查器）。"""

    def test_style_detects_ai_flavor_and_colloquial(self):
        md = "This study delves into the pivotal role of AI. 我们觉得这个东西说白了很简单。"
        result = call_tool("check_style", {"markdown": md})
        types = {i["type"] for i in result["issues"]}
        self.assertIn("ai_flavor", types)
        self.assertIn("colloquial", types)
        self.assertFalse(result["ok"])

    def test_style_clean_text_passes(self):
        result = call_tool("check_style", {"markdown": "# 标题\n\n实验结果表明该方法的准确率提升了 3 个百分点。\n"})
        self.assertTrue(result["ok"], result["issues"])

    def test_punctuation_halfwidth_after_cjk(self):
        result = call_tool("check_punctuation", {"markdown": "本方法效果显著, 准确率提升。\n"})
        self.assertFalse(result["ok"])
        self.assertTrue(any(i["type"] == "halfwidth_after_cjk" for i in result["issues"]))

    def test_punctuation_ignores_code_spans(self):
        md = "`a, b` 内联代码中的半角逗号不算问题，这里正常中文句子。\n"
        result = call_tool("check_punctuation", {"markdown": md})
        self.assertTrue(result["ok"], result["issues"])

    def test_figures_numbering_gap_and_phantom(self):
        md = "如图1所示与图3对比。\n\n**图1 示意**\n\n**图3 对比**\n"
        result = call_tool("check_figures_tables", {"markdown": md})
        types = {i["type"] for i in result["issues"]}
        self.assertIn("numbering_gap", types)  # 缺图2
        self.assertNotIn("phantom_reference", types)  # 图3 有 caption

    def test_figures_phantom_reference(self):
        md = "结果见图2。\n\n**图1 总览**\n"
        result = call_tool("check_figures_tables", {"markdown": md})
        self.assertTrue(any(i["type"] == "phantom_reference" for i in result["issues"]))

    def test_terms_undefined_acronym(self):
        md = "本文使用 RAG 技术构建系统。"  # 未定义 RAG
        result = call_tool("check_terms", {"markdown": md})
        self.assertTrue(any(i["type"] == "undefined_acronym" and "RAG" in i["detail"] for i in result["issues"]))

    def test_terms_common_acronym_exempt(self):
        md = "系统调用外部 API 获取数据。"
        result = call_tool("check_terms", {"markdown": md, "allow_common": True})
        self.assertTrue(result["ok"])
        strict = call_tool("check_terms", {"markdown": md, "allow_common": False})
        self.assertTrue(any("API" in i["detail"] for i in strict["issues"]))

    def test_terms_defined_but_unused(self):
        md = "检索增强生成（RAG）是常用范式。本文重点在写作而非检索。"
        result = call_tool("check_terms", {"markdown": md})
        # RAG 定义后未再次使用
        self.assertTrue(any(i["type"] == "unused_definition" for i in result["issues"]), result["issues"])

    def test_duplicates_detected(self):
        md = "这是第一段完全相同的测试句子内容示例。\n\n这是第一段完全相同的测试句子内容示例。\n"
        result = call_tool("check_duplicates", {"markdown": md})
        self.assertFalse(result["ok"])
        self.assertEqual(result["issues"][0]["type"], "duplicate_sentence")

    def test_references_future_year_flagged(self):
        md = "# 论文\n\n## References\n\n- Fake, F. (2099). A suspicious future paper title here. J, 1(1), 1-2.\n- Real, R. (2020). A perfectly normal past paper title. J, 2(1), 1-2.\n"
        result = call_tool("check_references_format", {"markdown": md})
        self.assertTrue(any(i["type"] == "future_year" for i in result["issues"]))

    def test_references_mixed_styles(self):
        md = "# 论文\n\n## References\n\n- Smith, J. (2020). One apa style paper about testing. Journal A, 1(1), 1-2.\n- [1] 王五. 一个国标格率的文献[J]. 期刊名, 2021, 5(2): 33-40.\n"
        result = call_tool("check_references_format", {"markdown": md})
        self.assertTrue(any(i["type"] == "mixed_styles" for i in result["issues"]))

    def test_proofread_composite_report(self):
        md = "# 测试论文\n\n本方法 delve 了问题, 如图2所示。\n\n**图1 演示**\n\n## References\n\n- A, B. (2098). Future hallucinated entry title example. J, 1(1), 1-2.\n"
        result = call_tool("proofread", {"markdown": md})
        self.assertIn("全文校对报告", result["text"])
        self.assertIn("ERROR", result["text"])  # 未来年份/幽灵引用为 error
        self.assertIn("WARNING", result["text"])  # AI 词/半角标点为 warning

    def test_proofread_empty_input(self):
        result = call_tool("proofread", {"markdown": ""})
        self.assertIn("输入为空", result["text"])


class TestIntextCitations(unittest.TestCase):
    """check_intext_citations：正文引用与文献表双向核对。"""

    NUMERIC = """# 论文

方法见文献[1]，与[2,5]一致，范围研究见[3-4]。

## References

- [1] Alpha A. First study[J]. J1, 2020.
- [2] Beta B. Second study[J]. J2, 2021.
- [3] Gamma C. Third study[J]. J3, 2022.
- [4] Delta D. Fourth study[J]. J4, 2023.
- [5] Epsilon E. Fifth study[J]. J5, 2024.
"""

    def test_numeric_all_paired_ok(self):
        result = call_tool("check_intext_citations", {"markdown": self.NUMERIC})
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(result["mode"], "numeric")

    def test_numeric_phantom_and_uncited(self):
        md = self.NUMERIC.replace("与[2,5]一致，范围研究见[3-4]。", "与[9]一致。")
        result = call_tool("check_intext_citations", {"markdown": md})
        types = {i["type"]: i for i in result["issues"]}
        self.assertIn("citation_missing_entry", types)  # [9] 不存在
        self.assertIn("entry_never_cited", types)  # [2][3][4][5] 未引用

    def test_author_year_matching(self):
        md = (
            "# 论文\n\n经典研究 (Smith, 2020) 与后续 (王五, 2021) 表明……\n\n"
            "## References\n\n"
            "- Smith, J. (2020). A classic paper on the topic. Journal X, 1(1), 1-9.\n"
            "- 王五. (2021). 另一篇中文论文标题示例. 期刊 Y, 2(1), 10-18.\n"
        )
        result = call_tool("check_intext_citations", {"markdown": md})
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(result["mode"], "author-year")

    def test_mixed_style_warning(self):
        md = "# 论文\n\n结果见[1]，另有研究 (Doe, 2019)。\n\n## References\n\n- [1] Alpha A. First study[J]. J1, 2020.\n"
        result = call_tool("check_intext_citations", {"markdown": md})
        self.assertTrue(any(i["type"] == "mixed_citation_style" for i in result["issues"]))

    def test_fullwidth_paren_author_year_detected(self):
        # 回归：中文论文常用全角括号（Lee, 2022），此前漏检导致混用告警失效
        md = (
            "# 论文\n\n框架见图2。相关研究见[1]，另有学者（Lee, 2022）指出。\n\n"
            "## References\n\n- [1] Alpha A. First study[J]. J1, 2020.\n"
            "- [2] Lee, K. (2022). Applicant reactions revisited. JAP, 107(3), 1-15.\n"
        )
        result = call_tool("check_intext_citations", {"markdown": md})
        self.assertTrue(any(i["type"] == "mixed_citation_style" for i in result["issues"]), result["issues"])
        self.assertEqual(result["mode"], "numeric")

    def test_time_adverbial_not_citation(self):
        # 回归：（截至2020年，…）是时间状语而非引用——曾误报 (截至, 2020) 幽灵引用
        md = (
            "# 论文\n\n## 1 引言\n\n相关研究进展缓慢（截至2020年，仅少数团队尝试）。"
            "经典框架见[1]。\n\n## References\n\n"
            "- [1] Smith, J. (2020). A real paper about this topic here. Journal, 1(1), 1-9.\n"
        )
        result = call_tool("check_intext_citations", {"markdown": md})
        self.assertFalse(any("截至" in i["detail"] for i in result["issues"]), result["issues"])


class TestSectionsAndBudget(unittest.TestCase):
    """check_sections 与 word_budget。"""

    EMPIRICAL_OK = """# 标题

**摘要**：本文研究 X。

**关键词**：A；B；C

## 1 引言

内容。

## 2 方法

内容。

## 3 结果

内容。

## 4 讨论

内容。

## 5 结论

内容。

## 参考文献

- Smith, J. (2020). Some paper about the topic here. Journal, 1(1), 1-9.
"""

    def test_empirical_complete_passes(self):
        result = call_tool("check_sections", {"markdown": self.EMPIRICAL_OK})
        self.assertTrue(result["ok"], result["issues"])

    def test_missing_methods_flagged(self):
        md = self.EMPIRICAL_OK.replace("## 2 方法\n\n内容。\n\n", "")
        result = call_tool("check_sections", {"markdown": md})
        self.assertTrue(any("Methods" in i["detail"] for i in result["issues"]))

    def test_keyword_count_info(self):
        md = self.EMPIRICAL_OK.replace("**关键词**：A；B；C", "**关键词**：只有两个词")
        result = call_tool("check_sections", {"markdown": md})
        self.assertTrue(any(i["type"] == "keyword_count" for i in result["issues"]))

    def test_word_budget_rows_and_unknown_journal(self):
        result = call_tool("word_budget", {"markdown": self.EMPIRICAL_OK, "journal": "top_empirical"})
        sections = [r["section"] for r in result["rows"]]
        self.assertIn("Introduction", sections)
        self.assertIn("Methods", sections)
        intro_row = next(r for r in result["rows"] if r["section"] == "Introduction")
        self.assertGreater(intro_row["actual"], 0)
        bad = call_tool("word_budget", {"markdown": "# x", "journal": "nope"})
        self.assertFalse(bad["ok"])

    def test_terms_roman_numerals_exempt(self):
        result = call_tool("check_terms", {"markdown": "实验分为 II、III、IV 三组进行。"})
        self.assertTrue(result["ok"], result["issues"])

    def test_proofread_json_format(self):
        result = call_tool(
            "proofread",
            {
                "markdown": "# T\n\n正文 delve 了问题。\n\n## References\n\n- A, B. (2098). Future entry title example here. J, 1(1), 1-2.\n",
                "format": "json",
            },
        )
        data = result if "summary" in result else json.loads(result["text"])
        self.assertIn("summary", data)
        self.assertIn("sections", data)
        names = {s["name"] for s in data["sections"]}
        self.assertIn("正文引用核对", names)


class TestIntegritySuite(unittest.TestCase):
    """学术诚信三件套：AI 痕迹 / 数字一致性 / 断言强度对冲。"""

    UNIFORM_TEXT = "。".join(["这是一个测试用的句子内容"] * 12) + "。"

    def test_ai_signature_short_text_guard(self):
        result = call_tool("check_ai_signature", {"markdown": "太短了，无法评估。"})
        self.assertTrue(result["ok"])
        self.assertIn("样本过短", result["note"])

    def test_ai_signature_uniform_sentences_flagged(self):
        result = call_tool("check_ai_signature", {"markdown": self.UNIFORM_TEXT})
        self.assertLess(result["metrics"]["burstinessCV"], 0.4)
        types = {i["type"] for i in result["issues"]}
        self.assertIn("low_burstiness", types)
        self.assertIn("band", result)
        self.assertIn("score", result)

    def test_ai_signature_varied_text_scores_lower(self):
        varied = (
            "本文提出一种新方法。实验！结果如何？我们发现效果显著提升了很多，"
            "尤其是在大规模数据集上的表现远超基线模型；与此同时，推理开销却几乎不变。"
            "为什么？关键在于三点。第一点，结构设计更合理；第二点，训练目标更贴近实际场景；"
            "第三点，也是最重要的一点——它把稀疏注意力用对了地方。综上，方法可行。"
            "当然，局限也存在。小样本场景下的稳定性仍待验证。"
        )
        r_uniform = call_tool("check_ai_signature", {"markdown": self.UNIFORM_TEXT})
        r_varied = call_tool("check_ai_signature", {"markdown": varied})
        self.assertLess(r_varied["score"], r_uniform["score"])

    def test_numbers_sample_size_conflict(self):
        md = "# 论文\n\n本研究样本量为300名参与者。\n\n## 方法\n\n数据分析基于最终样本量为280名。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "sample_size_conflict" for i in result["issues"]))

    def test_numbers_nonexclusive_buckets_exempt(self):
        md = "# 论文\n\n共发放问卷300份，回收285份，其中有效问卷260份。\n"
        result = call_tool("check_numbers", {"markdown": md})
        # 发放/回收/有效 是不同口径，不应互相矛盾
        self.assertFalse(any(i["type"] == "sample_size_conflict" for i in result["issues"]), result["issues"])

    def test_numbers_percent_overflow(self):
        md = "# 论文\n\n其中男性占60%，女性占50%，其他占5%。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "percent_overflow" for i in result["issues"]))

    def test_numbers_ci_percent_not_counted_as_share(self):
        # 回归：'95% CI' 是置信区间而非分类占比，不应计入加和（v2 修复稿曾误报 195%）
        md = "# 论文\n\n样本中本科占40%、硕士占35%、博士占25%。差异显著（p=0.03），Cohen d=0.62，95% CI [0.41, 0.83]。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "percent_overflow" for i in result["issues"]), result["issues"])

    def test_numbers_ratio_over_100(self):
        md = "# 论文\n\n该方法占比150%的市场份额。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "ratio_over_100" for i in result["issues"]))

    def test_numbers_fullwidth_percent_no_crash(self):
        # 回归：全角％分支无捕获组曾导致 float('') ValueError 崩溃
        md = "# 论文\n\n结果显示满意度达85％，比上年度提升12％。两项指标表现稳定。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(result["ok"], result["issues"])  # 85+12=97 合法，且未崩溃

    def test_numbers_fullwidth_percent_overflow_still_caught(self):
        md = "# 论文\n\n其中男性占60％，女性占50％。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "percent_overflow" for i in result["issues"]))

    def test_numbers_partition_sum_overflow(self):
        # 回归：互斥分桶加和超总量（"其中…另外…"），经典样本造假结构（v0.1.0 修复）
        md = "# 论文\n\n## 方法\n\n我们调查了300名学生。其中180名使用移动学习平台，另外200名使用传统方式。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "partition_sum_overflow" for i in result["issues"]), result["issues"])

    def test_numbers_partition_equal_not_flagged(self):
        md = "# 论文\n\n## 方法\n\n我们调查了300名学生。其中180名使用平台，另外120名不使用。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "partition_sum_overflow" for i in result["issues"]), result["issues"])

    def test_numbers_partition_bucket_over_container(self):
        md = "# 论文\n\n样本量为200人，其中男生350人，女生140人。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "partition_sum_overflow" for i in result["issues"]), result["issues"])

    def test_numbers_partition_flow_keywords_not_flagged(self):
        # 发放/回收/有效为流量口径且无样本关键词命中，不进入分桶检查
        md = "# 论文\n\n共发放问卷500份，回收480份，其中有效问卷450份。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "partition_sum_overflow" for i in result["issues"]), result["issues"])

    def test_numbers_thousands_separator_conflict(self):
        # 回归：千分位写法（1,500）曾对样本检查完全隐形
        md = "# 论文\n\n本研究样本量为1,500名参与者。\n\n## 方法\n\n数据分析基于最终样本量为1,200名。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "sample_size_conflict" for i in result["issues"]), result["issues"])

    def test_numbers_thousands_separator_same_value_no_conflict(self):
        md = "# 论文\n\n本研究样本量为1,500名参与者。\n\n## 方法\n\n数据分析基于全部1500名参与者。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "sample_size_conflict" for i in result["issues"]), result["issues"])

    def test_numbers_valid_sample_qualifier_still_separate(self):
        # 总样本与"有效样本"是不同口径（发放/有效流量），不应互相判矛盾
        md = "# 论文\n\n本研究样本量为1,500名参与者。\n\n## 方法\n\n最终有效样本为1,200名。\n"
        result = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "sample_size_conflict" for i in result["issues"]), result["issues"])

    def test_terms_definition_forms_recognized(self):
        # 回归：全称在前/缩写收尾的定义形态（学术写作最常见）曾不被识别，导致 AD/RL 误报
        md = (
            "## 方法\n"
            "本文研究异常检测（Anomaly Detection, AD）问题。\n"
            "深度学习 (deep learning, DL) 与强化学习 (RL) 均有涉及。\n"
            "IT 行业背景见相关报告。\n"
            "我们提出 QZX 模型处理该问题。\n"
        )
        result = call_tool("check_terms", {"markdown": md})
        undefined = [i["detail"] for i in result["issues"] if i["type"] == "undefined_acronym"]
        self.assertFalse(any("'AD'" in d or "'DL'" in d or "'RL'" in d or "'IT'" in d for d in undefined), undefined)
        self.assertTrue(any("'QZX'" in d for d in undefined), "真实未定义缩写应报出")

    def test_stats_p_value_cjk_adjacent(self):
        # 回归：中文紧邻写法"表明p=0.000"曾因 \b 词边界整体漏检（v0.1.0 修复）
        md = "# 论文\n\n## 结果\n\n数据分析表明p=0.000，效果极其显著。\n"
        result = call_tool("check_stats", {"markdown": md})
        self.assertTrue(any(i["type"] == "p_zero" for i in result["issues"]), result["issues"])

    def test_stats_p_value_cjk_trailing_digits_kept(self):
        # "p=0.000显著" 不能被截断成 p=0：数值后的汉字不应破坏完整捕获
        md = "# 论文\n\n## 结果\n\nt检验表明p=0.000显著。\n"
        result = call_tool("check_stats", {"markdown": md})
        self.assertEqual(result["summary"]["pValues"], 1, result["summary"])
        self.assertTrue(any(i["type"] == "p_zero" for i in result["issues"]), result["issues"])

    def test_ai_signature_line_numbers_survive_fences(self):
        # 回归：代码块剥离曾塌缩行数，其后发现的行号整体偏移（代码块在第3-5行）
        doc = (
            "# 论文\n\n```python\nx = 1  # underscores the importance\n```\n\n"
            "本章 underscores the importance of the method in practice.\n"
            "它显著提升了效果。此外结果稳健。而且方法通用。然而成本更低。因此值得推广。"
            "综上建议采用。同时保持审慎。"
        )
        result = call_tool("check_ai_signature", {"markdown": doc})
        truth = next(i + 1 for i, ln in enumerate(doc.split("\n")) if ln.startswith("本章"))
        hits = [i["line"] for i in result["issues"] if "underscores" in i.get("detail", "")]
        self.assertTrue(hits, "模板短语未检出")
        self.assertEqual(hits[0], truth, f"行号漂移: 报告 {hits[0]}, 真实 {truth}")

    def test_tamper_line_numbers_survive_fences(self):
        doc = "# 论文\n\n```python\nx = 1\n```\n\n正文开始。\u200b零宽字符在这里。\n"
        result = call_tool("check_tamper_traces", {"markdown": doc})
        zw = [i for i in result["issues"] if i["type"] == "zero_width_chars"]
        self.assertTrue(zw, "零宽字符未检出")
        truth = next(i + 1 for i, ln in enumerate(doc.split("\n")) if "\u200b" in ln)
        self.assertIn(f"L{truth}", zw[0]["detail"], zw[0]["detail"])

    def test_stats_and_figures_ignore_code_block(self):
        # 代码块里的 p=0.000（示例/注释）不是论文统计报告
        md = (
            "# 论文\n\n```python\n# p=0.000 如表2所示\nprint(res)\n```\n\n"
            "## 方法\n\n本文使用 t 检验（p=0.03）分析数据，结果见表2。\n"
        )
        result = call_tool("check_stats", {"markdown": md})
        self.assertFalse(any("p=0.000" in i.get("detail", "") for i in result["issues"]), result["issues"])
        self.assertEqual(result["summary"]["pValues"], 1, result["summary"])

    def test_citation_verify_network_error_is_x_not_c(self):
        # 回归：网络不可达曾被折叠成 C 级（查无此文），离线 CI 会误拦门禁
        with mock.patch("paper_tools.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")), mock.patch("paper_tools.time.sleep"):
            out = json.loads(paper_tools.citation_verify(doi="10.9999/x grade.test.offline"))
        self.assertEqual(out["grade"], "X", out)
        self.assertTrue(out.get("unverifiable"), out)

    def test_citation_verify_http_404_is_c(self):
        # 真正的"查无此文"必须是 C，不能伪装成网络故障
        with mock.patch("paper_tools.urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 404, "Not Found", None, None)):
            out = json.loads(paper_tools.citation_verify(doi="10.9999/x grade.test.404"))
        self.assertEqual(out["grade"], "C", out)

    def test_verify_references_offline_reports_x_never_fails_gate(self):
        md = "# 论文\n\n## 参考文献\n\n[1] Smith, J. (2020). Mobile learning systems in higher education practice. Journal of Educational Technology, 15(2), 100-110.\n"
        with mock.patch("paper_tools.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")), mock.patch("paper_tools.time.sleep"):
            report = paper_tools.verify_references(md)
        self.assertIn("X 级 1", report, report[:400])
        self.assertIn("不计入门禁失败", report)
        # X 级在 CLI 门禁语义下永不触发失败（threshold_rank X=99）
        self.assertNotIn("C 级 1", report)

    def test_hedging_unhedged_section_flagged(self):
        md = "# 论文\n\n## 结果分析\n\n显然该方法效果极佳。这无疑是重大突破。它彻底解决了问题。\n"
        result = call_tool("check_hedging", {"markdown": md})
        self.assertTrue(any(i["type"] == "unhedged_section" for i in result["issues"]))
        self.assertTrue(any(i["type"] == "absolute_term" for i in result["issues"]))

    def test_hedging_balanced_section_passes(self):
        md = "# 论文\n\n## 讨论\n\n结果表明该方法可能更优，相对基线约提升 5%，或许源于数据分布差异。这一发现有助于解释此前研究的不一致。\n"
        result = call_tool("check_hedging", {"markdown": md})
        self.assertTrue(result["ok"], result["issues"])

    def test_hedging_no_substring_false_positive(self):
        # 回归：'相对论/条约/约束' 曾被裸词 '相对/约' 子串误计为对冲措辞
        md = "# 论文\n\n## 理论\n\n本文基于相对论框架分析引力约束条件，并讨论了国际条约中的相关规定。该方法完全成立。\n"
        result = call_tool("check_hedging", {"markdown": md})
        theory = next(s for s in result["sections"] if s["section"] == "理论")
        self.assertEqual(theory["hedges"], 0, theory)


class TestStatsAndAudit(unittest.TestCase):
    """check_stats 统计红线 + audit_paper 一键审计。"""

    def test_stats_p_without_test_name(self):
        md = "# 论文\n\n组间差异显著（p=0.03）。\n"
        result = call_tool("check_stats", {"markdown": md})
        self.assertTrue(any(i["type"] == "p_without_test" for i in result["issues"]))
        self.assertEqual(result["summary"]["pValues"], 1)

    def test_stats_with_test_name_passes(self):
        md = "# 论文\n\n## 方法\n\n采用独立样本 t 检验。结果差异显著（p=0.03），Cohen d=0.8，95% CI [0.2, 1.4]。\n"
        result = call_tool("check_stats", {"markdown": md})
        self.assertFalse(any(i["type"] == "p_without_test" for i in result["issues"]), result["issues"])
        self.assertFalse(any(i["type"] == "missing_effect_size" for i in result["issues"]))

    def test_stats_out_of_range_and_zero_p(self):
        md = "# 论文\n\n报告 p=2.5 与 p=0.000 两处。\n"
        result = call_tool("check_stats", {"markdown": md})
        types = {i["type"] for i in result["issues"]}
        self.assertIn("p_out_of_range", types)
        self.assertIn("p_zero", types)

    def test_audit_paper_composite(self):
        md = "# 论文标题\n\n显然该方法效果极佳。\n\n## 1 引言\n\n引用见[3]。\n\n## 参考文献\n\n- [1] A, B. (2099). Future hallucinated title example here. J, 1(1), 1-2.\n"
        result = call_tool("audit_paper", {"markdown": md, "genre": "empirical"})
        text = result["text"]
        self.assertIn("审计总分", text)
        self.assertIn("AI 痕迹画像", text)
        self.assertIn("统计诚信", text)

    def test_audit_paper_json(self):
        md = "# T\n\n一些正文内容足够长以通过基本检查。\n\n## References\n\n- A, B. (2020). Normal past paper title here. J, 1(1), 1-2.\n"
        result = call_tool("audit_paper", {"markdown": md, "format": "json"})
        data = result if "score" in result else json.loads(result["text"])
        self.assertIn("score", data)
        self.assertIn("statsSummary", data)
        names = {s["name"] for s in data["sections"]}
        self.assertIn("AI 痕迹画像", names)


class TestLatexAndSelfPlagiarism(unittest.TestCase):
    """LaTeX 稿件感知 + 跨文档自查重（v1.20.0）。"""

    TEX_OK = "\\section{Intro} body text here with enough words to count well.\n\\subsection{Detail} more content follows in this subsection block."
    TEX_NOHEAD = "plain prose without any heading command."

    def test_word_count_latex(self):
        r = call_tool("word_count", {"markdown": self.TEX_OK, "source_format": "latex"})
        self.assertGreater(r["words"], 10)

    def test_structure_latex_headings(self):
        r = call_tool("check_structure", {"markdown": self.TEX_OK, "source_format": "latex"})
        self.assertTrue(r["ok"])
        self.assertEqual([h["title"] for h in r["headings"]], ["Intro", "Detail"])

    def test_structure_issues_are_dicts(self):
        # 回归：结构问题曾以裸字符串进入 issues，炸穿 proofread 的分级统计
        r = call_tool("check_structure", {"markdown": self.TEX_NOHEAD, "source_format": "latex"})
        item = r["issues"][0]
        assert isinstance(item, dict)
        self.assertEqual(item["type"], "no_headings")

    def test_proofread_latex_json(self):
        rep = call_tool("proofread", {"markdown": self.TEX_OK, "source_format": "latex", "format": "json"})
        data = rep if isinstance(rep, dict) else json.loads(rep["text"])
        self.assertIn("summary", data)

    def test_self_plagiarism_detects_overlap(self):
        import tempfile

        corpus = tempfile.mkdtemp(prefix="scholarseed-corpus-")
        shared = "this is a very distinctive sentence used for overlap testing purposes."
        with open(os.path.join(corpus, "old_paper.md"), "w", encoding="utf-8") as f:
            f.write("# Old\n\n" + shared + "\n")
        cur = "# New submission\n\n" + shared + "\nPlus novel analysis."
        r = call_tool("check_self_plagiarism", {"markdown": cur, "corpus_dir": corpus})
        files = {f["file"]: f["ratio"] for f in r["files"]}
        self.assertGreater(files.get("old_paper.md", 0), 0.05)
        self.assertTrue(any(i["type"] == "self_overlap" for i in r["issues"]))

    def test_self_plagiarism_missing_dir_skips(self):
        r = call_tool("check_self_plagiarism", {"markdown": "some text here", "corpus_dir": "Z:/no/such/dir"})
        self.assertTrue(r["ok"])

    def test_wrapped_reference_merged(self):
        # 回归：折行的文献条目曾把续行整体丢弃（卷期页码丢失）
        md = "# 论文\n\n## References\n\n- Barney, J. (1991). Firm resources and sustained competitive advantage.\n  Journal of Management, 17(1), 99-120.\n"
        entries = paper_tools._extract_reference_entries(md)
        self.assertEqual(len(entries), 1)
        self.assertIn("Journal of Management", entries[0])

    def test_audit_info_not_scored(self):
        # 回归：纯 INFO 提示曾无上限扣分（12 条 info 扣掉 21 分）。
        # 文档需满足其他全部检查，仅剩绝对化用词的 INFO 提示。
        md = (
            "# 论文\n\n"
            "**摘要**：本文检验 X。\n\n"
            "**关键词**：A；B；C\n\n"
            "## 1 引言\n\n背景见[1]。显然方案可行，无疑具有优势。不过可能仍存在局限。\n\n"
            "## 2 方法\n\n样本量为200名参与者。显然测量无疑可靠。或许仍有大约改进空间。\n\n"
            "## 3 结果\n\n采用 t 检验，结果显著（p=0.03），Cohen d=0.62，95% CI [0.4, 0.8]。"
            "显然效果接近完美，但可能受样本限制。\n\n"
            "## 4 讨论\n\n该发现无疑值得关注，或许与分布差异有关，有助于解释此前分歧。\n\n"
            "## 5 结论\n\n显然本研究推进了该方向，但仍需大量验证。\n\n"
            "## 参考文献\n\n"
            "- [1] Smith, J. (2020). A real paper about this topic here. Journal, 1(1), 1-9.\n"
        )
        result = call_tool("audit_paper", {"markdown": md, "genre": "empirical", "format": "json"})
        data = result if isinstance(result, dict) else json.loads(result["text"])
        self.assertEqual(data["score"], 100)
        self.assertGreater(data["summary"]["infos"], 0)  # 确有 info 存在但不扣分

    def test_sentences_abbrev_guard(self):
        sents = [
            "Smith et al. proposed a novel framework for algorithmic hiring.",
            "Jones et al. replicated the study across three industry sectors.",
            "As shown in Fig. 3, the effect sizes remain stable.",
            "Lee et al. questioned the external validity of these findings.",
            "Follow-up experiments by Wang et al. addressed this concern.",
            "Table 2 summarizes all participant demographics.",
            "Park et al. extended the model to gig-economy contexts.",
            "Overall the evidence points to consistent patterns.",
        ]
        r = call_tool("check_ai_signature", {"markdown": " ".join(sents)})
        self.assertEqual(r["metrics"]["sentences"], 8)


class TestProtocolHandshake(unittest.TestCase):
    def test_initialize(self):
        response = _rpc(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(response["result"]["serverInfo"]["name"], "paper-tools")

    def test_tools_list(self):
        response = _rpc(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}))
        names = {t["name"] for t in response["result"]["tools"]}
        self.assertEqual(
            names,
            {
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
                "check_rigor_declarations",
                "check_anonymization",
            },
        )

    def test_unknown_method(self):
        response = _rpc(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "nope", "params": {}}))
        self.assertEqual(response["error"]["code"], -32601)

    def test_malformed_json_returns_parse_error(self):
        # JSON-RPC 2.0 规范：解析失败必须返回 -32700，不得静默丢弃
        response = _rpc("{not valid json")
        self.assertIsNone(response["id"])
        self.assertEqual(response["error"]["code"], -32700)
        self.assertIn("Parse error", response["error"]["message"])


class TestBatchThreeFixes(unittest.TestCase):
    """问题排查第三批：英文阈值/代码块泄漏/LaTeX 嵌套与转义。"""

    def test_long_sentence_en_not_flagged(self):
        # 回归：25 词规范英文学术句（约160字符）曾被 90 字符阈值误判超长
        md = "# Paper\n\nWe conducted a series of controlled experiments across three benchmark datasets to evaluate whether the proposed method generalizes beyond its original setting.\n"
        r = call_tool("check_style", {"markdown": md})
        self.assertFalse(any(i["type"] == "long_sentence" for i in r["issues"]), r["issues"])

    def test_long_sentence_zh_still_flagged(self):
        md = "# 论文\n\n本研究通过一系列大规模受控实验系统性地验证了该方法在多种不同场景下的有效性并进一步分析了其在极端条件下的鲁棒性表现以及潜在的失效模式与相应的改进方向。\n"
        r = call_tool("check_style", {"markdown": md})
        self.assertTrue(any(i["type"] == "long_sentence" for i in r["issues"]))

    def test_style_ignores_code_fence(self):
        # 回归：围栏代码块内的 AI 词曾被当正文检查
        md = "# 论文\n\n```python\n# delve into the data pipeline\nprocess(data)\n```\n正文正常表述，不含任何问题词汇。\n"
        r = call_tool("check_style", {"markdown": md})
        self.assertFalse(any(i["type"] == "ai_flavor" for i in r["issues"]), r["issues"])

    def test_latex_nested_brace_section_title(self):
        # 回归：标题内嵌花括号曾使转换器输出空串
        tex = "\\section{Effects of \\texttt{learning-rate} schedules}"
        r = call_tool("check_structure", {"markdown": tex, "source_format": "latex"})
        titles = [h["title"] for h in r["headings"]]
        self.assertEqual(titles, ["Effects of learning-rate schedules"])

    def test_latex_escaped_dollar_preserved(self):
        # 回归：字面美元 \$5 曾被当作公式定界符注入 MATH
        from paper_tools import _latex_to_text

        tex = "The intervention costs \\$5 per unit and \\$10 total for firms."
        md = _latex_to_text(tex)
        self.assertIn("\\$5", md)
        self.assertNotIn("MATH", md)

    def test_latex_real_math_stripped(self):
        from paper_tools import _latex_to_text

        md = _latex_to_text("The effect is significant ($p<0.05$) across models.")
        self.assertIn("MATH", md)
        self.assertNotIn("0.05", md)


class TestCorpusCalibration(unittest.TestCase):
    """v1.21.0 真实语料校准回归（arXiv CS/数学/经济三学科实测驱动）。"""

    def test_mattr_length_invariance(self):
        # 旧 TTR 在长文档必然塌缩（2500 token -> ~0.12）；MATTR 应保持稳定
        import itertools

        # 纯字母真异形词：数字会被分词剥离导致全部塌缩为同一 token
        vocab = ["".join(c) for c in itertools.product("abcdefg", repeat=3)]
        tokens = []
        i = 0
        while len(tokens) < 2500:
            tokens.append(vocab[i % 300])
            if len(tokens) % 20 == 0:
                tokens.append(".")
            i += 1
        r = call_tool("check_ai_signature", {"markdown": " ".join(tokens) + "."})
        self.assertGreater(r["metrics"]["mattrEn"], 0.4)

    def test_zh_only_no_english_penalty(self):
        # 纯中文文本不应因无英文词被扣 mattrEn 满额缺分
        varied = (
            "本文提出一种新方法。实验！结果如何？我们发现效果显著提升了很多，"
            "尤其是在大规模数据集上的表现远超基线模型；与此同时，推理开销却几乎不变。"
            "为什么？关键在于三点。第一点，结构设计更合理；第二点，训练目标更贴近实际场景；"
            "第三点，也是最重要的一点——它把稀疏注意力用对了地方。综上，方法可行。"
            "当然，局限也存在。小样本场景下的稳定性仍待验证。"
        )
        r = call_tool("check_ai_signature", {"markdown": varied})
        self.assertLess(r["score"], 60)

    def test_latex_cite_keys_missing_and_uncited(self):
        tex = (
            "\\cite{alpha} and \\cite{ghost, alpha} discussed.\n"
            "\\begin{thebibliography}{9}\n"
            "\\bibitem{alpha} A. Alpha. Study One. 2020.\n"
            r"\end{thebibliography}"
        )
        r = paper_tools._check_cite_keys(tex)
        types = {i["type"] for i in r["issues"]}
        self.assertIn("citation_missing_entry", types)  # ghost 无 bibitem
        self.assertEqual(r["entries"], 1)

    def test_latex_empty_bib_downgrades_to_skip(self):
        # 参考文献在独立 .bbl 时：单文件输入看不到 \bibitem，应诚实跳过而非误报爆炸
        tex = "We discuss \\cite{a1} and \\cite{b2}. No bibliography here."
        r = paper_tools._check_cite_keys(tex)
        self.assertTrue(r["ok"])
        self.assertTrue(any(i["type"] == "bbl_external" for i in r["issues"]))

    def test_duplicates_two_occurrences_info(self):
        shared = "这一句在文档中出现了两次用于测试分级行为样例内容。"
        md = "# 论文\n\n" + shared + "\n\n再次出现：" + shared + "\n"
        r = call_tool("check_duplicates", {"markdown": md})
        self.assertTrue(all(i["severity"] == "info" for i in r["issues"]), r["issues"])

    def test_en_sample_requires_context(self):
        # 回归：数学证明中的 N=100 不带样本语义时不应触发口径矛盾
        md = "# 论文\n\n设 N=100 为群阶。由拉格朗日定理可得 N=200 的情形亦成立。\n"
        r = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "sample_size_conflict" for i in r["issues"]), r["issues"])

    def test_terms_placeholders_and_bib_excluded(self):
        tex = (
            "\\section{Intro}\nWe use REF CITE ENV MATH tokens here.\n"
            "\\begin{thebibliography}{9}\n\\bibitem{a} DBLP: ICLR NIPS WMT venue line 2020.\n"
            r"\end{thebibliography}"
        )
        r = call_tool("check_terms", {"markdown": tex, "source_format": "latex"})
        toks = [i["detail"].split("'")[1] for i in r["issues"] if i["type"] == "undefined_acronym"]
        for banned in ("REF", "CITE", "ENV", "MATH", "DBLP", "ICLR", "NIPS", "WMT"):
            self.assertNotIn(banned, toks, f"{banned} 不应被标记")

    def test_thebibliography_stripped_from_conversion(self):
        from paper_tools import _latex_to_text

        tex = (
            "\\section{Body} content here.\n"
            "\\begin{thebibliography}{9}\n\\bibitem{k} Some venue DBLP entry.\n"
            r"\end{thebibliography}"
        )
        md = _latex_to_text(tex)
        self.assertNotIn("DBLP", md)
        self.assertIn("content here", md)


class TestAuditPdf(unittest.TestCase):
    """audit_pdf：尽力级 PDF 文本提取与子集审计。"""

    @staticmethod
    def _mini_pdf(stream: bytes) -> bytes:
        return b"%PDF-1.4\n1 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n%%EOF"

    def _write(self, tmpdir, name, data):
        p = os.path.join(tmpdir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_uncompressed_stream_extracted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            body = b"BT (We conducted experiments on algorithmic fairness metrics.) Tj ET"
            path = self._write(td, "plain.pdf", self._mini_pdf(body))
            result = call_tool("audit_pdf", {"pdf_path": path, "genre": "tech", "min_chars": 40, "format": "json"})
            data = result if isinstance(result, dict) else json.loads(result["text"])
            self.assertGreater(data["extractedChars"], 20)
            names = {s["name"] for s in data["sections"]}
            self.assertIn("文风", names)
            self.assertIn("skippedChecks", data)

    def test_flate_stream_extracted(self):
        import tempfile
        import zlib

        with tempfile.TemporaryDirectory() as td:
            body = zlib.compress(b"BT (Clearly the method completely solves nothing.) Tj ET")
            path = self._write(td, "flate.pdf", self._mini_pdf(body))
            result = call_tool("audit_pdf", {"pdf_path": path, "min_chars": 40, "format": "json"})
            data = result if isinstance(result, dict) else json.loads(result["text"])
            self.assertGreater(data["extractedChars"], 20)

    def test_missing_file_note(self):
        result = call_tool("audit_pdf", {"pdf_path": "Z:/no/such/file.pdf"})
        text = result.get("note", "") if isinstance(result, dict) else str(result)
        self.assertIn("不存在", text)


class TestRegressionV1233(unittest.TestCase):
    """v1.23.3 回归：proofread 统计诚信丢失 + 科学计数 p 值误报（审查发现）。"""

    EMPIRICAL_BAD = (
        "# 论文标题\n\n## 摘要\n\n本研究检验假设。\n\n"
        "## 方法\n\n对被试进行 t 检验。\n\n"
        "## 结果\n\np=0.000，组间显著差异。\n\n"
        "## 结论\n\n效果显著。\n\n"
        "## 参考文献\n\nSmith, J. (2020). Some real looking title here. J, 1(1), 1-2.\n"
    )

    def test_proofread_includes_stats_section(self):
        """proofread 的统计诚信检查不得被覆盖丢弃。"""
        data = call_tool("proofread", {"markdown": self.EMPIRICAL_BAD, "format": "json"})
        names = {s["name"] for s in data["sections"]}
        self.assertIn("统计诚信", names)

    def test_proofread_stats_flags_p_zero(self):
        """proofread 报告应包含 p=0.000 这类统计红线问题。"""
        data = call_tool("proofread", {"markdown": self.EMPIRICAL_BAD, "format": "json"})
        stats_section = next(s for s in data["sections"] if s["name"] == "统计诚信")
        types = {i["type"] for i in stats_section["issues"]}
        self.assertIn("p_zero", types)

    def test_check_stats_scientific_notation_not_out_of_range(self):
        """p<10^{-7} 是合法小 p 值，不得报 p_out_of_range。"""
        md = "本文采用 t 检验分析，结果 p<10^{-7}，差异显著，报告 Cohen d=0.8 与 95% CI。\n\n## 参考文献\n\nA, B. (2021). Enough title words for matching here. J, 2(1), 1-2.\n"
        result = call_tool("check_stats", {"markdown": md})
        types = {i["type"] for i in result["issues"]}
        self.assertNotIn("p_out_of_range", types)

    def test_proofread_survey_genre_skips_stats(self):
        """非 empirical 体裁不注入统计诚信节（与 audit_paper 口径一致）。"""
        md = "# T\n\n一些正文内容足够长以通过基本检查。\n\n## References\n\n- A, B. (2020). Normal past paper title. J, 1(1), 1-2.\n"
        data = call_tool("proofread", {"markdown": md, "genre": "survey", "format": "json"})
        names = {s["name"] for s in data["sections"]}
        self.assertNotIn("统计诚信", names)


class TestWriterToolsV1240(unittest.TestCase):
    """v1.24.0 写作者工具：format_citation / check_abstract / check_title / audit_project。"""

    def _mock_crossref(self, message: dict):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": message}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        return mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx)

    MSG: ClassVar[dict] = {
        "DOI": "10.1038/nature14539",
        "title": ["Deep learning"],
        "author": [{"given": "Yann", "family": "LeCun"}, {"given": "Yoshua", "family": "Bengio"}, {"given": "Geoffrey", "family": "Hinton"}],
        "container-title": ["Nature"],
        "volume": "521",
        "issue": "7553",
        "page": "436-444",
        "issued": {"date-parts": [[2015]]},
        "publisher": "Springer Science and Business Media LLC",
        "type": "journal-article",
    }

    def test_format_citation_apa(self):
        with self._mock_crossref(self.MSG):
            out = call_tool("format_citation", {"doi": "10.1038/nature14539", "style": "apa"})
        self.assertIn("LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning.", out["text"])
        self.assertIn("Nature, 521(7553), 436-444", out["text"])
        self.assertIn("分级 A", out["text"])

    def test_format_citation_gbt(self):
        with self._mock_crossref(self.MSG):
            out = call_tool("format_citation", {"doi": "10.1038/nature14539", "style": "gbt"})
        self.assertIn("LECUN Y, BENGIO Y, HINTON G. Deep learning[J]. Nature, 2015, 521(7553): 436-444.", out["text"])

    def test_format_citation_ieee_and_bibtex(self):
        with self._mock_crossref(self.MSG):
            ieee = call_tool("format_citation", {"doi": "10.1038/nature14539", "style": "ieee"})
            bib = call_tool("format_citation", {"doi": "10.1038/nature14539", "style": "bibtex"})
        self.assertIn('Y. LeCun, Y. Bengio, and G. Hinton, "Deep learning," Nature, vol. 521', ieee["text"])
        self.assertIn("@article{lecun2015deep,", bib["text"])
        self.assertIn("pages   = {436--444}", bib["text"])

    def test_format_citation_unverified_no_entry(self):
        msg = {"message": {"items": []}}
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(msg).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        with mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx):
            out = call_tool("format_citation", {"title": "No Such Paper Exists Anywhere At All"})
        self.assertFalse(out.get("ok", True))
        self.assertEqual(out.get("grade"), "C")

    ABSTRACT_MD = (
        "# 标题\n\n## 摘要\n\n"
        "本研究旨在检验远程办公对员工绩效的影响，弥补现有弹性用工研究的空白。"
        "基于某科技企业 500 名员工两年的面板数据，采用固定效应模型进行分析。"
        "结果表明远程办公使绩效显著提升约 12%（p<0.01），且对高自主性岗位效应更强。"
        "研究结论为企业弹性用工政策与未来混合办公设计提供了实证依据与管理启示。\n\n"
        "## 引言\n\n正文。\n"
    )

    def test_check_abstract_all_elements(self):
        result = call_tool("check_abstract", {"markdown": self.ABSTRACT_MD})
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["summary"]["elementsMissing"]), 0)

    def test_check_abstract_missing_results(self):
        stripped = self.ABSTRACT_MD.replace("结果表明远程办公使绩效显著提升约 12%（p<0.01），且对高自主性岗位效应更强。", "")
        result = call_tool("check_abstract", {"markdown": stripped})
        types = {i["type"] for i in result["issues"]}
        self.assertIn("abstract_missing_element", types)

    def test_check_title_weak_words(self):
        result = call_tool("check_title", {"title": "浅析大数据背景下企业管理问题之我见"})
        types = {i["type"] for i in result["issues"]}
        self.assertIn("weak_title_word", types)
        self.assertGreater(result["stats"]["cjkChars"], 15)

    def test_check_title_from_markdown_h1(self):
        result = call_tool("check_title", {"markdown": "# Deep Learning\n\n正文。"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["stats"]["enWords"], 2)

    def test_audit_project_merges_chapters(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "01-intro.md"), "w", encoding="utf-8") as f:
                f.write("# 第1章 绪论\n\n本研究使用 LLM 技术分析。\n\n## 参考文献\n")
            with open(os.path.join(td, "02-method.md"), "w", encoding="utf-8") as f:
                f.write("# 第2章 方法\n\n样本 N=500，采用 t 检验，p=0.000。\n\n## 参考文献\n")
            out = call_tool("audit_project", {"project_dir": td, "genre": "empirical", "format": "json"})
            names = [r["file"] for r in out["files"]]
            self.assertEqual(names, ["01-intro.md", "02-method.md"])
            sec_names = {s["name"] for s in out["sections"]}
            self.assertIn("统计诚信", sec_names)
            stats_sec = next(s for s in out["sections"] if s["name"] == "统计诚信")
            self.assertTrue(any(i["type"] == "p_zero" for i in stats_sec["issues"]))

    def test_audit_project_missing_dir(self):
        result = call_tool("audit_project", {"project_dir": "Z:/no/such/dir"})
        text = result.get("note", "") if isinstance(result, dict) else str(result)
        self.assertIn("不存在", text)


class TestBomTolerance(unittest.TestCase):
    """Windows BOM 文件兼容：标题/引用正则不得因 \\ufeff 前缀失配。"""

    def test_structure_with_bom(self):
        r = call_tool("check_structure", {"markdown": "\ufeff# 标题\n\n## 二节\n\n正文内容。"})
        self.assertEqual(r["headings"][0]["title"], "标题")

    def test_intext_citations_with_bom(self):
        md = "\ufeff# 标题\n\n引用见[1]。\n\n## 参考文献\n\n- [1] A, B. (2020). Some real title here. J, 1(1), 1-2.\n"
        r = call_tool("check_intext_citations", {"markdown": md})
        self.assertNotIn("no_intext_citations", [i["type"] for i in r["issues"]])


class TestCli(unittest.TestCase):
    """CLI 入口（scripts/cli.py）：同一引擎的人用/CI 门面。"""

    def _run(self, argv):
        import cli

        buf = io.StringIO()
        err = io.StringIO()
        with mock.patch("sys.stdout", buf), mock.patch("sys.stderr", err):
            code = cli.main(argv)
        return code, buf.getvalue(), err.getvalue()

    def _write(self, td: str, name: str, text: str) -> str:
        p = os.path.join(td, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_version(self):
        code, out, _ = self._run(["version"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn(paper_tools.VERSION, out)

    def test_proofread_markdown_report(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            f = self._write(td, "p.md", "# 论文\n\n## 摘要\n\n研究检验。\n\n## 参考文献\n\nA, B. (2020). Enough title words here. J, 1(1), 1-2.\n")
            code, out, _ = self._run(["proofread", f])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("全文校对报告", out)

    def test_check_unknown_checker_exit_2(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            f = self._write(td, "p.md", "# T\n\n正文。")
            code, _, err = self._run(["check", "nope", f])
        self.assertEqual(code, cli.EXIT_INPUT_ERROR)
        self.assertIn("未知检查器", err)

    def test_missing_file_exit_2(self):
        code, _, err = self._run(["proofread", "Z:/no/such/file.md"])
        self.assertEqual(code, cli.EXIT_INPUT_ERROR)
        self.assertIn("不存在", err)

    def _mock_crossref(self, message: dict):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": message}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        return mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx)

    def test_verify_refs_gate_fails_on_c(self):
        import tempfile

        md = "# P\n\n引用[1]。\n\n## 参考文献\n\n- [1] A, B. (2099). Totally hallucinated title example. J, 1(1), 1-2.\n"
        with tempfile.TemporaryDirectory() as td:
            f = self._write(td, "p.md", md)
            msg = {"items": []}  # 标题检索无命中 -> C 级
            with self._mock_crossref(msg):
                code, _, _ = self._run(["verify-refs", f, "--fail-on", "C"])
        self.assertEqual(code, cli.EXIT_GATE_FAIL)

    def test_verify_refs_gate_passes_when_verified(self):
        import tempfile

        md = "# P\n\n引用[1]。\n\n## 参考文献\n\n- [1] R. Fickler. (2013). Quantum entanglement of macroscopic objects. Nature, 497(7448), 330-333. https://doi.org/10.1038/nature12373\n"
        with tempfile.TemporaryDirectory() as td:
            f = self._write(td, "p.md", md)
            msg = {
                "DOI": "10.1038/nature12373",
                "title": ["Quantum entanglement of macroscopic objects"],
                "author": [{"given": "R.", "family": "Fickler"}],
                "container-title": ["Nature"],
                "volume": "497",
                "issue": "7448",
                "page": "330-333",
                "issued": {"date-parts": [[2013]]},
            }
            with self._mock_crossref(msg):
                code, out, _ = self._run(["verify-refs", f, "--fail-on", "C"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("A=1", out)

    def test_citation_gbt_output(self):
        msg = {
            "DOI": "10.1038/nature14539",
            "title": ["Deep learning"],
            "author": [{"given": "Yann", "family": "LeCun"}],
            "container-title": ["Nature"],
            "volume": "521",
            "issue": "7553",
            "page": "436-444",
            "issued": {"date-parts": [[2015]]},
        }
        with self._mock_crossref(msg):
            code, out, _ = self._run(["citation", "10.1038/nature14539", "--style", "gbt"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("LECUN Y.", out)


class TestUniversalityV1280(unittest.TestCase):
    """v1.28.0 学科普适：MLA/Chicago 引用、humanities AI 画像、argumentative 体裁。"""

    def _mock_crossref(self, message: dict):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"message": message}).encode("utf-8")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = resp
        return mock.patch("paper_tools.urllib.request.urlopen", return_value=ctx)

    MSG: ClassVar[dict] = {
        "DOI": "10.1038/nature14539",
        "title": ["Deep learning"],
        "author": [{"given": "Yann", "family": "LeCun"}, {"given": "Yoshua", "family": "Bengio"}, {"given": "Geoffrey", "family": "Hinton"}],
        "container-title": ["Nature"],
        "volume": "521",
        "issue": "7553",
        "page": "436-444",
        "issued": {"date-parts": [[2015]]},
    }

    def test_format_citation_mla(self):
        with self._mock_crossref(self.MSG):
            out = call_tool("format_citation", {"doi": "10.1038/nature14539", "style": "mla"})
        self.assertIn('LeCun, Yann, et al. "Deep learning." Nature', out["text"])
        self.assertIn("vol. 521, no. 7553, 2015, pp. 436–444.", out["text"])

    def test_format_citation_chicago(self):
        with self._mock_crossref(self.MSG):
            out = call_tool("format_citation", {"doi": "10.1038/nature14539", "style": "chicago"})
        self.assertIn('LeCun, Yann, Yoshua Bengio, and Geoffrey Hinton. "Deep learning." Nature', out["text"])
        self.assertIn("Nature 521, no. 7553 (2015): 436–444.", out["text"])

    UNIFORM_TEXT = "本研究围绕核心概念展开分析。" * 30 + "It is worth noting that the framework remains consistent throughout. " * 12

    def test_ai_signature_humanities_mode_reduces_score(self):
        stem = call_tool("check_ai_signature", {"markdown": self.UNIFORM_TEXT})
        hum = call_tool("check_ai_signature", {"markdown": self.UNIFORM_TEXT, "style": "humanities"})
        self.assertEqual(hum["style"], "humanities")
        self.assertEqual(stem["style"], "stem")
        # 均匀句长/低 TTR 的文本在 humanities 模式下不应高于 stem 模式
        self.assertLessEqual(hum["score"], stem["score"])

    def test_ai_signature_default_is_stem(self):
        r = call_tool("check_ai_signature", {"markdown": self.UNIFORM_TEXT})
        self.assertEqual(r["style"], "stem")
        r2 = call_tool("check_ai_signature", {"markdown": self.UNIFORM_TEXT, "style": "quantitative-unknown"})
        self.assertEqual(r2["style"], "stem")

    def test_outline_argumentative(self):
        result = call_tool("generate_outline", {"topic": "数字劳动的异化问题", "genre": "argumentative"})
        text = result["text"]
        self.assertIn("论证体大纲", text)
        self.assertIn("对主要反驳的回应", text)
        self.assertIn("概念界定", text)

    def test_render_template_argumentative(self):
        result = call_tool("render_template", {"genre": "argumentative"})
        self.assertIn("## 四、对主要反驳的回应", result["text"])

    def test_check_sections_argumentative(self):
        md = (
            "# 论文\n\n## 一、问题的提出\n\n内容足够长的正文段落。\n\n"
            "## 二、概念界定与分析框架\n\n内容足够长的正文段落。\n\n"
            "## 三、论证主体\n\n内容足够长的正文段落。\n\n"
            "## 四、对主要反驳的回应\n\n内容足够长的正文段落。\n\n"
            "## 五、结论与限度\n\n关键词：论证、反驳。\n"
        )
        r = call_tool("check_sections", {"markdown": md, "genre": "argumentative"})
        missing = [i for i in r["issues"] if i["type"] == "missing_sections"]
        self.assertEqual(missing, [])


class TestSimRegressionsV1281(unittest.TestCase):
    """长程场景模拟（S1-S5）发现问题的回归测试。"""

    def test_cli_proofread_markdown_not_json_wrapped(self):
        """CLI 无 --json 时必须输出可读 Markdown 报告而非二次编码 JSON。"""
        import tempfile

        import cli

        with tempfile.TemporaryDirectory() as td:
            f = os.path.join(td, "p.md")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("# 论文\n\n## 摘要\n\n研究检验。\n\n## 参考文献\n\nA, B. (2020). Enough title words here. J, 1(1), 1-2.\n")
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = cli.main(["proofread", f])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertTrue(buf.getvalue().lstrip().startswith("# 全文校对报告"), "报告被二次编码为 JSON: " + buf.getvalue()[:80])

    def test_check_style_long_sentence_line_numbers_with_duplicates(self):
        """重复超长句的行号必须各自正确（旧实现 find() 恒报首次行号）。"""
        long_sent = "这一句话故意写得非常长用来验证同一句子在文中重复出现两次时各自的行号是否能够被正确地指向真实位置而不是全部指向首次出现的位置判定。"
        md = "# T\n\n" + long_sent + "\n\n中间普通句。\n\n" + long_sent + "\n"
        r = call_tool("check_style", {"markdown": md})
        lines = sorted(i["line"] for i in r["issues"] if i["type"] == "long_sentence")
        self.assertEqual(lines, [3, 7], f"行号错误: {lines}")

    def test_check_title_no_h1_returns_missing(self):
        """无 H1 且未传 title 时如实报缺，不拿首段冒充标题。"""
        r = call_tool("check_title", {"markdown": "这是一段没有标题开头的正文内容。"})
        types = {i["type"] for i in r["issues"]}
        self.assertIn("missing_title", types)

    def test_audit_project_short_text_ai_line_note(self):
        """合并文本过短时 AI 画像行显示原因，不出现 '?/100' 占位符。"""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "01.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# 第一章\n\n短内容。\n\n## 参考文献\n")
            result = call_tool("audit_project", {"project_dir": td})
            text = result["text"]
        self.assertNotIn("?/100", text)
        self.assertIn("未评估", text)

class TestAgentPrimitives(unittest.TestCase):
    """智能体动力原语：next_actions / gate_suite / audit_delta / brief 审计。"""

    DIRTY = '# 论文\n\n## 结果\n\n效果显著如表3所示（p=0.000）。\n'
    FIXED = '# 论文\n\n## 结果\n\n效果显著如表 1 所示。\n\n表 1：组间对比。\n'

    def test_next_actions_plans_are_ordered_and_complete(self):
        for goal, min_steps in (("submission", 6), ("thesis", 3), ("polish", 3)):
            r = call_tool("next_actions", {"goal": goal})
            self.assertTrue(r["steps"], goal)
            self.assertGreaterEqual(len(r["steps"]), min_steps, goal)
            orders = [s["order"] for s in r["steps"]]
            self.assertEqual(orders, list(range(1, len(r["steps"]) + 1)), goal)
            for s in r["steps"]:
                self.assertTrue(s["tool"] and s["pass"], s)

    def test_next_actions_unknown_goal_rejected(self):
        r = call_tool("next_actions", {"goal": "hacking"})
        self.assertFalse(r["ok"])
        self.assertIn("submission", r["note"])

    def test_gate_suite_fails_dirty_and_lists_blocking(self):
        bad = call_tool("gate_suite", {"markdown": self.DIRTY})
        self.assertFalse(bad["pass"])
        self.assertGreaterEqual(bad["totalErrors"], 1)
        self.assertTrue(bad["blocking"])
        gate_names = {g["gate"] for g in bad["gates"]}
        self.assertIn("stats", gate_names)
        self.assertIn("figures", gate_names)
        self.assertIn("numbers", gate_names)

    def test_gate_suite_subset_selection(self):
        r = call_tool("gate_suite", {"markdown": self.DIRTY, "gates": "style,numbers"})
        self.assertEqual({g["gate"] for g in r["gates"]}, {"style", "numbers"})

    def test_gate_suite_clean_document_passes(self):
        good = "# 移动学习对成绩的影响\n\n## 摘要\n\n本研究检验移动学习对成绩的影响，结果显著（p<0.001，Cohen's d=0.6）。\n\n## 引言\n\n已有研究 [1] 表明该方向值得深入研究。\n\n## 方法\n\n采用 t 检验分析数据。\n\n## 结果\n\n结果如表 1 所示。\n\n表 1：实验组与对照组对比。\n\n## 讨论\n\n结果与既有研究一致，样本有限需谨慎。\n\n## 结论\n\n研究结论支持假设。\n\n## 关键词\n\n移动学习；自主学习\n\n## 参考文献\n\n[1] Smith, J. (2020). Effects of mobile learning practice. Journal of Educational Technology, 15(2), 100-110.\n"
        r = call_tool("gate_suite", {"markdown": good})
        self.assertTrue(r["pass"], r["blocking"])
        self.assertEqual(r["totalErrors"], 0)

    def test_audit_delta_reports_net_improvement(self):
        d = call_tool("audit_delta", {"before": self.DIRTY, "after": self.FIXED})
        self.assertGreater(d["fixedCount"], 0)
        self.assertEqual(d["introducedCount"], 0)
        self.assertIn("净改善", d["verdict"])
        self.assertLess(d["errorsAfter"], d["errorsBefore"])

    def test_audit_delta_detects_regression(self):
        d = call_tool("audit_delta", {"before": self.FIXED, "after": self.DIRTY})
        self.assertGreater(d["introducedCount"], 0)
        self.assertIn("净退步", d["verdict"])

    def test_audit_paper_brief_mode_is_compact(self):
        raw = call_tool("audit_paper", {"markdown": self.DIRTY, "format": "json", "brief": True})
        self.assertFalse(raw["pass"])
        self.assertGreaterEqual(raw["errors"], 1)
        self.assertTrue(raw["blocking"])
        self.assertNotIn("sections", raw)


class TestPersonaEvalFixes(unittest.TestCase):
    """Persona 深度测评暴露的缺口回归：英文分桶/口径、重复句标题黏连、英文绝对词、文献区标点。"""

    def test_numbers_english_partition_overflow(self):
        md = (
            "## Methods\n\n"
            "We surveyed 320 patients with cancer, of whom 180 received therapy A, while 200 received chemotherapy alone.\n"
        )
        r = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "partition_sum_overflow" for i in r["issues"]), r["issues"])

    def test_numbers_english_partition_consistent_not_flagged(self):
        md = (
            "## Methods\n\n"
            "We surveyed 300 patients, of whom 180 received therapy A, while 120 received placebo.\n"
        )
        r = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "partition_sum_overflow" for i in r["issues"]), r["issues"])

    def test_numbers_english_sample_of_conflict(self):
        md = (
            "## Methods\n\nWe surveyed a sample of 250 employees.\n\n"
            "## Results\n\nThe final sample of 180 employees provided complete responses.\n"
        )
        r = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "sample_size_conflict" for i in r["issues"]), r["issues"])

    def test_duplicates_survive_headings_between_copies(self):
        sent = "Patients enriched for the stress state showed poorer progression-free survival."
        md = "# T\n\n" + sent + "\n\n## Discussion\n\n" + sent + "\n"
        r = call_tool("check_duplicates", {"markdown": md})
        self.assertTrue(any(i["type"] == "duplicate_sentence" for i in r["issues"]), r["issues"])

    def test_hedging_flags_english_absolute_terms(self):
        md = "## Discussion\n\nThis study undoubtedly establishes the mechanism.\n"
        r = call_tool("check_hedging", {"markdown": md})
        self.assertTrue(any(i["type"] == "absolute_term" and "undoubtedly" in i["detail"] for i in r["issues"]), r["issues"])

    def test_punctuation_ignores_references_section(self):
        md = "# 论文\n\n正文说明完整。\n\n## 参考文献\n\n[1] 张三. 论文标题研究[J]. 学报, 2021, 1(1): 1-10.\n"
        r = call_tool("check_punctuation", {"markdown": md})
        self.assertEqual(r["issues"], [])


class TestReferenceAndLinkIntegrity(unittest.TestCase):
    """文献完整性 / 时效性 / 占位符 / 链接可信 / 摘要-正文一致性 / 不可能统计值。"""

    def test_completeness_catches_gaps_and_bad_doi(self):
        md = (
            "## 参考文献\n\n"
            "[1] 张三. 一篇没有来源的论文 (2020).\n"
            "[2] Smith, J. (2021). A study with bad doi. Journal, 15(2), 100-110. doi:10.12/bad\n"
            "[3] 王五. (2023). 缺页码的文献. 学报.\n"
        )
        r = call_tool("check_references_completeness", {"markdown": md})
        types = {i["type"] for i in r["issues"]}
        self.assertIn("missing_source", types)
        self.assertIn("missing_type_marker", types)
        self.assertIn("malformed_doi", types)
        self.assertIn("missing_pages", types)

    def test_completeness_clean_entries_pass(self):
        md = "## 参考文献\n\n[1] 李四. 移动学习研究[J]. 现代教育技术, 32(4), 45-52.\n"
        r = call_tool("check_references_completeness", {"markdown": md})
        self.assertEqual([i for i in r["issues"] if i["severity"] != "info"], [], r["issues"])

    def test_recency_flags_all_stale(self):
        md = (
            "## 参考文献\n\n"
            "[1] A. (1998). Old one here. J, 1, 1-2.\n"
            "[2] B. (2001). Old two here. J, 1, 1-2.\n"
            "[3] C. (2005). Old three here. J, 1, 1-2.\n"
            "[4] D. (2010). Old four here. J, 1, 1-2.\n"
        )
        r = call_tool("check_references_recency", {"markdown": md})
        self.assertTrue(any(i["type"] == "stale_references" for i in r["issues"]), r["issues"])

    def test_placeholders_caught(self):
        md = "# 论文\n\n方法部分待补充。\n结果见表 TODO。\n"
        r = call_tool("check_placeholders", {"markdown": md})
        details = " ".join(i["detail"] for i in r["issues"])
        self.assertIn("TODO", details)
        self.assertIn("待补充", details)

    def test_links_offline_catches_fake_hosts(self):
        md = (
            "# 论文\n\n详见 https://example.com/paper 与 http://localhost/x 和 "
            "https://site.invalid/a 以及真实形态的 https://journal.example.edu/article。\n"
        )
        r = call_tool("check_links", {"markdown": md})
        types = {i["type"] for i in r["issues"]}
        self.assertIn("placeholder_url", types)
        self.assertIn("malformed_url", types)
        # 合法形态的 .edu 链接不应被报
        self.assertFalse(any("journal.example.edu" in i["detail"] for i in r["issues"]), r["issues"])

    def test_numbers_abstract_body_mismatch(self):
        md = (
            "## 摘要\n\n本研究调查了250名学生的移动学习行为。\n\n"
            "## 方法\n\n我们招募了300名学生参与本研究。\n"
        )
        r = call_tool("check_numbers", {"markdown": md})
        self.assertTrue(any(i["type"] == "abstract_number_mismatch" for i in r["issues"]), r["issues"])

    def test_numbers_abstract_body_consistent_not_flagged(self):
        md = (
            "## 摘要\n\n本研究调查了300名学生的移动学习行为。\n\n"
            "## 方法\n\n我们招募了300名学生参与本研究。\n"
        )
        r = call_tool("check_numbers", {"markdown": md})
        self.assertFalse(any(i["type"] == "abstract_number_mismatch" for i in r["issues"]), r["issues"])

    def test_stats_impossible_values(self):
        md = "## 结果\n\n变量相关显著（r=1.35），且 Cohen's d=8.2，效果极大。\n"
        r = call_tool("check_stats", {"markdown": md})
        types = {i["type"] for i in r["issues"]}
        self.assertIn("r_out_of_range", types)
        self.assertIn("implausible_effect_size", types)


class TestVagueAttribution(unittest.TestCase):
    """模糊归因：无引注的'研究表明/experts say'须报，同句有引注须豁免。"""

    def test_vague_without_citation_flagged(self):
        md = "## 引言\n\n有研究表明该效应在不同群体中均稳健。\n人们普遍认为这一方向具有前景。\n"
        r = call_tool("check_vague_attribution", {"markdown": md})
        details = " ".join(i["detail"] for i in r["issues"])
        self.assertIn("有研究表明", details)
        self.assertIn("人们普遍认为", details)

    def test_english_vague_flagged(self):
        md = "## Introduction\n\nExperts agree that this approach works well across contexts.\n"
        r = call_tool("check_vague_attribution", {"markdown": md})
        self.assertTrue(any("experts agree" in i["detail"].lower() for i in r["issues"]), r["issues"])

    def test_citation_in_sentence_exempt(self):
        md = (
            "## 引言\n\n研究表明移动学习能提升成绩 [1]。\n"
            "有研究表明该效应稳健（王五，2021）。\n"
            "Research suggests the effect replicates (Smith, 2020).\n"
        )
        r = call_tool("check_vague_attribution", {"markdown": md})
        self.assertEqual([i for i in r["issues"] if i["type"] == "vague_attribution"], [], r["issues"])


if __name__ == "__main__":
    unittest.main()

