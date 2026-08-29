#!/usr/bin/env python3
# Copyright 2026 ScholarSeed contributors
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE.
# Commercial use requires a separate license from the maintainers.
"""ScholarSeed 插件规范校验器。

校验插件包是否符合 Agent Plugins 1.0 目录规范：
- plugin.json 必填项（$schema + name）与字段合法性
- mcp.json 结构
- skills/ 目录结构与 SKILL.md frontmatter
- 路径不越界
- 构建产物残留
- 文档与代码能力一致性（README/CHANGELOG 工具声明 vs 代码注册）
- 版本单一来源（plugin.json 为唯一版本声明处，paper_tools.py 禁止硬编码 VERSION 字面量）
- CHANGELOG 版本一致性
- 死代码检测（AST 扫描 return 后不可达语句）
- 词数口径声明（README 须写明"不含参考文献"）
- SemVer 升版纪律（无 Added 段不得提升次版本号，v1.20.1 起）

用法：
    python scripts/validate_plugin.py [插件根目录]
默认校验本仓库根目录。

返回码：0 = 通过，1 = 存在失败项。
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

PLUGIN_JSON_REQUIRED = ("$schema", "name")
PLUGIN_JSON_KNOWN = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SCHEMA_IDS = (
    "https://storage.googleapis.com/plugins-schema/plugin.schema.json",
    "https://schema.plugins.agent.build/plugin.json",
    "https://schema.plugins.agent.build/plugin.schema.json",
    "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
)

SKILL_FRONTMATTER_REQUIRED = ("name", "description")


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _validate_plugin_json(root: Path, errors: list, warnings: list) -> None:
    path = root / "plugin.json"
    if not path.exists():
        errors.append("缺少 plugin.json")
        return
    data = _load_json(path)
    for field in PLUGIN_JSON_REQUIRED:
        if not data.get(field):
            errors.append(f"plugin.json 缺少必填字段: {field}")
    if "$schema" in data and data["$schema"] not in SCHEMA_IDS:
        warnings.append(f"plugin.json $schema 不在已知版本列表中: {data['$schema']}")
    name = data.get("name")
    if name and not NAME_PATTERN.match(name):
        errors.append(f"plugin.json name 非法（应匹配 {NAME_PATTERN.pattern}）: {name}")
    unknown = set(data) - PLUGIN_JSON_KNOWN
    if unknown:
        warnings.append(f"plugin.json 含未知字段（需人工确认是否规范允许）: {sorted(unknown)}")


def _validate_mcp_json(root: Path, errors: list, warnings: list) -> None:
    path = root / "mcp.json"
    if not path.exists():
        errors.append("缺少 mcp.json")
        return
    data = _load_json(path)
    if not data.get("$schema"):
        errors.append("mcp.json 缺少 $schema 字段")
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        errors.append("mcp.json 缺少非空 mcpServers 对象")
        return
    for server_name, cfg in servers.items():
        if not isinstance(cfg, dict):
            errors.append(f"mcp.json 服务器 {server_name} 配置非法")
            continue
        server_type = cfg.get("type", "stdio")
        if server_type not in {"stdio", "http", "sse"}:
            warnings.append(f"mcp.json 服务器 {server_name} 的 type 未知（规范枚举 stdio/http/sse）: {server_type}")
        if server_type == "stdio":
            if not cfg.get("command"):
                errors.append(f"mcp.json 服务器 {server_name} 缺少 command（stdio 型必填且非空）")
            if "cwd" not in cfg:
                warnings.append(f"mcp.json 服务器 {server_name} 缺少 cwd（建议指向 ${{PLUGIN_ROOT}}）")
        elif not cfg.get("url"):
            errors.append(f"mcp.json 服务器 {server_name} 缺少 url（非 stdio 型必填且非空）")


def _validate_skills(root: Path, errors: list, warnings: list) -> None:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        errors.append("缺少 skills/ 目录")
        return
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            warnings.append(f"skills/ 下存在非目录项: {skill_dir.name}")
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"技能 {skill_dir.name} 缺少 SKILL.md")
            continue
        text = skill_md.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text)
        for field in SKILL_FRONTMATTER_REQUIRED:
            if not frontmatter.get(field):
                errors.append(f"技能 {skill_dir.name} 的 SKILL.md 缺少 frontmatter 字段: {field}")
        for path in skill_dir.rglob("*"):
            if any(part in {"__pycache__", ".git", ".venv"} for part in path.parts):
                errors.append(f"技能目录含不应存在的文件: {path.relative_to(root)}")


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def _validate_no_traversal(root: Path, errors: list) -> None:
    for path in root.rglob("*"):
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"检测到越界路径: {path}")


def _validate_no_build_artifacts(root: Path, errors: list) -> None:
    """检查真正的分发产物污染。

    __pycache__/*.pyc 是解释器临时缓存：任何一次 import 都会重新生成，
    对其报错只会制造"跑完测试再单独校验就红"的假阳性（release_gate 已
    在校验前清理，这里对缓存类条目直接豁免，避免开发者本地误报）。
    .pytest_cache / .venv / node_modules 等仍是需要报告的真实污染源。
    """
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if any(part in {".pytest_cache", ".venv", "node_modules"} for part in rel.parts):
            errors.append(f"插件含不应存在的构建产物目录: {rel}")


def _registered_tools(tools_py: Path) -> set:
    """用 AST 解析 paper_tools.py 中 TOOLS 注册的工具名。"""
    tree = ast.parse(tools_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if "TOOLS" not in targets or not isinstance(node.value, ast.List):
            continue
        names = set()
        for item in node.value.elts:
            if not isinstance(item, ast.Dict):
                continue
            for key, value in zip(item.keys, item.values):
                if isinstance(key, ast.Constant) and key.value == "name" and isinstance(value, ast.Constant):
                    names.add(value.value)
        return names
    return set()


def _validate_declared_capabilities(root: Path, errors: list, warnings: list) -> None:
    """文档声称的工具能力 vs 代码注册工具的一致性检查（防文档与实现脱节）。

    - README「MCP 工具」表与 CHANGELOG 中"`工具名` 工具"声称的能力，代码必须已实现；
    - 代码已注册但 README 工具表未声明的，给出警告。
    """
    tools_py = root / "scripts" / "paper_tools.py"
    if not tools_py.exists():
        warnings.append("scripts/paper_tools.py 不存在，跳过能力一致性检查")
        return
    registered = _registered_tools(tools_py)
    if not registered:
        warnings.append("scripts/paper_tools.py 中未解析到 TOOLS 注册名，跳过能力一致性检查")
        return

    declared: set = set()
    readme = root / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        m = re.search(r"## MCP 工具(.*?)(?=\n## )", text, flags=re.S)
        table = m.group(1) if m else text
        declared |= set(re.findall(r"^\|\s*`([a-z_]{3,})`", table, flags=re.M))
    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        declared |= set(re.findall(r"`([a-z_]{3,})`\s*工具", changelog.read_text(encoding="utf-8")))

    missing = declared - registered
    if missing:
        errors.append(f"文档声称但代码未实现的工具: {sorted(missing)}")
    undocumented = registered - declared
    if undocumented:
        warnings.append(f"代码已注册但文档未声明的工具: {sorted(undocumented)}")


def _server_version(tools_py: Path) -> str | None:
    """用 AST 读取 paper_tools.py 的 VERSION 常量（仅当为字面量时返回）。"""
    tree = ast.parse(tools_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if "VERSION" in targets and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


def _validate_version_consistency(root: Path, errors: list) -> None:
    """版本号单一来源：plugin.json 是唯一版本声明处。

    paper_tools.py 的 VERSION 必须从 plugin.json 动态读取（如 _load_version()），
    禁止硬编码字面量——字面量必然随升版漂移，是历史反复脱节的根源。
    """
    tools_py = root / "scripts" / "paper_tools.py"
    if not tools_py.exists():
        return
    hardcoded = _server_version(tools_py)
    if hardcoded is not None:
        errors.append(f"paper_tools.py 硬编码了 VERSION = '{hardcoded}'；版本号必须从 plugin.json 动态读取（单一来源），请删除该字面量")


def _validate_changelog_version(root: Path, errors: list) -> None:
    """CHANGELOG.md 最新版本号必须与 plugin.json.version 一致。

    覆盖场景：文档声称升版而 plugin.json / 代码未同步（或反之），
    仅靠 plugin.json-vs-代码 双比较无法发现的三方脱节。
    """
    changelog = root / "CHANGELOG.md"
    plugin_path = root / "plugin.json"
    if not changelog.exists() or not plugin_path.exists():
        return
    pv = str(_load_json(plugin_path).get("version", ""))
    if not pv:
        return
    m = re.search(r"^## \[([^\]]+)\]", changelog.read_text(encoding="utf-8"), flags=re.M)
    if not m:
        return
    latest = m.group(1).strip()
    if latest != pv:
        errors.append(f"CHANGELOG 最新版本[{latest}] 与 plugin.json[{pv}] 不一致")


def _dead_code_lines(tree: ast.AST) -> list:
    """扫描各语句块，return/raise 之后出现的语句为不可达死代码，返回行号列表。"""
    hits = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not (isinstance(body, list) and body and all(isinstance(s, ast.stmt) for s in body)):
            continue
        unreachable = False
        for stmt in body:
            if unreachable:
                hits.append(stmt.lineno)
            if isinstance(stmt, (ast.Return, ast.Raise)):
                unreachable = True
    return sorted(set(hits))


def _validate_dead_code(root: Path, errors: list) -> None:
    """AST 扫描 paper_tools.py，检测函数内 return 之后的不可达死代码（防历史返工）。"""
    tools_py = root / "scripts" / "paper_tools.py"
    if not tools_py.exists():
        return
    lines = _dead_code_lines(ast.parse(tools_py.read_text(encoding="utf-8")))
    if lines:
        errors.append(f"paper_tools.py 存在 return 后不可达代码（行号 {lines}），请删除")


def _validate_wordcount_caliber(root: Path, errors: list) -> None:
    """词数口径统一：README 必须声明"正文统计不含参考文献"的约定。

    主 README 或中文版 README.zh-CN.md 任一包含该口径声明即通过
    （英文主文档可用 'references excluded' 表述）。
    """
    candidates = [root / "README.md", root / "README.zh-CN.md"]
    markers = ("不含参考文献", "references excluded")
    found = False
    for cand in candidates:
        if not cand.exists():
            continue
        text = cand.read_text(encoding="utf-8")
        if any(mk in text for mk in markers):
            found = True
            break
    if not found:
        errors.append("README 未声明词数统计口径（须写明：正文词数统计不含参考文献 / references excluded）")


JOURNAL_DB_REQUIRED_FIELDS = ("name", "type", "domains", "position", "length", "note")


def _validate_journal_db(root: Path, errors: list) -> None:
    """期刊库数据文件校验：必须为对象数组，每条含匹配所需字段（防手改数据破坏 journal_matcher）。"""
    path = root / "data" / "journals.json"
    if not path.exists():
        errors.append("缺少 data/journals.json（journal_matcher 的期刊库数据源）")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        errors.append(f"data/journals.json 不是合法 JSON: {e}")
        return
    if not isinstance(data, list) or not data:
        errors.append("data/journals.json 必须是非空数组")
        return
    for i, entry in enumerate(data, 1):
        if not isinstance(entry, dict):
            errors.append(f"data/journals.json 第 {i} 条不是对象")
            continue
        missing = [f for f in JOURNAL_DB_REQUIRED_FIELDS if f not in entry]
        if missing:
            errors.append(f"data/journals.json 第 {i} 条（{entry.get('name', '?')}）缺字段: {missing}")


def _validate_version_bump_type(root: Path, errors: list) -> None:
    """SemVer 升版纪律：最新条目若无 Added 段（仅修复/杂务），不得提升次版本号。

    需要至少两个 CHANGELOG 版本条目；不足时跳过。
    """
    path = root / "CHANGELOG.md"
    if not path.exists():
        return
    entries = re.findall(r"^## \[([^\]]+)\] - ([\d-]+)\s*$(.*?)(?=^## \[|\Z)", path.read_text(encoding="utf-8"), flags=re.M | re.S)
    if len(entries) < 2:
        return

    def _semver(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return None

    latest_v, _, latest_body = entries[0]
    prev_v = entries[1][0]
    cur, prev = _semver(latest_v), _semver(prev_v)
    if not cur or not prev:
        return
    has_added = bool(re.search(r"^###\s+Added", latest_body, flags=re.M))
    minor_bumped = (cur[0], cur[1]) > (prev[0], prev[1])
    major_bumped = cur[0] > prev[0]
    if minor_bumped and not major_bumped and not has_added:
        errors.append(f"版本 {latest_v} 相对 {prev_v} 提升了次版本号，但该条目没有 Added 段（纯修复/杂务应为 patch 级）——违反 CONTRIBUTING 版本号规范")


def validate(root: Path) -> bool:
    errors: list = []
    warnings: list = []
    _validate_plugin_json(root, errors, warnings)
    _validate_mcp_json(root, errors, warnings)
    _validate_skills(root, errors, warnings)
    _validate_no_traversal(root, errors)
    _validate_no_build_artifacts(root, errors)
    _validate_declared_capabilities(root, errors, warnings)
    _validate_version_consistency(root, errors)
    _validate_changelog_version(root, errors)
    _validate_dead_code(root, errors)
    _validate_wordcount_caliber(root, errors)
    _validate_journal_db(root, errors)
    _validate_version_bump_type(root, errors)

    print(f"校验目录: {root.resolve()}")
    print("-" * 50)
    if not errors and not warnings:
        print("PASS: 全部检查通过")
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")
    print("-" * 50)
    print(f"结果: {len(errors)} 失败 / {len(warnings)} 警告")
    return not errors


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    sys.exit(0 if validate(root) else 1)
