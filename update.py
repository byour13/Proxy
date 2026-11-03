#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update.py —— 一键更新节点订阅

用法：
  把新的 txt 丢进 input/ 目录，然后运行：
      python update.py

  可选参数：
      --gen-only   只生成订阅文件，不做 git 操作（等于直接跑 build.py）
      --no-push    生成并提交，但不推送到 GitHub
      --force      即使节点内容没变化也照常提交推送
      --prefix X   临时改节点名前缀（默认 TG-）
      --exclude R  剔除名称匹配正则的节点，例如 "过期|官网"
      --include R  只保留名称匹配正则的节点

流程：预检 → 生成 → 判断有无变化 → 提交 → 推送 → 清理 jsDelivr 缓存
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

# ---------- 控制台中文输出 ----------
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

ROOT = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(ROOT, "input")
OUTPUT_DIR = os.path.join(ROOT, "output")
BUILD_PY = os.path.join(ROOT, "build.py")

GH_REPO = "byour13/Proxy"
BRANCH = "main"
LOON_URL = f"https://cdn.jsdelivr.net/gh/{GH_REPO}@{BRANCH}/output/loon.txt"
CLASH_URL = f"https://cdn.jsdelivr.net/gh/{GH_REPO}@{BRANCH}/output/clash.yaml"
PURGE_BASE = f"https://purge.jsdelivr.net/gh/{GH_REPO}@{BRANCH}/output/"

TOTAL_STEPS = 5


def title(step, text):
    print(f"\n[{step}/{TOTAL_STEPS}] {text}")


def run(cmd, cwd=ROOT, timeout=180, capture=True):
    """执行命令，返回 (returncode, stdout+stderr)"""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, timeout=timeout,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.STDOUT if capture else None,
        )
        out = ""
        if capture and p.stdout:
            out = p.stdout.decode("utf-8", "replace")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "命令执行超时"
    except FileNotFoundError as e:
        return 127, f"找不到命令：{e.filename}"


def file_digest(paths):
    """对输出文件内容做指纹，用于判断节点是否真的变了。

    clash.yaml 头部有「生成时间」注释，若直接 hash 会每次都判定为变化，
    这里剔除所有注释行后再比对。
    """
    h = hashlib.sha256()
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, "rb") as f:
            data = f.read()
        # 统一换行：git checkout 可能把 LF 转成 CRLF，不能算作内容变化
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if p.lower().endswith((".yaml", ".yml")):
            data = b"\n".join(
                line for line in data.split(b"\n")
                if not line.lstrip().startswith(b"#")
            )
        h.update(data)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="一键更新节点订阅并推送")
    ap.add_argument("--gen-only", action="store_true", help="只生成，不做 git 操作")
    ap.add_argument("--no-push", action="store_true", help="生成并提交，但不推送")
    ap.add_argument("--force", action="store_true", help="节点没变化也强制提交推送")
    ap.add_argument("--latest", action="store_true", help="只用 input 里最新的一个 txt，忽略更早的文件")
    ap.add_argument("--prefix", default="TG-", help="节点名前缀，默认 TG-")
    ap.add_argument("--include", default="", help="只保留名称匹配该正则的节点")
    ap.add_argument("--exclude", default="", help="剔除名称匹配该正则的节点")
    args = ap.parse_args()

    # ---------- 1 预检 ----------
    title(1, "预检")
    if not os.path.isfile(BUILD_PY):
        print(f"[FAIL] 找不到 build.py：{BUILD_PY}")
        return 1

    os.makedirs(INPUT_DIR, exist_ok=True)
    files = sorted(
        os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(".txt") and os.path.isfile(os.path.join(INPUT_DIR, f))
    )
    if not files:
        print(f"[FAIL] {INPUT_DIR} 里没有 .txt 文件")
        print("       请把新下载的节点文件放进 input/ 目录后再运行本脚本")
        return 1

    if args.latest and len(files) > 1:
        newest = max(files, key=os.path.getmtime)
        print(f"--latest 生效：只使用最新文件 {os.path.basename(newest)}")
        files = [newest]

    print(f"输入文件 {len(files)} 个：")
    for f in files:
        size = os.path.getsize(f)
        print(f"  - {os.path.basename(f)}  ({size} 字节)")
    if len(files) > 1 and not args.latest:
        print("  （多个文件会被合并去重；只想用最新那个可加 --latest）")

    is_git = not args.gen_only
    if is_git:
        if not shutil.which("git"):
            print("[FAIL] 系统里找不到 git 命令")
            return 1
        code, out = run(["git", "rev-parse", "--is-inside-work-tree"])
        if code != 0:
            print("[FAIL] 当前目录不是 git 仓库")
            print(out.strip()[:300])
            return 1
        print("git 仓库检查通过")

    # ---------- 2 生成 ----------
    title(2, "生成订阅文件")
    before = file_digest([os.path.join(OUTPUT_DIR, "loon.txt"),
                          os.path.join(OUTPUT_DIR, "clash.yaml")])

    cmd = [sys.executable, BUILD_PY]
    for f in files:
        cmd += ["--input", f]
    cmd += ["--out", OUTPUT_DIR, "--prefix", args.prefix]
    if args.include:
        cmd += ["--include", args.include]
    if args.exclude:
        cmd += ["--exclude", args.exclude]

    code, out = run(cmd, timeout=300)
    print(out.rstrip())
    if code != 0:
        print("[FAIL] 生成失败，已中止（不会推送任何内容）")
        return 1

    after = file_digest([os.path.join(OUTPUT_DIR, "loon.txt"),
                         os.path.join(OUTPUT_DIR, "clash.yaml")])
    changed = before != after

    with open(os.path.join(OUTPUT_DIR, "status.json"), encoding="utf-8") as f:
        status = json.load(f)
    print(f"\n本次共 {status['nodes']} 个节点，协议分布 {status['by_type']}")

    if args.gen_only:
        print("\n[完成] 仅生成模式，已跳过提交与推送")
        _print_urls()
        return 0

    # ---------- 3 判断有无变化 ----------
    title(3, "检查变更")
    code, out = run(["git", "status", "--porcelain"])
    dirty = [l for l in out.splitlines() if l.strip()]
    input_dirty = any(
        l[3:].strip().startswith("input/") or l[3:].strip().startswith('"input/')
        for l in dirty
    )

    need_commit = bool(dirty)
    if need_commit and not changed and not input_dirty and not args.force:
        print("[跳过] 节点内容与上次完全一致（仅时间戳变化），不产生空提交")
        print("       确实要提交请加 --force")
        # 把仅含新时间戳的输出还原，保持工作区干净
        for f in ("output/status.json", "output/clash.yaml"):
            run(["git", "checkout", "--", f])
        need_commit = False

    if need_commit:
        if changed:
            print(f"检测到 {len(dirty)} 项变更：")
            for l in dirty[:12]:
                print("  " + l)
            if len(dirty) > 12:
                print(f"  ... 另有 {len(dirty) - 12} 项")
        else:
            print("节点内容未变，但 input/ 有新增文件，一并提交")
    else:
        print("输出内容无变化")

    # ---------- 4 提交 ----------
    if need_commit:
        title(4, "提交到本地仓库")
        run(["git", "add", "-A"])
        msg = f"chore: 更新节点（{status['nodes']} 个，{time.strftime('%Y-%m-%d %H:%M')}）"
        code, out = run(["git", "commit", "-m", msg])
        print(out.rstrip()[:800])
        if code != 0:
            print("[FAIL] 提交失败")
            return 1
        print(f"[OK] 已提交：{msg}")
    else:
        print("（本次没有需要提交的改动）")

    if args.no_push:
        print("\n[完成] --no-push 模式，未推送")
        _print_urls()
        return 0

    # 本地是否领先远程（避免"没变更就永远推不上去"）
    code, out = run(["git", "rev-list", "--count", f"origin/{BRANCH}..HEAD"])
    ahead = int(out.strip()) if (code == 0 and out.strip().isdigit()) else 1
    if ahead == 0:
        print("\n[完成] 远程已是最新，无需推送")
        _print_urls()
        return 0
    print(f"本地有 {ahead} 个提交待推送")

    # ---------- 5 推送 + 清缓存 ----------
    title(5, "推送到 GitHub")
    code, out = run(["git", "push", "origin", f"HEAD:{BRANCH}"], timeout=300)
    print(out.rstrip()[:1200])
    if code != 0:
        print("\n[FAIL] 推送失败")
        low = out.lower()
        if any(k in low for k in ("authentication", "could not read username", "invalid username",
                                  "permission denied", "403", "401", "terminal prompts disabled")):
            print("       原因：GitHub 凭证无效或未登录")
            print("       处理：在项目目录手动执行一次  git push")
            print("             Git Credential Manager 会弹窗，用浏览器登录 GitHub 即可，")
            print("             登录成功后本脚本以后就能全自动推送。")
        elif "rejected" in low or "non-fast-forward" in low:
            print("       原因：远程有本地没有的提交")
            print("       处理：执行  git pull --rebase origin main  后重跑本脚本")
        else:
            print("       可稍后重试，或手动执行  git push  origin main")
        return 1

    print("[OK] 推送成功")
    _purge_cache()
    _print_urls(with_version=status.get("updated_ts", int(time.time())))
    return 0


def _purge_cache():
    """通知 jsDelivr 清除缓存，免去手动加 ?v=N"""
    print("\n正在清理 jsDelivr 缓存 …")
    ok = 0
    for name in ("loon.txt", "clash.yaml"):
        try:
            req = urllib.request.Request(PURGE_BASE + name, headers={"User-Agent": "update-py"})
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read(200)
            print(f"  [OK] {name} 缓存已提交刷新")
            ok += 1
        except Exception as e:
            print(f"  [WARN] {name} 刷新失败：{e}")
    if ok == 0:
        print("  （如果客户端看到的还是旧节点，可临时在订阅地址后加 ?v=N）")


def _print_urls(with_version=None):
    v = f"?v={with_version}" if with_version else ""
    print("\n" + "=" * 62)
    print("Loon 订阅地址：")
    print("  " + LOON_URL + v)
    print("Clash Verge 订阅地址：")
    print("  " + CLASH_URL + v)
    print("=" * 62)
    print("Loon：配置 → 订阅 → 更新    Clash Verge：配置页点刷新图标")
    print("（若仍是旧节点，等 1~2 分钟缓存刷新，或改用带 ?v= 的地址）")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)
