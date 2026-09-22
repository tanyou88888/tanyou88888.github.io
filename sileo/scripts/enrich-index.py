#!/usr/bin/env python3
"""
enrich-index.py — dpkg-scanpackages 后处理。

dpkg-scanpackages 只搬运 deb control 字段，会丢掉 Sileo 专属的
Icon / SileoDepiction 字段，且多行 Changelog 的位置影响 Sileo 解析。
本脚本按固定规则补全并规范化 Packages 索引：

  1. Icon:            <REPO_URL>/icons/<包ID>.png（存在对应文件才注入）
  2. SileoDepiction:  <REPO_URL>/depictions/<包ID>.json?v=<内容哈希前8位>
                      （Sileo 按 URL 缓存 depiction；用内容哈希做版本号，
                        depiction 内容一变 URL 自动变，无需手工递增）
  3. 字段排序:        Package → Name → Icon → SileoDepiction → 其余 → Changelog（多行字段置尾）
  4. 分类归一:        按目录 Section 统一为「rootless 插件 / roothide 插件」
  5. 旧版本保留策略:  每包仅保留最近 KEEP_VERSIONS 个版本的 deb，
                      更旧的 deb 自动删除（日记块随之由规则 4 清理）
  6. Requires 自动统一: Details 的 Requires 行按分区（rootless/roothide）
                      与 firmware 依赖自动生成
  7. depiction 自动更新:
                      - 从索引各版本的 control Changelog 自动生成 depiction 的
                        Changelog 选项卡（新版本块自动插到顶部，同版本已一致则原样保留）
                      - Details 的 Version 行同步为最新版本号

deb control 的 Changelog 是更新日记的唯一数据源：control 里写了什么，
Sileo 更新日志页与 depiction 日记页就显示什么。
"""

import hashlib
import json
import os
import re
import sys

REPO_URL = "https://tanyou88888.github.io/sileo"
KEEP_VERSIONS = 3  # 每包保留的最近版本数，更旧的 deb 自动清理
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIELD_ORDER = [
    "Package", "Name", "Icon", "SileoDepiction", "Version", "Architecture",
    "Maintainer", "Installed-Size", "Pre-Depends", "Depends", "Filename",
    "Size", "MD5sum", "SHA1", "SHA256", "Section", "Description",
    "Author", "Origin", "Bugs", "Homepage",
]


def parse(text):
    """解析 Packages 为 stanza 列表：每项为 (fields dict, multiline dict)。"""
    stanzas = []
    for block in text.rstrip("\n").split("\n\n"):
        if not block.strip():
            continue
        fields, multi, cur = {}, [], None
        for line in block.splitlines():
            if line.startswith((" ", "\t")):
                if cur is not None and multi:
                    multi[-1][1].append(line)
                continue
            key, _, val = line.partition(":")
            cur = key.strip()
            fields[cur] = val.strip()
            multi.append([cur, []])
        stanzas.append((fields, {k: v for k, v in multi if v}))
    return stanzas


def render(fields, multi):
    lines, emitted = [], set()
    for key in FIELD_ORDER:
        if key in fields:
            lines.append("%s: %s" % (key, fields[key]))
            emitted.add(key)
            if key in multi:
                lines.extend(multi[key])
    for key in fields:
        if key not in emitted:
            lines.append("%s: %s" % (key, fields[key]))
            if key in multi:
                lines.extend(multi[key])
    return "\n".join(lines)


def vkey(version):
    """版本号排序键：数字段逐位比较。"""
    parts = []
    for seg in re.split(r"[.\-+~]", version):
        parts.append(int(seg) if seg.isdigit() else 0)
    return tuple(parts)


def changelog_block(title, entries):
    """一个版本的 depiction 更新日记块（与手工版同构）。"""
    views = [{"class": "DepictionHeaderView", "title": title}]
    for e in entries:
        views.append({"class": "DepictionMarkdownView", "markdown": "• " + e,
                      "useSpacing": True, "useMargins": True, "margins": "{0,4,10,4}"})
    views.append({"class": "DepictionSeparatorView"})
    return views


def head_ver(view):
    """从 HeaderView 标题提取版本号 token。"""
    m = re.match(r"v?([0-9][0-9A-Za-z.\-+]*)", view.get("title", ""))
    return m.group(1) if m else None


def sync_depiction(pkg, versions, changelogs, requires=None):
    """把 control Changelog 同步进 depiction。versions 需已降序排列。

    - 索引中存在且带 Changelog 的版本：插入/更新日记块（置顶）
    - 索引中已不存在的版本（deb 被删除）：清理其日记块，不留失效残留
    - Details 的 Version 行始终同步为最新版本
    """
    path = os.path.join(BASE, "depictions", pkg + ".json")
    if not os.path.isfile(path):
        return
    d = json.load(open(path, encoding="utf-8"))
    changed = False
    vset = set(versions)
    for tab in d.get("tabs", []):
        if tab.get("tabname") != "Changelog":
            continue
        views = tab["views"]
        # ① 清理已不存在版本的日记块（deb 删除后自动清残留）
        kept, i = [], 0
        while i < len(views):
            v = views[i]
            if v.get("class") == "DepictionHeaderView":
                j = len(views)
                for k in range(i + 1, len(views)):
                    if views[k].get("class") == "DepictionHeaderView":
                        j = k
                        break
                hv = head_ver(v)
                if versions and hv is not None and hv not in vset:
                    changed = True  # 丢弃该块
                else:
                    kept.extend(views[i:j])
                i = j
            else:
                kept.append(v)
                i += 1
        views[:] = kept
        # ② 插入/更新存在版本的日记块
        for ver in versions:
            if ver not in changelogs:
                continue
            first_line, entries = changelogs[ver]
            block = changelog_block(first_line, entries)
            hit = [i for i, v in enumerate(views)
                   if v.get("class") == "DepictionHeaderView" and head_ver(v) == ver]
            if hit:
                i = hit[0]
                j = len(views)
                for k in range(i + 1, len(views)):
                    if views[k].get("class") == "DepictionHeaderView":
                        j = k
                        break
                if views[i:j] != block:
                    views[i:j] = block
                    changed = True
            else:
                first_h = next((i for i, v in enumerate(views)
                                if v.get("class") == "DepictionHeaderView"), len(views))
                views[first_h:first_h] = block
                changed = True
    # ③ Details 的 Version 行同步（独立于日记块变化）
    for tab in d.get("tabs", []):
        if tab.get("tabname") == "Details":
            for v in tab.get("views", []):
                if v.get("class") == "DepictionTableTextView" and v.get("title") == "Version":
                    if versions and v.get("text") != versions[0]:
                        v["text"] = versions[0]
                        changed = True
                if v.get("class") == "DepictionTableTextView" and v.get("title") == "Requires" and requires:
                    if v.get("text") != requires:
                        v["text"] = requires
                        changed = True
    if not changed:
        return
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=4)


def main():
    pkg_path = os.path.join(BASE, "Packages")
    stanzas = parse(open(pkg_path, encoding="utf-8").read())

    # 按包聚合版本与 Changelog
    by_pkg = {}
    for fields, multi in stanzas:
        pkg = fields.get("Package", "")
        ver = fields.get("Version", "")
        ent = by_pkg.setdefault(pkg, {"versions": [], "changelogs": {}})
        if ver:
            ent["versions"].append(ver)
        if "Changelog" in fields and ver:
            lines = [fields["Changelog"]] + multi.get("Changelog", [])
            lines = [l.strip() for l in lines if l.strip()]
            if len(lines) >= 1:
                ent["changelogs"][ver] = (lines[0], lines[1:])

    # 按包聚合 firmware 最低版本（取最新条目的 Depends）
    fw = {}
    for fields, multi in stanzas:
        pkg = fields.get("Package", "")
        dep = fields.get("Depends", "")
        m = re.search(r"firmware\s*\(>=\s*([0-9.]+)\)", dep)
        if pkg and (pkg not in fw or (m and "firmware" in dep)):
            fw[pkg] = m.group(1) if m else None

    # 旧版本保留策略：每包保留最近 KEEP_VERSIONS 个版本，删除更旧的 deb
    dropped = []
    for pkg, ent in by_pkg.items():
        ent["versions"].sort(key=vkey, reverse=True)
        if len(ent["versions"]) <= KEEP_VERSIONS:
            continue
        for ver in ent["versions"][KEEP_VERSIONS:]:
            for fields, multi in stanzas:
                if fields.get("Package") == pkg and fields.get("Version") == ver:
                    fn = fields.get("Filename", "")
                    if fn:
                        path = os.path.join(BASE, fn)
                        if os.path.isfile(path):
                            os.remove(path)
                            dropped.append(fn)
    if dropped:
        print("旧版本清理（保留最近 %d 版）: %s" % (KEEP_VERSIONS, ", ".join(dropped)))
        stanzas = [(f, m) for f, m in stanzas
                   if not any(f.get("Filename") == fn for fn in dropped)]
        for pkg, ent in by_pkg.items():
            ent["versions"] = [v for v in ent["versions"]
                               if v in {f.get("Version") for f, _ in stanzas if f.get("Package") == pkg}]

    out = []
    for fields, multi in stanzas:
        pkg = fields.get("Package", "")
        ent = by_pkg.get(pkg, {"versions": [], "changelogs": {}})
        ent["versions"].sort(key=vkey, reverse=True)

        # 自动同步 depiction 更新日记与 Requires（在计算哈希前完成）
        zone = ("roothide" if "/roothide/" in fields.get("Filename", "")
                else "rootless" if "/rootless/" in fields.get("Filename", "") else None)
        minfw = fw.get(pkg)
        requires = " · ".join(x for x in (
            ("iOS %s+" % minfw) if minfw else None, zone) if x)
        sync_depiction(pkg, ent["versions"], ent["changelogs"], requires or None)

        # Icon：仓库内每包图标（强制覆盖，保证命名约定统一）
        if os.path.isfile(os.path.join(BASE, "icons", pkg + ".png")):
            fields["Icon"] = "%s/icons/%s.png" % (REPO_URL, pkg)
        # SileoDepiction：内容哈希做 ?v=，自动缓存破坏
        dpath = os.path.join(BASE, "depictions", pkg + ".json")
        if os.path.isfile(dpath):
            digest = hashlib.sha256(open(dpath, "rb").read()).hexdigest()[:8]
            fields["SileoDepiction"] = "%s/depictions/%s.json?v=%s" % (REPO_URL, pkg, digest)
        # 分类归一：按目录统一 Section
        if "/roothide/" in fields.get("Filename", ""):
            fields["Section"] = "roothide 插件"
        elif "/rootless/" in fields.get("Filename", ""):
            fields["Section"] = "rootless 插件"
        # 删除废弃的小写 Sileodepiction 字段（Sileo 会误读为 depiction 地址）
        fields.pop("Sileodepiction", None)
        out.append(render(fields, multi))

    open(pkg_path, "w", encoding="utf-8").write("\n\n".join(out) + "\n")

    # 生成 Packages.gz（mtime 固定，保证同内容同哈希）并更新 Release 校验和
    import gzip as _gz
    raw = open(pkg_path, "rb").read()
    gz_path = os.path.join(BASE, "Packages.gz")
    with _gz.GzipFile(filename="Packages", mode="wb", fileobj=open(gz_path, "wb"), mtime=0) as f:
        f.write(raw)
    gz_data = open(gz_path, "rb").read()

    rel_path = os.path.join(BASE, "Release")
    rel = [l for l in open(rel_path, encoding="utf-8").read().splitlines()
           if not re.match(r"^(MD5Sum|SHA1|SHA256):", l) and not l.startswith(" ")]
    def _h(data, algo):
        return hashlib.new(algo, data).hexdigest()
    rel.append("MD5Sum:")
    for name, data in (("Packages", raw), ("Packages.gz", gz_data)):
        rel.append(" %s %8d %s" % (_h(data, "md5"), len(data), name))
    rel.append("SHA256:")
    for name, data in (("Packages", raw), ("Packages.gz", gz_data)):
        rel.append(" %s %8d %s" % (_h(data, "sha256"), len(data), name))
    open(rel_path, "w", encoding="utf-8").write("\n".join(rel) + "\n")

    print("enriched %d stanzas" % len(out))


if __name__ == "__main__":
    sys.exit(main())
