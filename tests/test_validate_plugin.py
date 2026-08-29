"""validate_plugin.py 检查项的单元测试。

覆盖：
- 版本单一来源（paper_tools.py 禁止硬编码 VERSION 字面量，v1.10.0 起）
- CHANGELOG 最新版本与 plugin.json 一致性
- return 后不可达死代码检测（AST）
- 词数口径声明（README 须含"不含参考文献"）

运行方式（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import validate_plugin


def _make_root() -> Path:
    """构造一个含合法 plugin.json / paper_tools.py / README.md 的最小插件目录。

    paper_tools.py 使用动态版本读取（VERSION = _load_version()），符合 v1.10.0 规范。
    """
    root = Path(tempfile.mkdtemp(prefix="ScholarSeed-ut-"))
    (root / "scripts").mkdir(parents=True)
    (root / "plugin.json").write_text(
        json.dumps({"name": "ScholarSeed", "version": "1.7.0", "license": "Apache-2.0"}),
        encoding="utf-8",
    )
    (root / "scripts" / "paper_tools.py").write_text(
        'SERVER_NAME = "paper-tools"\n'
        'VERSION = _load_version()\n'
        '\n'
        'def _load_version():\n'
        '    return "1.7.0"\n'
        '\n'
        'def f():\n'
        '    return 1\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("word_count 统计口径：正文词数不含参考文献。", encoding="utf-8")
    return root


class TestVersionConsistency(unittest.TestCase):
    def test_dynamic_version_passes(self):
        root = _make_root()
        errors = []
        validate_plugin._validate_version_consistency(root, errors)
        self.assertEqual(errors, [])

    def test_hardcoded_version_literal_fails(self):
        root = _make_root()
        (root / "scripts" / "paper_tools.py").write_text(
            'SERVER_NAME = "paper-tools"\nVERSION = "1.7.0"\n\ndef f():\n    return 1\n',
            encoding="utf-8",
        )
        errors = []
        validate_plugin._validate_version_consistency(root, errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("硬编码", errors[0])


class TestDeadCode(unittest.TestCase):
    def test_dead_code_lines_detected(self):
        src = (
            "def ok():\n"
            "    return 1\n"
            "def bad():\n"
            "    return 1\n"
            "    print('unreachable')\n"
        )
        hits = validate_plugin._dead_code_lines(ast.parse(src))
        self.assertEqual(hits, [5])

    def test_validate_dead_code_flags_error(self):
        root = _make_root()
        (root / "scripts" / "paper_tools.py").write_text(
            'VERSION = "1.7.0"\n\ndef f():\n    return 1\n    x = 2\n',
            encoding="utf-8",
        )
        errors = []
        validate_plugin._validate_dead_code(root, errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("不可达代码", errors[0])

    def test_validate_dead_code_clean_passes(self):
        root = _make_root()
        errors = []
        validate_plugin._validate_dead_code(root, errors)
        self.assertEqual(errors, [])


class TestWordcountCaliber(unittest.TestCase):
    def test_readme_declares_caliber_passes(self):
        root = _make_root()
        errors = []
        validate_plugin._validate_wordcount_caliber(root, errors)
        self.assertEqual(errors, [])

    def test_readme_missing_caliber_fails(self):
        root = _make_root()
        (root / "README.md").write_text("word_count 统计词数。", encoding="utf-8")
        errors = []
        validate_plugin._validate_wordcount_caliber(root, errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("词数", errors[0])


class TestChangelogVersion(unittest.TestCase):
    def test_changelog_matching_passes(self):
        root = _make_root()
        (root / "CHANGELOG.md").write_text(
            "## [1.7.0] - 2026-08-20\n- 新增 CHANGELOG 版本一致性检查。\n", encoding="utf-8"
        )
        errors = []
        validate_plugin._validate_changelog_version(root, errors)
        self.assertEqual(errors, [])

    def test_changelog_drift_fails(self):
        root = _make_root()
        (root / "CHANGELOG.md").write_text(
            "## [1.8.0] - 2026-09-01\n- 计划中的升级。\n", encoding="utf-8"
        )
        errors = []
        validate_plugin._validate_changelog_version(root, errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("CHANGELOG 最新版本", errors[0])

    def test_no_changelog_passes(self):
        root = _make_root()
        errors = []
        validate_plugin._validate_changelog_version(root, errors)
        self.assertEqual(errors, [])


class TestVersionBumpType(unittest.TestCase):
    """SemVer 升版纪律：无 Added 段不得提升次版本号（v1.20.1 起）。"""

    def _changelog(self, root, body):
        (root / "CHANGELOG.md").write_text(body, encoding="utf-8")

    def test_fix_only_minor_bump_fails(self):
        root = _make_root()
        self._changelog(root,
            "## [1.21.0] - 2026-08-22\n\n### Fixed\n\n- 修复若干。\n\n"
            "## [1.20.0] - 2026-08-21\n\n### Added\n\n- 功能。\n")
        errors = []
        validate_plugin._validate_version_bump_type(root, errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("Added 段", errors[0])

    def test_added_minor_bump_passes(self):
        root = _make_root()
        self._changelog(root,
            "## [1.21.0] - 2026-08-22\n\n### Added\n\n- 新工具。\n\n"
            "## [1.20.0] - 2026-08-21\n\n### Added\n\n- 功能。\n")
        errors = []
        validate_plugin._validate_version_bump_type(root, errors)
        self.assertEqual(errors, [])

    def test_fix_patch_bump_passes(self):
        root = _make_root()
        self._changelog(root,
            "## [1.20.1] - 2026-08-22\n\n### Fixed\n\n- 修复。\n\n"
            "## [1.20.0] - 2026-08-21\n\n### Added\n\n- 功能。\n")
        errors = []
        validate_plugin._validate_version_bump_type(root, errors)
        self.assertEqual(errors, [])

    def test_single_entry_skipped(self):
        root = _make_root()
        self._changelog(root, "## [1.0.0] - 2026-01-01\n\n### Added\n\n- 初始。\n")
        errors = []
        validate_plugin._validate_version_bump_type(root, errors)
        self.assertEqual(errors, [])


if __name__ == "__main__":

    unittest.main()
