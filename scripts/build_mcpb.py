"""构建 ScholarSeed 的 .mcpb 包（Smithery/Anthropic MCP Server Bundle 格式）。"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
version = plugin["version"]

manifest = {
    "manifest_version": "0.2",
    "name": "scholarseed",
    "display_name": "ScholarSeed",
    "version": version,
    "description": plugin["description"],
    "author": {"name": plugin["author"]["name"], "url": plugin["author"].get("url", "")},
    "license": "PolyForm-Noncommercial-1.0.0",
    "repository": plugin.get("repository", ""),
    "keywords": plugin.get("keywords", []),
    "server_type": "python",
    "server": {
        "type": "python",
        "entry_point": "scripts/paper_tools.py",
        "mcp_config": {
            "command": "python",
            "args": ["${__dirname}/scripts/paper_tools.py"],
        },
    },
    "compatibility": {
        "platforms": ["win32", "darwin", "linux"],
        "runtimes": {"python": ">=3.9"},
    },
}

dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
out = dist / f"ScholarSeed-{version}.mcpb"

include_files = [
    "plugin.json", "mcp.json", "smithery.yaml", "README.md", "README.zh-CN.md",
    "LICENSE", "CHANGELOG.md", "SECURITY.md",
]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    for rel in include_files:
        p = ROOT / rel
        if p.exists():
            zf.write(p, rel)
    for folder in ("scripts", "skills", "data"):
        d = ROOT / folder
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file() and "__pycache__" not in str(f):
                    zf.write(f, f.relative_to(ROOT).as_posix())

print(f"built: {out.name} ({out.stat().st_size} bytes)")
