#!/usr/bin/env python3
"""
enrich-index.py — dpkg-scanpackages 后处理。

dpkg-scanpackages 只搬运 deb control 字段，会丢掉 Sileo 专属的
Icon / SileoDepiction 字段，且多行 Changelog 的位置影响 Sileo 解析。
本脚本按固定规则补全并规范化 Packages 索引：

  1. Icon:            <REPO_URL>/icons/<包ID>.png（存在对应文件才注入）
  2. SileoDepiction:  <REPO_URL>/depictions/<包ID>.json（存在对应文件才注入；
                      Sileo 按 URL 缓存 depiction，需在 URL 上带 ?v=N 递增以强制刷新）
  3. 字段排序:        Package → Name → Icon → SileoDepiction → 其余 → Changelog（多行字段置尾）

已写入 deb control 的 Changelog 会被 scanpackages 自然带出，本脚本仅调整其位置。
"""

import os
import sys

REPO_URL = "https://tanyou88888.github.io/sileo"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# depiction URL 缓存版本号：改了 depiction 内容后在这里 +1
DEPICTION_VERSIONS = {
    "com.charlieleung.trollopenreborn": 5,
    "com.charlieleung.trollopenjb": 1,
}

FIELD_ORDER = [
    "Package", "Name", "Icon", "SileoDepiction", "Version", "Architecture",
    "Maintainer", "Installed-Size", "Pre-Depends", "Depends", "Filename",
    "Size", "MD5sum", "SHA1", "SHA256", "Section", "Description",
    "Author", "Origin", "Bugs", "Homepage",
]


def parse(text):
    """解析 Packages 为 stanza 列表：每项为 (fields dict, multiline list[(key, lines)])。"""
    stanzas = []
    for block in text.rstrip("\n").split("\n\n"):
        if not block.strip():
            continue
        fields, multi, cur = {}, [], None
        for line in block.splitlines():
            if line.startswith((" ", "\t")):
                if cur is not None:
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


def main():
    path = os.path.join(BASE, "Packages")
    text = open(path, encoding="utf-8").read()
    out = []
    for fields, multi in parse(text):
        pkg = fields.get("Package", "")
        # Icon：优先使用仓库内每包图标
        if not fields.get("Icon") and os.path.isfile(os.path.join(BASE, "icons", pkg + ".png")):
            fields["Icon"] = "%s/icons/%s.png" % (REPO_URL, pkg)
        # SileoDepiction：仅当扁平 depiction 文件存在
        if not fields.get("SileoDepiction") and os.path.isfile(os.path.join(BASE, "depictions", pkg + ".json")):
            v = DEPICTION_VERSIONS.get(pkg, 1)
            fields["SileoDepiction"] = "%s/depictions/%s.json?v=%d" % (REPO_URL, pkg, v)
        out.append(render(fields, multi))
    open(path, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
    print("enriched %d stanzas" % len(out))


if __name__ == "__main__":
    sys.exit(main())
