#!/usr/bin/env python3
"""
build-homepage.py — 从 Packages 索引自动渲染源主页 index.html。

卡片数据（图标/名称/简介/最新版本/分区）全部来自索引与仓库约定文件，
加减软件包后无需手工维护主页。由 APT 流水线在 enrich 之后调用。
"""

import hashlib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = "https://tanyou88888.github.io/sileo"

TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0d0d16">
  <title>tanyou88888 · Jailbreak Repo</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0d0d16; --surface: #16161f; --surface2: #1e1e2a;
      --border: rgba(255,255,255,.08); --text: #f0f0f5; --muted: #9898ac;
      --accent1: #bf85ff; --accent2: #5eb7ff; --accent3: #ff7eb3; --radius: 18px;
    }
    body { background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
      min-height: 100vh; padding-bottom: 60px; }
    .hero { text-align: center; padding: 64px 24px 40px; position: relative; overflow: hidden; }
    .hero::before { content: ''; position: absolute; inset: 0; background:
        radial-gradient(ellipse 60% 40% at 25% 0%, rgba(94,183,255,.18) 0%, transparent 70%),
        radial-gradient(ellipse 50% 35% at 75% 0%, rgba(255,126,179,.15) 0%, transparent 70%),
        radial-gradient(ellipse 40% 30% at 50% 80%, rgba(191,133,255,.12) 0%, transparent 70%);
      pointer-events: none; }
    .hero-logo { width: 96px; height: 96px; border-radius: 26px;
      box-shadow: 0 8px 40px rgba(191,133,255,.35), 0 2px 8px rgba(0,0,0,.6); margin-bottom: 20px; }
    .hero h1 { font-size: clamp(1.8rem, 5vw, 2.8rem); font-weight: 700; letter-spacing: -.02em;
      background: linear-gradient(135deg, var(--accent2) 0%, var(--accent1) 50%, var(--accent3) 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
      margin-bottom: 8px; }
    .hero p { color: var(--muted); font-size: 1rem; margin-bottom: 32px; }
    .add-buttons { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 16px; }
    .add-btn { display: inline-flex; align-items: center; gap: 9px; padding: 12px 22px;
      border-radius: 50px; font-size: .95rem; font-weight: 600; text-decoration: none;
      transition: transform .15s, box-shadow .15s; border: 1px solid var(--border); }
    .add-btn:hover { transform: translateY(-2px); }
    .add-btn svg { flex-shrink: 0; }
    .btn-sileo { background: linear-gradient(135deg,#1a6fff,#6b2fff); box-shadow: 0 4px 20px rgba(107,47,255,.4); color:#fff; }
    .btn-zebra { background: linear-gradient(135deg,#ff8c00,#ffd000); box-shadow: 0 4px 20px rgba(255,160,0,.35); color:#1a1a00; }
    .btn-cydia { background: linear-gradient(135deg,#00b4d8,#0077b6); box-shadow: 0 4px 20px rgba(0,180,216,.35); color:#fff; }
    .copy-url { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 4px; }
    .url-chip { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px;
      padding: 7px 14px; font-size: .85rem; font-family: "SF Mono", ui-monospace, monospace;
      color: var(--accent2); cursor: pointer; transition: background .15s; }
    .url-chip:hover { background: var(--surface); }
    .copy-hint { font-size: .8rem; color: var(--muted); }
    .section-header { max-width: 680px; margin: 40px auto 16px; padding: 0 20px;
      display: flex; align-items: baseline; gap: 10px; }
    .section-header h2 { font-size: 1.15rem; font-weight: 600; color: var(--text); }
    .section-header .badge { font-size: .75rem; font-weight: 600; padding: 2px 8px;
      background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; color: var(--muted); }
    .pkg-grid { max-width: 680px; margin: 0 auto; padding: 0 16px; display: flex; flex-direction: column; gap: 8px; }
    .pkg-card { display: flex; align-items: center; gap: 16px; background: var(--surface);
      border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px;
      transition: background .15s, border-color .15s; }
    .pkg-card:hover { background: var(--surface2); border-color: rgba(255,255,255,.14); }
    .pkg-icon { width: 54px; height: 54px; border-radius: 13px; flex-shrink: 0; background: var(--surface2); }
    .pkg-info { flex: 1; min-width: 0; }
    .pkg-name { font-weight: 600; font-size: 1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .pkg-desc { color: var(--muted); font-size: .875rem; margin-top: 2px; line-height: 1.4; }
    .pkg-meta { margin-top: 5px; display: flex; gap: 6px; align-items: center; }
    .pkg-version { font-size: .75rem; color: var(--accent1); background: rgba(191,133,255,.12);
      border-radius: 4px; padding: 1px 7px; }
    .pkg-section { font-size: .75rem; color: var(--muted); background: var(--surface2);
      border-radius: 4px; padding: 1px 7px; }
    footer { text-align: center; margin-top: 56px; color: var(--muted); font-size: .8rem; }
    footer a { color: var(--accent2); text-decoration: none; }
  </style>
</head>
<body>
  <div class="hero">
    <img class="hero-logo" src="__REPO__/CydiaIcon.png" alt="tanyou88888">
    <h1>tanyou88888</h1>
    <p>iOS 越狱软件源 &nbsp;&middot;&nbsp; __COUNT__ packages</p>
    <div class="add-buttons">
      <a class="add-btn btn-sileo" href="sileo://source/__REPO__/">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/><path fill="#1a6fff" d="M8 10h8M8 14h5" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>
        添加到 Sileo
      </a>
      <a class="add-btn btn-zebra" href="zbra://sources/add/__REPO__/">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/><path fill="#ff8c00" d="M7 8h10M7 12h7M7 16h10" stroke="#1a1a00" stroke-width="2" stroke-linecap="round"/></svg>
        添加到 Zebra
      </a>
      <a class="add-btn btn-cydia" href="cydia://url/https://cydia.saurik.com/api/share#?source=__REPO__/">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/><path fill="#00b4d8" d="M9 12l2 2 4-4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        添加到 Cydia
      </a>
    </div>
    <div class="copy-url">
      <span class="url-chip" onclick="navigator.clipboard.writeText('__REPO__/').then(()=>{this.textContent='已复制！';setTimeout(()=>this.textContent='__REPO__/',1500)})">__REPO__/</span>
      <span class="copy-hint">点击复制</span>
    </div>
  </div>

  <div class="section-header">
    <h2>软件包</h2>
    <span class="badge">__COUNT__</span>
  </div>

  <div class="pkg-grid">
__CARDS__
  </div>

  <footer>
    © 2026 tanyou88888 &nbsp;·&nbsp; <a href="https://github.com/tanyou88888/tanyou88888.github.io">GitHub</a>
  </footer>
</body>
</html>
"""


def vkey(version):
    parts = []
    for seg in re.split(r"[.\-+~]", version):
        parts.append(int(seg) if seg.isdigit() else 0)
    return tuple(parts)


def main():
    text = open(os.path.join(BASE, "Packages"), encoding="utf-8").read()
    pkgs = {}
    for block in text.rstrip("\n").split("\n\n"):
        if not block.strip():
            continue
        f = {}
        for line in block.splitlines():
            if line.startswith((" ", "\t")) or ":" not in line:
                continue
            k, v = line.split(":", 1)
            f[k.strip()] = v.strip()
        pkg = f.get("Package", "")
        if not pkg:
            continue
        cur = pkgs.setdefault(pkg, {"name": pkg, "ver": "0", "desc": "",
                                    "section": "", "icon": ""})
        if vkey(f.get("Version", "0")) >= vkey(cur["ver"]):
            cur.update({
                "name": f.get("Name", pkg),
                "ver": f.get("Version", "0"),
                "desc": f.get("Description", cur["desc"]),
                "section": f.get("Section", cur["section"]),
                "icon": f.get("Icon", cur["icon"]),
            })

    cards = []
    for pkg in sorted(pkgs, key=lambda p: vkey(pkgs[p]["ver"]), reverse=True):
        info = pkgs[pkg]
        icon = info["icon"] or "%s/CydiaIcon.png" % REPO_URL
        desc = info["desc"].split("。")[0][:60]
        cards.append(
            '    <div class="pkg-card">\n'
            '      <img class="pkg-icon" src="%s" alt="%s icon" onerror="this.src=\'%s/CydiaIcon.png\'">\n'
            '      <div class="pkg-info">\n'
            '        <div class="pkg-name">%s</div>\n'
            '        <div class="pkg-desc">%s</div>\n'
            '        <div class="pkg-meta"><span class="pkg-version">v%s</span>'
            '<span class="pkg-section">%s</span></div>\n'
            '      </div>\n'
            '    </div>' % (icon, info["name"], REPO_URL, info["name"],
                           desc, info["ver"], info["section"]))

    html = (TEMPLATE.replace("__REPO__", REPO_URL)
            .replace("__COUNT__", str(len(pkgs)))
            .replace("__CARDS__", "\n\n".join(cards)))
    out = os.path.join(os.path.dirname(BASE), "index.html")
    open(out, "w", encoding="utf-8").write(html)
    print("homepage: %d packages" % len(pkgs))


if __name__ == "__main__":
    sys.exit(main())
