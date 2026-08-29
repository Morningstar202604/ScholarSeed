"""Gitee <-> GitCode 全量储存与同步 v2。

固化各平台正确姿势：
- Gitee：写操作 JSON 体必须含 name（必填）+ charset=UTF-8 + 浏览器 UA；创建用表单 access_token
- GitCode：认证走 private-token 请求头，JSON 体

能力：双侧存在性/可见性/描述对齐 + 引用同步（pushed_at 新者为准）+ 空仓库对齐。
"""
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GITEE_USER = "badhope"
GITEE_TOKEN = os.environ.get("TRAVELER_GITEE_TOKEN", os.environ.get("GITEE_TOKEN", ""))
GITCODE_TOKEN = os.environ.get("TRAVELER_GITCODE_TOKEN", os.environ.get("GITCODE_TOKEN", ""))
WORK = Path(tempfile.gettempdir()) / "pair-v2"
LOG = WORK / "v2_log.jsonl"
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json;charset=UTF-8"}


def http_json(url, method="GET", body=None, headers=None, form=None):
    h = {"User-Agent": "Mozilla/5.0"}
    h.update(headers or {})
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        return True, json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode(errors="replace")[:120]
        except Exception:
            pass
        return False, {"http": e.code, "detail": detail}
    except Exception as e:
        return False, {"error": str(e)[:100]}


def list_gitee():
    out, page = [], 1
    while True:
        ok, data = http_json(
            f"https://gitee.com/api/v5/user/repos?access_token={GITEE_TOKEN}"
            f"&per_page=100&page={page}")
        if not ok or not isinstance(data, list) or not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    res = {}
    for r in out:
        res[r["path"]] = {
            "private": r.get("private", True),
            "desc": r.get("description") or "",
            "pushed_at": r.get("pushed_at") or "",
            "empty": bool(r.get("emptied") or not r.get("default_branch")),
        }
    return res


def list_gitcode():
    ok, data = http_json("https://gitcode.com/api/v5/user/repos?per_page=100",
                         headers={"private-token": GITCODE_TOKEN})
    res = {}
    if ok and isinstance(data, list):
        for r in data:
            res[r["path"]] = {
                "private": r.get("private", False),
                "desc": r.get("description") or "",
                "pushed_at": r.get("pushed_at") or "",
                "empty": False,
            }
    else:
        print("GitCode 列表异常:", str(data)[:120])
    return res


def sh(args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)


def urls(platform, name):
    if platform == "gitee":
        api = f"https://gitee.com/api/v5/repos/{GITEE_USER}/{name}"
        auth = f"?access_token={GITEE_TOKEN}"
        git = f"https://{GITEE_USER}:{GITEE_TOKEN}@gitee.com/{GITEE_USER}/{name}.git"
        return api + auth, api, git
    api = f"https://gitcode.com/api/v5/repos/{GITEE_USER}/{name}"
    git = f"https://badhope:{GITCODE_TOKEN}@gitcode.com/{GITEE_USER}/{name}.git"
    return api, api, git


def get_meta(platform, name):
    api, _, _ = urls(platform, name)
    hdr = {"private-token": GITCODE_TOKEN} if platform == "gitcode" else {}
    ok, data = http_json(api, headers=hdr)
    if not ok:
        return None
    return {"exists": True,
            "private": bool(data.get("private")),
            "desc": data.get("description") or "",
            "pushed_at": data.get("pushed_at") or ""}


def patch_public_desc(platform, name, desc):
    api, _, _ = urls(platform, name)
    if platform == "gitee":
        ok, r = http_json(api, "PATCH",
                          {"access_token": GITEE_TOKEN, "name": name,
                           "private": False, "description": desc},
                          {"User-Agent": "Mozilla/5.0"})
    else:
        ok, r = http_json(api, "PATCH",
                          {"name": name, "private": False, "description": desc},
                          {"private-token": GITCODE_TOKEN})
    return ok and (r.get("private") is False if isinstance(r, dict) else False)


def create_empty(platform, name, desc):
    if platform == "gitee":
        ok, _ = http_json(
            "https://gitee.com/api/v5/user/repos", "POST",
            form={"access_token": GITEE_TOKEN, "name": name,
                  "description": desc, "auto_init": "false"})
        return ok
    ok, _ = http_json("https://gitcode.com/api/v5/user/repos", "POST",
                      {"name": name, "description": desc, "private": False,
                       "auto_init": False}, {"private-token": GITCODE_TOKEN})
    return ok


def ls_refs(platform, name):
    _, _, git = urls(platform, name)
    ok, out = sh(["git", "ls-remote", git])
    if not ok:
        return {}
    refs = {}
    for ln in out.splitlines():
        parts = ln.split()
        if len(parts) == 2:
            refs[parts[1]] = parts[0]
    return refs


def mirror_all_branches(src_platform, dst_platform, name):
    _, _, src_git = urls(src_platform, name)
    _, _, dst_git = urls(dst_platform, name)
    work = WORK / f"{dst_platform}__{name}.git"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    ok, out = sh(["git", "clone", "--mirror", src_git, str(work)])
    if not ok:
        raise RuntimeError("clone fail: " + out[-150:])
    sh(["git", "-C", str(work), "remote", "set-url", "--push", "origin", dst_git])
    ok, out = sh(["git", "-C", str(work), "push", "--mirror", "origin"])
    if not ok:
        raise RuntimeError("push fail: " + out[-200:])


def done_mark(key):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"k": key}) + "\n")


def is_done(key):
    if not LOG.exists():
        return False
    return any(json.loads(line).get("k") == key
               for line in LOG.read_text(encoding="utf-8").splitlines())


def main():
    gitee, gitcode = list_gitee(), list_gitcode()
    # 排除特殊用户页仓库
    SPECIAL = {"Morningstar202604", "weed33834"}
    names = sorted((set(gitee) | set(gitcode)) - SPECIAL - {"AstrBot"})
    print(f"Gitee {len(gitee)} | GitCode {len(gitcode)} | 待处理并集 {len(names)}\n")
    actions = []
    for i, name in enumerate(names, 1):
        gm, cm = gitee.get(name), gitcode.get(name)
        acts = []
        # 可见性对齐为公开
        if gm and gm["private"]:
            if patch_public_desc("gitee", name, gm["desc"]):
                gm["private"] = False
                acts.append("gitee转公开")
        if cm and cm["private"]:
            if patch_public_desc("gitcode", name, cm["desc"]):
                cm["private"] = False
                acts.append("gitcode转公开")
        # 描述补齐（单侧缺失时复制另一侧）
        if gm and cm:
            if not gm["desc"] and cm["desc"]:
                patch_public_desc("gitee", name, cm["desc"])
                acts.append("gitee补描述")
            elif not cm["desc"] and gm["desc"]:
                patch_public_desc("gitcode", name, gm["desc"])
                acts.append("gitcode补描述")
        # 内容同步
        rg = ls_refs("gitee", name) if gm else {}
        rc = ls_refs("gitcode", name) if cm else {}
        g_has, c_has = bool(rg), bool(rc)
        if g_has and c_has:
            hg, hc = rg.get("refs/heads/main") or rg.get("refs/heads/master"), \
                     rc.get("refs/heads/main") or rc.get("refs/heads/master")
            if hg and hc and hg != hc:
                pg, pc = (gm or {}).get("pushed_at",""), (cm or {}).get("pushed_at","")
                src, dst = ("gitee","gitcode") if pg >= pc else ("gitcode","gitee")
                mirror_all_branches(src, dst, name)
                acts.append(f"{src}->{dst} 覆盖")
        elif g_has and not c_has:
            create_empty("gitcode", name, (gm or {}).get("desc",""))
            mirror_all_branches("gitee", "gitcode", name)
            acts.append("gitcode新建并镜像")
        elif c_has and not g_has:
            create_empty("gitee", name, (cm or {}).get("desc",""))
            mirror_all_branches("gitcode", "gitee", name)
            acts.append("gitee新建并镜像")
        else:
            acts.append("双侧均空(跳过)")

        key = f"{name}|" + ";".join(acts)
        done_mark(key)
        actions.append((name, acts))
        print(f"[{i}/{len(names)}] {name}: {'; '.join(acts) if acts else '无变更'}")

    print("\n===== 汇总 =====")
    changed = [(n, a) for n, a in actions if a != ["双侧均空(跳过)"] and a != ["无变更"]]
    for n, a in changed:
        print(f"  {n}: {'; '.join(a)}")


if __name__ == "__main__":
    main()
