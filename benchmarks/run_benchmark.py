r"""基准跑批器：解包 arXiv 语料 → \input 合并 → 全量审计 → JSONL + 分布汇总。"""
import gzip
import io
import json
import re
import sys
import tarfile
import tempfile
import time
from collections import Counter
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import paper_tools as pt  # noqa: E402  # 需先注入仓库 scripts 路径

BASE = Path(tempfile.gettempdir()) / "scholarseed-v2"
OUT_JSONL = Path(r"D:\github\ScholarSeed\benchmarks\results\corpus_results.jsonl")
GENRE_BY_CAT = {
    "cs.CL": "tech", "cs.CV": "tech", "cs.LG": "tech",
    "stat.AP": "empirical", "econ.GN": "empirical", "q-bio.NC": "empirical",
    "gr-qc": "tech", "cond_mat_mtrl_sci": "tech", "math_CO": "tech",
}


def extract_any(src: Path, dest: Path):
    raw = src.read_bytes()
    dest.mkdir(parents=True, exist_ok=True)
    if raw[:2] != b"\x1f\x8b":
        return []
    try:
        data = gzip.decompress(raw)
    except Exception:
        return []
    if len(data) > 262 and (b"ustar" in data[257:263] or b"GNU" in data[257:265]):
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(dest)
        return list(dest.rglob("*.tex"))
    suffix = ".tex" if (b"\\documentclass" in data or b"\\section" in data) else ""
    if suffix:
        out = dest / "main.tex"
        out.write_bytes(data)
        return [out]
    return []


def resolve_inputs(main_tex: str, base_dir: Path, depth: int = 0) -> str:
    r"""一层 \input/\include 展开：多文件工程合并为单文本。"""

    def repl(m):
        name = m.group(1).strip()
        if not name.endswith(".tex"):
            name += ".tex"
        cand = None
        for c in base_dir.rglob(Path(name).name):
            cand = c
            break
        if cand is None or depth > 2:
            return f"% [missing input {m.group(1)}]"
        sub = cand.read_text(encoding="utf-8", errors="replace")
        return resolve_inputs(sub, cand.parent, depth + 1)

    t = re.sub(r"\\(?:input|include)\{([^}]+)\}", repl, main_tex)
    return t


def find_main(texs):
    for f in texs:
        try:
            if "\\documentclass" in f.read_text(encoding="utf-8", errors="replace"):
                return f
        except Exception:
            continue
    return max(texs, key=lambda f: f.stat().st_size)


def main():
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    t0 = time.time()
    n_ok = n_skip = 0
    for gz in sorted(BASE.glob("*/*.tar.gz")):
        cat_key = gz.parent.name.replace("_", ".") if "_" in gz.parent.name else gz.parent.name
        # 目录名形如 cs_CL / cond_mat_mtrl_sci；映射回类别键
        cat = None
        for known in GENRE_BY_CAT:
            if known.replace(".", "_") == gz.parent.name:
                cat = known
                break
        cat = cat or cat_key
        pid = gz.stem.replace(".tar", "")
        work = BASE / "_work_" / pid
        texs = extract_any(gz, work)
        if not texs:
            n_skip += 1
            continue
        mainf = find_main(texs)
        try:
            raw = mainf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            n_skip += 1
            continue
        merged = resolve_inputs(raw, mainf.parent)
        genre = GENRE_BY_CAT.get(cat, "tech")
        try:
            out = pt.audit_paper(merged, genre=genre, fmt="json", source_format="latex")
            d = json.loads(out)
        except Exception as e:
            rows.append({"id": pid, "category": cat, "error": repr(e)[:200]})
            with OUT_JSONL.open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            continue
        types = Counter()
        for sec in d["sections"]:
            for i in sec["issues"]:
                types[i["type"]] += 1
        rows.append({
            "id": pid, "category": cat, "score": d["score"],
            "errors": d["summary"]["errors"], "warnings": d["summary"]["warnings"],
            "infos": d["summary"]["infos"],
            "aiScore": d["aiSignature"].get("score"),
            "aiBand": d["aiSignature"].get("band"),
            "chars": len(merged), "issueTypes": dict(types),
            "secs": round(time.time() - t0, 1),
        })
        n_ok += 1
        print(f"[{n_ok}] {cat} {pid}: {d['score']} 分 "
              f"(E{d['summary']['errors']}/W{d['summary']['warnings']}/I{d['summary']['infos']} "
              f"AI={d['aiSignature'].get('band')})")

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    ok_rows = [r for r in rows if "score" in r]
    print("\n===== 汇总 =====")
    print(f"成功 {len(ok_rows)} / 跳过 {n_skip} | 总耗时 {time.time()-t0:.0f}s")
    if not ok_rows:
        return
    scores = sorted(r["score"] for r in ok_rows)
    n = len(scores)
    med = scores[n // 2]
    mean = sum(scores) / n
    bands = Counter(r["aiBand"] for r in ok_rows)
    print(f"分数: min={scores[0]} 中位={med} 均值={mean:.1f} max={scores[-1]}")
    dist = Counter()
    for s in scores:
        dist[s // 20 * 20] += 1
    print("分布(每20分桶): ", dict(sorted(dist.items())))
    print("AI 档位分布:", dict(bands))
    err_total = sum(r["errors"] for r in ok_rows)
    warn_total = sum(r["warnings"] for r in ok_rows)
    print(f"ERROR 合计 {err_total} | WARNING 合计 {warn_total}")
    type_tot = Counter()
    for r in ok_rows:
        for k, v in r["issueTypes"].items():
            type_tot[k] += v
    print("TOP 问题类型:", sorted(type_tot.items(), key=lambda x: -x[1])[:12])


if __name__ == "__main__":
    main()
