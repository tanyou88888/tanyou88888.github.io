# tanyou88888 越狱软件源 · 运维文档

> 本文档面向维护者（人类或 AI agent），记录源结构、自动化流水线、上游同步、维护规则与踩坑史。
> 面向用户的页面是 [index.html](https://tanyou88888.github.io/)。

## 源信息

| 项 | 值 |
|---|---|
| 源地址 | `https://tanyou88888.github.io/sileo/` |
| 显示名 / 描述 | Label: tanyou88888 分屏源（Release 文件可改） |
| 支持管理器 | Sileo / Zebra / Cydia |
| 包数量 | 10 个（见下表） |
| 分区规则 | **声明式按目录**：`debs/rootless/` 或 `debs/roothide/`，与文件名、control 内容无关 |

## 上游同步（配置驱动：`sileo/meta/upstreams.json`）

加上游 = 在 JSON 里加一条 `{repo, private, asset_suffix, dest, package}`，**无需改 workflow**。
字段：repo=仓库；private=是否需 `JBOPENREBORN_TOKEN`；asset_suffix=资产名后缀（如 arm64e.deb）；dest=rootless|roothide；package=记 meta 日期用的包 ID。

## 软件包与上游同步（4 个上游）

| 包（Package ID） | 分区 | 来源 | 同步方式 |
|---|---|---|---|
| JBOpenReborn (com.charlieleung.trollopenreborn) | roothide | `hejunjiea/JBOpenReborn`（私有） | 自动，最新 Release |
| TrollOpen 分屏 (com.charlieleung.trollopenjb) | roothide | 手动 | 一次性收录 |
| iOS MCP (com.witchan.ios-mcp) | roothide | `witchan/ios-mcp`（公开） | 自动，arm64e 资产（上游 roothide=arm64e） |
| 隐藏小白条/横条 (cn.llld.*) | roothide | 手动 | 一次性收录 |
| Virtual Mac (com.mac.virtual) | rootless | `nfzerox/VirtualMacOniPad`（公开） | 自动，**上游明确不支持 roothide**，固件限 14.5–16.3.1 |
| Frida (re.frida.server) | rootless | `frida/frida`（公开） | 自动，arm64 资产（已验尸 `./var/jb/` = rootless 构建） |
| 强制第三方输入法 (llld.keyboard)、FiveColumnsCC、最近通话时间 | rootless | 手动 | 一次性收录 |

**分区判定依据留档**（勿凭感觉搬动）：
- JBOpenReborn = roothide：用户 2026-09-23 三次确认定论；
- ios-mcp = roothide：上游 README 表格 roothide→arm64e；
- VirtualMac = rootless：上游 README 明确「不支持 Dopamine-roothide」；
- Frida = rootless：deb 解包路径 `./var/jb/`。

## 目录结构

```
index.html                      主页（build-homepage.py 自动生成，勿手改）
.github/workflows/
  apt-repo.yml                  APT 索引流水线（手动上传链路）
  pull-release.yml              拉取流水线（发布主链路）：4 上游同步 + 自建索引
  两条共用 concurrency: repo-write（互斥，cancel-in-progress）
sileo/
  Release                       Label/Description 手改；校验和段由 enrich 维护
  Packages / Packages.gz        索引（流水线生成，勿手改）
  debs/rootless/  debs/roothide/
  depictions/<包ID>.json        depiction（enrich 自动维护 Changelog/Version/Requires/Size/Released）
  icons/<包ID>.png              图标（存在即注入）
  banners/<包ID>.png            头图横幅
  meta/release-dates.json       发布日期表（手动包从 deb 构建时间戳取证补录）
  scripts/enrich-index.py       核心：索引后处理（规则见下）
  scripts/build-homepage.py     主页生成（含最近更新时间线、OG 分享卡）
```

## enrich-index.py 自动化规则（每次重建全量幂等执行）

1. **Icon**：`icons/<包ID>.png` 存在即注入（强制覆盖）
2. **SileoDepiction**：`?v=` = depiction **内容哈希前 8 位**（内容变 URL 自动变，Sileo 必刷新）
3. **分类归一**：按目录覆写 Section（rootless 插件 / roothide 插件）
4. **更新日记**：从 control `Changelog` 自动渲染；deb 删除后日记块自动清除
5. **版本保留**：每包最近 `KEEP_VERSIONS=3` 版，更旧自动删
6. **Requires / Size / Released**：自动生成（分区+固件 / 最新 deb 大小 / meta 日期）
7. **Release 校验和**：Packages(.gz) 的 MD5Sum/SHA256（gz mtime=0 定哈希）
8. 删除废弃小写 `Sileodepiction` 字段

## 流水线

### pull-release.yml（发布主链路，每 15 分钟 + 手动/API 触发）
1. 同步 JBOpenReborn（私有，需 secret `JBOPENREBORN_TOKEN`：hejunjiea 账号、对私有仓库 Contents Read-only）
2. 同步 witchan/ios-mcp（公开，arm64e）
3. 同步 nfzerox/VirtualMacOniPad（公开，任意 deb 资产）
4. 同步 frida/frida（公开，iphoneos-arm64）
5. **自建索引**（scan + enrich + homepage）→ 提交
- 可选通知 secret：`BARK_URL` / `TELEGRAM_BOT_TOKEN`+`TELEGRAM_CHAT_ID`
- 私有仓库资产必须走 **API 端点 + Accept: application/octet-stream**（browser_download_url 404）

### apt-repo.yml（手动上传链路）
- 触发：push（debs/depictions/icons/banners/Release/scripts 路径变更）
- **GITHUB_TOKEN 推送不触发其他 workflow**（防递归）——所以 pull 自建索引，不依赖链式触发

### 并发保护
两流水线共用 `concurrency.group: repo-write` + `cancel-in-progress: true`。

## 日常操作

| 场景 | 做法 |
|---|---|
| JBOpenReborn 发新版 | 私有仓库发 Release 附 deb（control 带 Changelog）→ 15 分钟内自动上架 |
| 其他上游更新 | 自动（15 分钟轮询） |
| 手动加包 | deb 丢对应分区目录，push（文件名随意） |
| 删包/版本 | 删 deb push，索引与日记自动清 |
| 换图标/横幅 | 覆盖 icons/banners 对应文件，push |
| 新包接 depiction | 复制现有模板改内容 |
| 立刻拉取 | API dispatch（agent 可代跑，约 1 分钟全链路） |

## 账号与凭据（本机 Mac）

| 凭据 | 位置 | 权限 |
|---|---|---|
| hejunjiea fine-grained token | 钥匙串 | 私有仓库读 + 公开源仓库写（2026-09-25 起为 Write 协作者） |
| tanyou88888 ghp_ classic token | 钥匙串（remote URL 带用户名路由，不再明文内嵌） | 源仓库 repo + workflow |

两账号均有源仓库写权限，任一失效不影响运维。ghp_ 曾在排查中暴露，**待 regenerate**。

## 维护规则（踩坑沉淀，务必遵守）

1. **YAML 块内脚本必须单行**——多行 python 内联缩进低于块基准 = workflow 整体失效（dispatch 422）。已踩两次。
2. **本机改动前先 fetch-rebase**：CI 每 15 分钟可能提交；冲突解法 = 重跑 `enrich-index.py` + `build-homepage.py` 再提交，不手解 Packages.gz 二进制冲突。
3. **大包推送慢不是挂死**：20MB 级 deb 上传需数分钟，加大超时；钥匙串读取偶发卡住时用「显式凭据 URL 直推」绕开。
4. **JBOpenReborn 分区 = roothide 定论**，勿再搬动（2026-09-23 用户三次确认）。
5. Workflow 文件推送需 token 带 workflow scope。
6. 私有仓库（hejunjiea）Actions 被 billing 卡住——一切依赖它的 CI 不可用，「拉取」方向因此设计为公开仓库主动拉。
7. token/敏感值曾出现在会话输出中——本仓库相关 token 建议 rotate。

## 历史大事记

- 2026-09-20~21：源从零搭建（图标/depiction/更新日记/分区/主页/自动化）
- 2026-09-22：JBOpenReborn 发布链路打通（0.6.103 首次自 Release 上架）
- 2026-09-23：分区定论 roothide；enrich 全自动化（日记/分类/保留/哈希缓存）
- 2026-09-24：0.6.214 黑帧修复版全链路自动上架验证成功；并发保护
- 2026-09-25：ios-mcp / VirtualMac / frida 三上游接入；双账号协作者打通
