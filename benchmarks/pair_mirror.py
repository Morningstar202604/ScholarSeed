"""Gitee <-> GitCode 平台间对账同步（GitHub 封禁期间的备用方案）。

逻辑：
1. 枚举两平台全部仓库 -> 并集
2. 仅单侧存在 -> 从有的一侧镜像克隆，创建并推送到缺失侧（含公开态 PATCH）
3. 双侧存在但 main 哈希不同 -> 以 pushed_at 较新者为准单向覆盖
4. 断点续传日志同前
"""
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

GITEE_USER = "badhope"
GITEE_TOKEN = os.environ.get("TRAVELER_GITEE_TOKEN", os.environ.get("GITEE_TOKEN", ""))
GITCODE_TOKEN = os.environ.get("TRAVELER_GITCODE_TOKEN", os.environ.get("GITCODE_TOKEN", ""))
WORK = Path(tempfile.gettempdir()) / "pair-mirror-work"
LOG = WORK / "pair_log.jsonl"
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def http_json(url, method="GET", body=None, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        return True, json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        return False, {"error": str(e)[:100]}


def list_gitee():
    out, page = [], 1
    while True:
        ok, data = http_json(
            f"https://gitee.com/api/v5/user/repos?access_token={GITEE_TOKEN}"
            f"&per_page=100&page={page}")
        if not ok or not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    return {r["path"]: {"desc": r.get("description") or "",
                        "pushed_at": r.get("pushed_at") or ""} for r in out}


def list_gitcode():
    ok, data = http_json("https://gitcode.com/api/v5/user/repos?per_page=100",
                         headers={"private-token": GITCODE_TOKEN})
    if not ok:
        print("GitCode 列表失败:", data)
        return {}
    return {r["path"]: {"desc": r.get("description") or "",
                        "pushed_at": r.get("pushed_at") or ""} for r in data}


def sh(args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)


def ls_main(platform, owner, name):
    url = {"gitee": f"https://{GITEE_USER}:{GITEE_TOKEN}@gitee.com/{owner}/{name}.git",
           "gitcode": f"https://badhope:{GITCODE_TOKEN}@gitcode.com/{owner}/{name}.git"}[platform]
    ok, out = sh(["git", "ls-remote", url, "main"])
    if not ok:
        ok2, out2 = sh(["git", "ls-remote", url, "master"])
        return out2.split()[0] if ok2 and out2.strip() else ""
    return out.split()[0] if out.strip() else ""


def done_mark(name, direction):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"repo": name, "direction": direction}) + "\n")


def is_done(name, direction):
    if not LOG.exists():
        return False
    return any(f'"{name}"' in ln and direction in ln
               for ln in LOG.read_text(encoding="utf-8").splitlines())


def mirror_between(src_platform, dst_platform, name):
    src_url = {
        "gitee": f"https://{GITEE_USER}:{GITEE_TOKEN}@gitee.com/{GITEE_USER}/{name}.git",
        "gitcode": f"https://badhope:{GITCODE_TOKEN}@gitcode.com/{GITEE_USER}/{name}.git",
    }[src_platform]
    dst_url = {
        "gitee": f"https://{GITEE_USER}:{GITEE_TOKEN}@gitee.com/{GITEE_USER}/{name}.git",
        "gitcode": f"https://badhope:{GITCODE_TOKEN}@gitcode.com/{GITEE_USER}/{name}.git",
    }[dst_platform]
    work = WORK / f"{dst_platform}__{name}.git"
    if work.exists():
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    ok, out = sh(["git", "clone", "--mirror", src_url, str(work)])
    if not ok:
        raise RuntimeError("clone fail: " + out[-150:])
    sh(["git", "-C", str(work), "remote", "set-url", "--push", "origin", dst_url])
    ok, out = sh(["git", "-C", str(work), "push", "--mirror", "origin"])
    if not ok:
        raise RuntimeError("push fail: " + out[-200:])
    done_mark(name, f"{src_platform}->{dst_platform}")


def main():
    gitee = list_gitee()
    gitcode = list_gitcode()
    names = sorted(set(gitee) | set(gitcode))
    print(f"Gitee {len(gitee)} 个 | GitCode {len(gitcode)} 个 | 并集 {len(names)}\n")
    failures = []
    for i, name in enumerate(names, 1):
        in_g, in_c = name in gitee, name in gitcode
        tag = f"[{i}/{len(names)}] {name}:"
        if in_g and in_c:
            h_g = ls_main("gitee", GITEE_USER, name)
            h_c = ls_main("gitcode", GITEE_USER, name)
            if h_g and h_c and h_g != h_c:
                # 以 pushed_at 新者覆盖旧者
                pg = gitee[name]["pushed_at"]
                pc = gitcode[name]["pushed_at"]
                src, dst = (("gitee", "gitcode") if pg >= pc else ("gitcode", "gitee"))
                try:
                    mirror_between(src, dst, name)
                    print(f"{tag} 双侧存在且分叉 -> {src} 覆盖 {dst}")
                except Exception as e:
                    print(f"{tag} 覆盖失败 {str(e)[:80]}")
                    failures.append((name, f"{src}->{dst}", str(e)[:60]))
                continue
            elif h_g == h_c and h_g:
                print(f"{tag} 已一致 ({h_g[:7]})")
                continue
            else:
                print(f"{tag} 双侧均无 main 提交，跳过")
                continue
        if in_g and not in_c:
            src = "gitee"
        elif in_c and not in_g:
            src = "gitcode"
        else:
            continue
        dst = "gitcode" if src == "gitee" else "gitee"
        if is_done(name, f"{src}->{dst}"):
            print(f"{tag} 日志已完成")
            continue
        # 在缺失侧创建
        if dst == "gitee":
            body = ("access_token=" + GITEE_TOKEN + "&name=" + name +
                    "&auto_init=false")
            req = urllib.request.Request(
                "https://gitee.com/api/v5/user/repos", data=body.encode(),
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            created = True
            try:
                urllib.request.urlopen(req, timeout=30)
            except Exception as e:
                created = False
                print(f"{tag} gitee 创建失败 {str(e)[:60]}")
                failures.append((name, "gitee-create", str(e)[:50]))
        else:
            created, resp = http_json(
                "https://gitcode.com/api/v5/user/repos", "POST",
                {"name": name, "private": False, "auto_init": False},
                {"private-token": GITCODE_TOKEN})
            if not created:
                print(f"{tag} gitcode 创建失败 {str(resp)[:60]}")
                failures.append((name, "gitcode-create", str(resp)[:50]))
        if not created:
            continue
        try:
            mirror_between(src, dst, name)
            print(f"{tag} 已从 {src} 镜像到 {dst}")
        except Exception as e:
            print(f"{tag} 推送失败 {str(e)[:80]}")
            failures.append((name, f"{src}->{dst}", str(e)[:60]))

    print("\n===== 完成 =====")
    if failures:
        print("失败清单:")
        for f in failures:
            print(" ", f)


if __name__ == "__main__":
    main()
