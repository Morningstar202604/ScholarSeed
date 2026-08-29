"""arXiv 多学科语料下载器：每类取 N 篇近期论文的 e-print 源码。

礼貌策略：请求间隔 >=3 秒；支持断点续传（已存在文件跳过）。
产出：{out}/{cat}/{id}.tar.gz + manifest.jsonl
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("corpus_raw")
PER_CAT = int(sys.argv[2]) if len(sys.argv) > 2 else 8

CATEGORIES = [
    "cs.CL", "cs.CV", "cs.LG",
    "stat.AP", "econ.GN", "q-bio.NC",
    "gr-qc", "cond-mat.mtrl-sci", "math.CO",
]
UA = {"User-Agent": "Mozilla/5.0 (ScholarSeed-corpus-builder; academic QA research)"}


def api_ids(cat: str, n: int) -> list:
    url = (f"https://export.arxiv.org/api/query?search_query=cat:{cat}"
           f"&start=0&max_results={n}&sortBy=submittedDate")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        xml = r.read().decode("utf-8", errors="replace")
    ids = re.findall(r"<id>https?://arxiv.org/abs/([^<]+)</id>", xml)
    return [i.split("v")[0] for i in ids]


def fetch_eprint(pid: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    try:
        req = urllib.request.Request(f"https://arxiv.org/e-print/{pid}", headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
    except Exception as e:
        print(f"  FAIL {pid}: {e}")
        return False
    if data[:5] == b"%PDF-" or b"<html" in data[:200].lower():
        print(f"  SKIP {pid}: PDF-only 或被拦截")
        return False
    dest.write_bytes(data)
    return True


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.jsonl"
    done = set()
    if manifest_path.exists():
        for ln in manifest_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(ln)["id"])
            except Exception:
                pass

    with manifest_path.open("a", encoding="utf-8") as mf:
        for cat in CATEGORIES:
            cdir = OUT / cat.replace(".", "_")
            cdir.mkdir(parents=True, exist_ok=True)
            print(f"== {cat} ==")
            try:
                ids = api_ids(cat, PER_CAT * 2)  # 多取一倍冗余，跳过失败项
            except Exception as e:
                print(f"  API 失败: {e}")
                continue
            got = 0
            for pid in ids:
                if got >= PER_CAT:
                    break
                safe = pid.replace("/", "_")
                if safe in done:
                    got += 1
                    continue
                time.sleep(3)  # arXiv 礼貌延迟
                ok = fetch_eprint(pid, cdir / f"{safe}.tar.gz")
                mf.write(json.dumps({"id": pid, "category": cat,
                                     "downloaded": ok}, ensure_ascii=False) + "\n")
                mf.flush()
                done.add(safe)
                if ok:
                    got += 1
                    print(f"  OK {pid} ({got}/{PER_CAT})")
            print(f"  小计 {got}")


if __name__ == "__main__":
    main()
