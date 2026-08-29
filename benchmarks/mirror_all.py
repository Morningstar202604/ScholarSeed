"""全项目镜像同步编排器：GitHub(源) -> Gitee + GitCode。

- 仅处理非 fork、非归档仓库
- 裸镜像克隆（含全部分支与标签）后 push --mirror 到两平台
- 缺库自动创建（公开）；创建后再 PATCH 补描述与公开态
- 断点续传：sync_log.jsonl 记录已完成的 (repo, platform)
"""
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

GH_USER = "Morningstar202604"
GITEE_USER = "badhope"
# 凭据一律从环境变量读取，严禁硬编码（ see SECURITY.md）
GITEE_TOKEN = os.environ.get("TRAVELER_GITEE_TOKEN", os.environ.get("GITEE_TOKEN", ""))
GITCODE_TOKEN = os.environ.get("TRAVELER_GITCODE_TOKEN", os.environ.get("GITCODE_TOKEN", ""))
WORK = Path(tempfile.gettempdir()) / "scholarseed-mirror-work"
LOG = WORK / "sync_log.jsonl"
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def sh(args, cwd=None, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{args[:3]} failed: {r.stderr[-300:]}")
    return r.stdout.strip()


def http_json(url, method="GET", body=None, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        return True, json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        return False, {"error": str(e)[:120]}


def list_gh_repos():
    out = sh(["gh", "repo", "list", GH_USER, "--limit", "200",
              "--json", "name,isFork,isArchived,description,defaultBranchRef"])
    repos = json.loads(out)
    return [r for r in repos if not r["isFork"] and not r["isArchived"]]


def gitee_exists(name):
    ok, _ = http_json(
        f"https://gitee.com/api/v5/repos/{GITEE_USER}/{name}"
        f"?access_token={GITEE_TOKEN}")
    return ok


def gitee_create(name, desc):
    body = ("access_token=" + GITEE_TOKEN +
            "&name=" + name +
            "&private=false&auto_init=false")
    req = urllib.request.Request(
        "https://gitee.com/api/v5/user/repos", data=body.encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as e:
        print(f"    gitee 创建失败: {str(e)[:80]}")
        return False


def gitee_patch_desc_public(name, desc):
    body = json.dumps({"access_token": GITEE_TOKEN, "name": name,
                       "private": False, "description": desc or ""}).encode()
    req = urllib.request.Request(
        f"https://gitee.com/api/v5/repos/{GITEE_USER}/{name}",
        data=body,         method="PATCH",
        headers={"Content-Type": "application/json;charset=UTF-8",
                 "User-Agent": "Mozilla/5.0"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return r.get("private") is False
    except Exception:
        return False


def gitcode_exists(name):
    ok, _ = http_json(f"https://gitcode.com/api/v5/repos/{GITEE_USER}/{name}",
                      headers={"private-token": GITCODE_TOKEN})
    return ok


def gitcode_create(name, desc):
    ok, _ = http_json("https://gitcode.com/api/v5/user/repos", "POST",
                      {"name": name, "description": desc or "",
                       "private": False, "auto_init": False},
                      {"private-token": GITCODE_TOKEN})
    return ok


def done_mark(repo, platform):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"repo": repo, "platform": platform}) + "\n")


def is_done(repo, platform):
    if not LOG.exists():
        return False
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(ln)
            if d["repo"] == repo and d["platform"] == platform:
                return True
        except Exception:
            pass
    return False


def mirror_push(name, gh_url, platform, remote_url):
    work = WORK / (name.replace("/", "_") + ".git")
    if not work.exists():
        sh(["git", "clone", "--mirror", gh_url, str(work)])
    sh(["git", "-C", str(work), "remote", "set-url", "--push", "origin", remote_url])
    r = subprocess.run(["git", "-C", str(work), "push", "--mirror", "origin"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    done_mark(name, platform)


def main():
    repos = list_gh_repos()
    print(f"共 {len(repos)} 个自有仓库（fork/归档除外）\n")
    failures = []
    for i, r in enumerate(repos, 1):
        name = r["name"]
        desc = r.get("description") or ""
        branch = (r.get("defaultBranchRef") or {}).get("name", "main")
        gh_url = f"https://github.com/{GH_USER}/{name}.git"
        print(f"[{i}/{len(repos)}] {name} (默认分支 {branch})")

        # ---- Gitee ----
        if not is_done(name, "gitee"):
            try:
                if not gitee_exists(name):
                    if not gitee_create(name, desc):
                        raise RuntimeError("create fail")
                mirror_push(name, gh_url, "gitee",
                            f"https://{GITEE_USER}:{GITEE_TOKEN}@gitee.com/{GITEE_USER}/{name}.git")
                # 公开态与描述对齐（PATCH 需带 name）
                if not gitee_patch_desc_public(name, desc):
                    print("    ⚠ gitee 公开态/描述 PATCH 未生效")
                print("    gitee ✔")
            except Exception as e:
                print(f"    gitee ✘ {str(e)[:100]}")
                failures.append((name, "gitee", str(e)[:80]))
        else:
            print("    gitee 已完成(日志)")

        # ---- GitCode ----
        if not is_done(name, "gitcode"):
            try:
                if not gitcode_exists(name):
                    if not gitcode_create(name, desc):
                        raise RuntimeError("create fail")
                mirror_push(name, gh_url, "gitcode",
                            f"https://{GITEE_USER}:{GITCODE_TOKEN}@gitcode.com/{GITEE_USER}/{name}.git")
                print("    gitcode ✔")
            except Exception as e:
                print(f"    gitcode ✘ {str(e)[:100]}")
                failures.append((name, "gitcode", str(e)[:80]))
        else:
            print("    gitcode 已完成(日志)")

    print("\n===== 完成 =====")
    if failures:
        print("失败清单:")
        for f in failures:
            print(" ", f)


if __name__ == "__main__":
    main()
