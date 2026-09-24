# tanyou88888 越狱软件源 · 运维文档

> 本文档面向维护者（人类或 AI agent），记录源结构、自动化流水线、维护规则与踩坑史。
> 面向用户的页面是 [index.html](https://tanyou88888.github.io/)。

## 源信息

| 项 | 值 |
|---|---|
| 源地址 | `https://tanyou88888.github.io/sileo/` |
| 支持管理器 | Sileo / Zebra / Cydia |
| 上游代码仓 | `hejunjiea/JBOpenReborn`（私有），正式版经 Release 自动投递 |
| 分区规则 | **声明式按目录**：`debs/rootless/` = rootless 插件，`debs/roothide/` = roothide 插件（与文件名无关） |

## 目录结构

```
index.html                      主页（由 build-homepage.py 自动生成，勿手改）
.github/workflows/
  apt-repo.yml                  APT 索引流水线：deb/素材变更 → 重建索引
  pull-release.yml              拉取流水线：定时/手动从私有仓库 Release 拉 deb，
                                自带索引重建（不依赖链式触发）
sileo/
  Release                       源元数据（enrich 自动维护 MD5Sum/SHA256 段）
  Packages / Packages.gz        索引（流水线生成，勿手改）
  debs/rootless/                rootless 分区
  debs/roothide/                roothide 分区（JBOpenReborn 固定投递到此）
  depictions/<包ID>.json        每包 depiction（enrich 自动维护 Changelog/Version/Requires）
  icons/<包ID>.png              每包图标（存在即自动注入 Icon 字段）
  banners/<包ID>.png            每包头图横幅
  meta/release-dates.json       发布日期表（拉取流水线维护，enrich 读它补日记日期）
  scripts/enrich-index.py       核心：索引后处理（见下）
  scripts/build-homepage.py     主页生成
```

## enrich-index.py 的自动化规则

每次流水线重建索引时执行，规则全量幂等：

1. **Icon**：`icons/<包ID>.png` 存在即注入（强制覆盖）
2. **SileoDepiction**：`depictions/<包ID>.json` 存在即注入，`?v=` = **内容哈希前 8 位**（内容变 → URL 自动变 → Sileo 必然刷新，无手工版本号）
3. **分类归一**：按目录覆写 Section 为「rootless 插件 / roothide 插件」
4. **更新日记自动生成**：从各版本 deb 的 control `Changelog` 字段渲染 depiction 的 Changelog 选项卡（新版本置顶；deb 删除后对应日记块自动清除）
5. **版本保留**：每包保留最近 `KEEP_VERSIONS=3` 个版本，更旧 deb 自动删除
6. **Requires 自动统一**：按目录（rootless/roothide）+ firmware 依赖自动生成
7. **日期注入**：读 `meta/release-dates.json` 给自动日记块补「Updated · 日期」
8. **Release 校验和**：生成 Packages.gz（mtime=0 定哈希）并写入 MD5Sum/SHA256 段
9. 删除废弃的小写 `Sileodepiction` 字段（Sileo 会误读为 depiction 地址）

## 流水线

### pull-release.yml（发布主链路）
- 触发：`schedule`（每 6 小时，UTC 0/6/12/18）+ `workflow_dispatch`（手动/API）
- 流程：拉私有仓库最新 Release 的 deb（API 端点 + octet-stream，私有资产 browser_download_url 会 404）→ 校验 ar 格式 → 记录发布日期 → **自建索引**（scan + enrich + homepage）→ 提交
- 依赖 secret：`JBOPENREBORN_TOKEN`（hejunjiea 账号、对私有仓库 Contents: Read-only 的 fine-grained PAT）
- 可选 secret：`BARK_URL` / `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`（上架通知）

### apt-repo.yml（手动上传链路）
- 触发：`push`（debs/depictions/icons/banners/Release/scripts 路径变更）
- 流程：scanpackages → enrich → homepage → 提交
- 注意：**GITHUB_TOKEN 推送的提交不会触发 workflow**（GitHub 防递归）——所以 pull-release 自建索引，不依赖它

### 并发保护
两条流水线共用 `concurrency.group: repo-write` + `cancel-in-progress: true`：
互斥执行，新触发取消进行中的旧例。两者都是全量重建，取消无损失。

## 日常操作

| 场景 | 做法 |
|---|---|
| 发新正式版 | 私有仓库发 Release 附 deb（control 带 Changelog）→ 最迟 6h 自动上架；等不及喊 agent API 触发（约 1 分钟） |
| 手动加包 | deb 丢进对应分区目录，push（文件名随意，识别靠 control） |
| 删包/删版本 | 删 deb 后 push，流水线自动清索引与日记块 |
| 换图标/横幅 | 覆盖 `icons/<包ID>.png` / `banners/<包ID>.png`，push |
| 新包要 depiction | 复制任一现有 depiction 改内容，enrich 自动注入引用 |

## 维护规则（踩坑沉淀，务必遵守）

1. **YAML 块内脚本必须单行**：`run: |` 里嵌多行 python 内联，续行缩进低于块基准 = workflow 整体失效（dispatch 报 422）。已踩两次。
2. **depiction 改内容必伴随哈希变化**：`?v=` 是内容哈希，所以**只能通过 enrich 写 depiction**（或保证 JSON 序列化格式与脚本一致），手改后要重跑 enrich 让哈希更新。
3. **本机改仓库前先 `git pull --rebase`**：CI 机器人随时可能提交；冲突时以「重跑 enrich + build-homepage 再提交」解决，不手解 Packages.gz 二进制冲突。
4. **JBOpenReborn 分区 = roothide，定论不再搬动**（2026-09-23 用户三次确认后定格）。
5. **Workflow 文件的推送需要 Token 有 workflow scope**：远程 URL 内嵌的 ghp_ token（repo+workflow）可用；钥匙串里 hejunjiea 的 fine-grained token 无此权限，API 调用注意区分。
6. 私有仓库（hejunjiea）的 Actions 被 billing 卡住时，一切依赖它的 CI 不可用——这也是「拉取」方向设计成公开仓库主动拉的原因。

## 环境凭据（本机 Mac）

- `git credential`（钥匙串）：hejunjiea 账号 fine-grained token——可读私有仓库、API 读操作；对公开仓库只读
- 公开仓库 remote URL 内嵌：ghp_ 经典 token（repo + workflow scope）——git push（含 workflow 文件）、API dispatch 用它提取自 remote URL
