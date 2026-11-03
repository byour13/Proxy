#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py —— 一份节点 txt，生成 Loon 与 Clash Verge 两种订阅

输入：任意数量的节点 txt（支持直接传文件、传目录、或省略则读 ./input）
输出：
  output/loon.txt        base64 通用订阅（Loon [Remote Proxy] 订阅这个）
  output/clash.yaml      Clash YAML（Clash Verge 订阅这个，仅节点 + 一个自动测速组）
  output/nodes.loon.txt  Loon 原生 [Proxy] 行（手动粘贴 / 排查用）
  output/status.json     节点数、更新时间

用法：
  python build.py --input "C:\\Users\\admin\\Downloads\\Telegram Desktop\\11.txt"
  python build.py --input ./input --prefix TG- --exclude "过期|官网"
  python build.py                      # 等价于 --input ./input

支持协议：anytls / vmess / vless / trojan / ss / hysteria2
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from urllib.parse import urlparse, parse_qs, unquote

# ==================== 基础工具 ====================

def b64d(s: str) -> bytes:
    s = s.strip().replace("\n", "").replace("\r", "")
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


def q1(qs, k, d=""):
    v = qs.get(k)
    return v[0] if v else d


def clean_name(name, fallback):
    name = unquote(name or "").strip()
    name = re.sub(r"[\r\n,=]", " ", name)
    return name or fallback


def flag(qs, *keys):
    return any(q1(qs, k).lower() in ("1", "true") for k in keys)


# ==================== 各协议 → 统一结构 ====================

def p_anytls(uri):
    p = urlparse(uri)
    qs = parse_qs(p.query)
    pwd = unquote(p.username or "")
    name = clean_name(p.fragment, f"AnyTLS-{p.hostname}")
    sni = q1(qs, "sni", p.hostname)
    insecure = flag(qs, "insecure", "allowInsecure")
    fp = q1(qs, "fp")

    loon = [f'"{pwd}"', f"sni={sni}"]
    if insecure:
        loon.append("skip-cert-verify=true")
    if fp:
        loon.append(f"tls-profile={fp}")
    if unquote(q1(qs, "alpn")):
        loon.append(f'alpn="{unquote(q1(qs, "alpn"))}"')
    loon += ["udp=true", "block-quic=false"]

    clash = {"name": name, "type": "anytls", "server": p.hostname, "port": int(p.port),
             "password": pwd, "sni": sni, "udp": True}
    if fp:
        clash["client-fingerprint"] = fp
    if insecure:
        clash["skip-cert-verify"] = True

    return {"key": f"{p.hostname}:{p.port}:{pwd}", "name": name, "share": uri,
            "loon": f"{name} = AnyTLS,{p.hostname},{p.port}," + ",".join(loon),
            "clash": clash}


def p_vmess(uri):
    raw = uri[len("vmess://"):].split("#")[0]
    o = json.loads(b64d(raw).decode("utf-8", "ignore"))
    server, port, uuid = o.get("add", ""), int(o.get("port", 443)), o.get("id", "")
    if not server or not uuid:
        raise ValueError("vmess 缺 add/id")
    net = (o.get("net") or "tcp").lower()
    name = clean_name(o.get("ps", ""), f"VMess-{server}")
    tls = (o.get("tls") or "").lower() == "tls"
    sni = o.get("sni") or o.get("host") or server
    insecure = str(o.get("allowInsecure", o.get("insecure", "0"))) in ("1", "true")
    fp = o.get("fp")

    loon = [f'"{uuid}"']
    if net in ("ws", "http"):
        loon += [f"transport={net}", f'path="{o.get("path") or "/"}"']
        if o.get("host"):
            loon.append(f"host={o['host']}")
    if tls:
        loon += ["over-tls=true", f"tls-name={sni}"]
        if insecure:
            loon.append("skip-cert-verify=true")
        if fp:
            loon.append(f"tls-profile={fp}")
    aid = int(o.get("aid") or o.get("alterId") or 0)
    if aid:
        loon.append(f"alterId={aid}")
    loon += [f"cipher={o.get('scy') or o.get('security') or 'auto'}", "udp=true"]

    clash = {"name": name, "type": "vmess", "server": server, "port": port,
             "uuid": uuid, "alterId": aid,
             "cipher": o.get("scy") or o.get("security") or "auto",
             "udp": True, "tls": tls}
    if tls:
        clash["servername"] = sni
        if insecure:
            clash["skip-cert-verify"] = True
        if fp:
            clash["client-fingerprint"] = fp
    if net in ("ws", "http"):
        clash["network"] = net
        ws = {"path": o.get("path") or "/"}
        if o.get("host"):
            ws["headers"] = {"Host": o["host"]}
        clash["ws-opts"] = ws

    return {"key": f"{server}:{port}:{uuid}", "name": name, "share": uri,
            "loon": f"{name} = VMess,{server},{port}," + ",".join(loon), "clash": clash}


def p_vless(uri):
    p = urlparse(uri)
    qs = parse_qs(p.query)
    uuid = unquote(p.username or "")
    name = clean_name(p.fragment, f"VLESS-{p.hostname}")
    net = (q1(qs, "type", "tcp")).lower()
    sec = q1(qs, "security", "none")
    sni = unquote(q1(qs, "sni", p.hostname))
    fp = q1(qs, "fp")

    loon = [f'"{uuid}"']
    if net in ("ws", "http"):
        loon += [f"transport={net}", f'path="{unquote(q1(qs,"path","/"))}"']
        if q1(qs, "host"):
            loon.append(f"host={q1(qs,'host')}")
    if sec in ("tls", "reality"):
        loon += ["over-tls=true", f"sni={sni}"]
        if sec == "reality":
            loon.append("reality=true")
            if q1(qs, "pbk"):
                loon.append(f'public-key="{q1(qs,"pbk")}"')
            if q1(qs, "sid"):
                loon.append(f"short-id={q1(qs,'sid')}")
        if fp:
            loon.append(f"tls-profile={fp}")
        if flag(qs, "allowInsecure"):
            loon.append("skip-cert-verify=true")
    loon.append("udp=true")

    clash = {"name": name, "type": "vless", "server": p.hostname, "port": int(p.port),
             "uuid": uuid, "udp": True, "tls": sec in ("tls", "reality")}
    if clash["tls"]:
        clash["servername"] = sni
        if fp:
            clash["client-fingerprint"] = fp
        if flag(qs, "allowInsecure"):
            clash["skip-cert-verify"] = True
    if sec == "reality":
        clash["reality-opts"] = {"public-key": q1(qs, "pbk"), "short-id": q1(qs, "sid")}
    if net in ("ws", "http"):
        clash["network"] = net
        ws = {"path": unquote(q1(qs, "path", "/"))}
        if q1(qs, "host"):
            ws["headers"] = {"Host": q1(qs, "host")}
        clash["ws-opts"] = ws

    return {"key": f"{p.hostname}:{p.port}:{uuid}", "name": name, "share": uri,
            "loon": f"{name} = VLESS,{p.hostname},{p.port}," + ",".join(loon), "clash": clash}


def p_trojan(uri):
    p = urlparse(uri)
    qs = parse_qs(p.query)
    pwd = unquote(p.password or p.username or "")
    name = clean_name(p.fragment, f"Trojan-{p.hostname}")
    sni = unquote(q1(qs, "sni", p.hostname))

    loon = [f'"{pwd}"', f"sni={sni}"]
    if flag(qs, "allowInsecure"):
        loon.append("skip-cert-verify=true")
    if (q1(qs, "type", "tcp")).lower() == "ws":
        loon += ["transport=ws", f'path="{unquote(q1(qs,"path","/"))}"']
        if q1(qs, "host"):
            loon.append(f"host={q1(qs,'host')}")
    loon.append("udp=true")

    clash = {"name": name, "type": "trojan", "server": p.hostname, "port": int(p.port),
             "password": pwd, "sni": sni, "udp": True}
    if flag(qs, "allowInsecure"):
        clash["skip-cert-verify"] = True
    if (q1(qs, "type", "tcp")).lower() == "ws":
        clash["network"] = "ws"
        ws = {"path": unquote(q1(qs, "path", "/"))}
        if q1(qs, "host"):
            ws["headers"] = {"Host": q1(qs, "host")}
        clash["ws-opts"] = ws

    return {"key": f"{p.hostname}:{p.port}:{pwd}", "name": name, "share": uri,
            "loon": f"{name} = Trojan,{p.hostname},{p.port}," + ",".join(loon), "clash": clash}


def p_ss(uri):
    body = uri[len("ss://"):]
    frag = ""
    if "#" in body:
        body, frag = body.split("#", 1)
    body = body.split("?")[0]
    if "@" not in body:
        dec = b64d(body).decode("utf-8", "ignore")
        method, rest = dec.split(":", 1)
        pwd, hostport = rest.rsplit("@", 1)
        server, port = hostport.rsplit(":", 1)
    else:
        userinfo, hostport = body.rsplit("@", 1)
        try:
            method, pwd = b64d(userinfo).decode().split(":", 1)
        except Exception:
            method, pwd = userinfo.split(":", 1)
        server, port = hostport.rsplit(":", 1)
    name = clean_name(frag, f"SS-{server}")
    return {"key": f"{server}:{port}:{pwd}", "name": name, "share": uri,
            "loon": f'{name} = Shadowsocks,{server},{port},"{method}","{pwd}",udp=true',
            "clash": {"name": name, "type": "ss", "server": server, "port": int(port),
                      "cipher": method, "password": pwd, "udp": True}}


def p_hy2(uri):
    p = urlparse(uri)
    qs = parse_qs(p.query)
    pwd = unquote(p.password or p.username or "")
    name = clean_name(p.fragment, f"HY2-{p.hostname}")
    sni = unquote(q1(qs, "sni", p.hostname))
    insecure = flag(qs, "insecure", "allowInsecure")

    loon = [f'"{pwd}"', f"sni={sni}"]
    if insecure:
        loon.append("skip-cert-verify=true")
    if q1(qs, "obfs") == "salamander":
        loon.append(f'salamander-password="{unquote(q1(qs, "obfs-password"))}"')
    loon.append("udp=true")

    clash = {"name": name, "type": "hysteria2", "server": p.hostname, "port": int(p.port),
             "password": pwd, "sni": sni, "udp": True}
    if insecure:
        clash["skip-cert-verify"] = True
    if q1(qs, "obfs") == "salamander":
        clash["obfs"] = "salamander"
        clash["obfs-password"] = unquote(q1(qs, "obfs-password"))

    return {"key": f"{p.hostname}:{p.port}:{pwd}", "name": name, "share": uri,
            "loon": f"{name} = Hysteria2,{p.hostname},{p.port}," + ",".join(loon), "clash": clash}


PARSERS = {"anytls": p_anytls, "vmess": p_vmess, "vless": p_vless,
           "trojan": p_trojan, "ss": p_ss, "hysteria2": p_hy2, "hy2": p_hy2}


# ==================== 解析与过滤 ====================

def parse_text(text):
    """单文件解析，返回 (nodes, stats)"""
    nodes, seen = [], set()
    stats = {"lines": 0, "ok": 0, "dup": 0, "unsupported": 0, "bad": 0, "unsupported_kinds": set()}
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith(("#", "//")):
            continue
        stats["lines"] += 1
        m = re.match(r"^([a-zA-Z0-9]+)://", line)
        if not m:
            stats["bad"] += 1
            continue
        scheme = m.group(1).lower()
        fn = PARSERS.get(scheme)
        if not fn:
            stats["unsupported"] += 1
            stats["unsupported_kinds"].add(scheme)
            continue
        try:
            node = fn(line)
        except Exception:
            stats["bad"] += 1
            continue
        if node["key"] in seen:
            stats["dup"] += 1
            continue
        seen.add(node["key"])
        nodes.append(node)
        stats["ok"] += 1
    return nodes, stats


def collect_files(path):
    if os.path.isdir(path):
        out = []
        for root, _, files in os.walk(path):
            for f in sorted(files):
                if f.lower().endswith((".txt", ".list", ".conf")):
                    out.append(os.path.join(root, f))
        return out
    return [path]


# ==================== YAML 渲染（不依赖 pyyaml） ====================

def _scalar(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def dump_yaml(obj, ind=0):
    sp = "  " * ind
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, dict) and v:
                lines.append(f"{sp}{k}:")
                lines.append(dump_yaml(v, ind + 1))
            elif isinstance(v, list) and v:
                lines.append(f"{sp}{k}:")
                lines.append(dump_yaml(v, ind + 1))
            elif isinstance(v, dict):
                lines.append(f"{sp}{k}: {{}}")
            elif isinstance(v, list):
                lines.append(f"{sp}{k}: []")
            else:
                lines.append(f"{sp}{k}: {_scalar(v)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for it in obj:
            if isinstance(it, dict) and it:
                sub = dump_yaml(it, ind + 1).split("\n")
                lines.append(f"{sp}- {sub[0].lstrip()}")
                lines.extend(sub[1:])
            elif isinstance(it, list) and it:
                lines.append(f"{sp}-")
                lines.extend(dump_yaml(it, ind + 1).split("\n"))
            else:
                lines.append(f"{sp}- {_scalar(it)}")
        return "\n".join(lines)
    return f"{sp}{_scalar(obj)}"


# ==================== 输出 ====================

def build(nodes, out_dir, prefix, group_name, test_url, interval, tolerance):
    os.makedirs(out_dir, exist_ok=True)

    # 统一加前缀 + 重名加序号
    used = {}
    for n in nodes:
        name = prefix + n["name"]
        if name in used:
            used[name] += 1
            name = f"{name} #{used[name]}"
        else:
            used[name] = 1
        old = n["name"]
        n["name"] = name
        n["loon"] = n["loon"].replace(old + " = ", name + " = ", 1)
        n["clash"]["name"] = name

    loon_body = "\n".join(n["loon"] for n in nodes)
    share_body = "\n".join(n["share"] for n in nodes)

    with open(os.path.join(out_dir, "nodes.loon.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(loon_body + ("\n" if loon_body else ""))

    with open(os.path.join(out_dir, "loon.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(base64.b64encode(share_body.encode()).decode() if share_body else "")

    names = [n["name"] for n in nodes]
    clash_cfg = {
        "mixed-port": 7890,
        "allow-lan": False,
        "bind-address": "*",
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "proxy-groups": [
            {"name": group_name, "type": "url-test", "proxies": names,
             "url": test_url, "interval": interval, "tolerance": tolerance},
        ] if names else [],
        "proxies": [n["clash"] for n in nodes],
        "rules": ["GEOIP,CN,DIRECT", f"MATCH,{group_name}"],
    }
    header = (f"# 由 build.py 生成 — {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
              f"# 节点数: {len(nodes)}\n"
              f"# 仅节点 + 自动测速组，规则只有 GEOIP,CN 直连 + 兜底走组\n")
    with open(os.path.join(out_dir, "clash.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(header + dump_yaml(clash_cfg) + "\n")

    status = {
        "nodes": len(nodes),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "updated_ts": int(time.time()),
        "prefix": prefix,
        "group": group_name,
        "by_type": {t: sum(1 for n in nodes if n["clash"]["type"] == t)
                    for t in sorted({n["clash"]["type"] for n in nodes})},
        "files": [],
    }
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", action="append", default=None,
                    help="节点 txt 文件或目录，可重复传多次；省略则读 ./input")
    ap.add_argument("--out", "-o", default="output", help="输出目录，默认 output")
    ap.add_argument("--prefix", default="TG-", help="节点名前缀，默认 TG-")
    ap.add_argument("--group", default="TG节点", help="Clash 策略组名，默认 TG节点")
    ap.add_argument("--test-url", default="https://www.gstatic.com/generate_204")
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--tolerance", type=int, default=50)
    ap.add_argument("--include", default="", help="只保留名称匹配该正则的节点")
    ap.add_argument("--exclude", default="", help="剔除名称匹配该正则的节点")
    args = ap.parse_args()

    inputs = args.input or ["input"]
    files = []
    for p in inputs:
        files.extend(collect_files(p))
    if not files:
        print(f"[FATAL] 没找到输入文件：{inputs}", flush=True)
        return 1

    all_nodes, seen, total_stats = [], set(), {}
    for fp in files:
        try:
            with open(fp, encoding="utf-8", errors="ignore") as f:
                nodes, st = parse_text(f.read())
        except Exception as e:
            print(f"[WARN] 读取失败 {fp}: {e}", flush=True)
            continue
        for k, v in st.items():
            if k == "unsupported_kinds":
                total_stats.setdefault(k, set()).update(v)
            else:
                total_stats[k] = total_stats.get(k, 0) + v
        print(f"[INFO] {os.path.basename(fp)}: {st['ok']} 个节点"
              f"（重复 {st['dup']}，不支持 {st['unsupported']}，异常 {st['bad']}）", flush=True)
        for n in nodes:
            if n["key"] in seen:
                continue
            seen.add(n["key"])
            all_nodes.append(n)

    if args.include:
        rx = re.compile(args.include)
        all_nodes = [n for n in all_nodes if rx.search(n["name"])]
    if args.exclude:
        rx = re.compile(args.exclude)
        all_nodes = [n for n in all_nodes if not rx.search(n["name"])]

    if not all_nodes:
        print("[FATAL] 合并后没有任何可用节点", flush=True)
        return 1

    status = build(all_nodes, args.out, args.prefix, args.group,
                   args.test_url, args.interval, args.tolerance)
    status["files"] = [os.path.basename(f) for f in files]
    with open(os.path.join(args.out, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"[OK] 共 {len(all_nodes)} 个节点 → {args.out}/"
          f"（loon.txt / clash.yaml / nodes.loon.txt / status.json）", flush=True)
    print(f"[分布] {status['by_type']}", flush=True)
    if total_stats.get("unsupported_kinds"):
        print(f"[跳过] 不支持的协议: {sorted(total_stats['unsupported_kinds'])}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
