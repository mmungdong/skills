# crwu-dws references/01 —— M2 案例镜像与 manifest 规范（`knowledge/` 落盘）

> 版本 v2（2026-09-08，随 crwu-dws v0.3：明确"案例镜像≠缓存"+ exportedAt 时效语义）。
> 本文档随技能安装（源仓与运行时双份）；改前先读 `docs/design-crwu-dws.md` §6/§10（D6/D7/D9）与 references/00。

## 1. 目标布局

```
<案例目录>/                      # = 源审核数据文件所在目录的父级（crwu-audit 材料包旁）
├── <源审核数据文件…>            # crwu-audit 材料包（部署约定注入，与本技能无关，只读不碰）
└── knowledge/                   # ← M2 唯一落点（与源审核数据文件同级）
    ├── <顶层folder>/<子folder>/<文档名>.md
    ├── <文档名>-<nodeId前8>.md   # 仅"不同 nodeId 同名"冲突时
    ├── .crwu-manifest.jsonl     # 镜像清单（§3）
    └── .crwu-directory.json     # 目录快照（references/00 schema，mode="M2"）
```

- 点文件（`.crwu-*`）是镜像元数据，不映射远端节点；agent 读参考文档时跳过。
- folder → 本地目录；adoc → `.md`；其余类型（axls/able/appt/adraw/amind/未知）→ `skipped` 不落正文（v0.1，D7）。
- **案例镜像不是缓存**：它是"某导出时点"的案例材料快照（用户显式要求留档）；`~/.crwu/knowledge/dws-dir-cache/` 目录缓存层永远不接收 M2 的任何文件（§6）。

## 2. 命名与冲突规则（确定性，可复跑；同 v0.2）

1. 清洗：本地目录/文件名去除 `\/:*?"<>|` 与首尾空白；清洗后为空 → 用 nodeId 前 8 位兜底。
2. folder 目录同名冲突 → 后建者追加 `-<nodeId前8>`；重跑按 manifest 已登记路径回稳（不漂移）。
3. adoc 规范名 `<节点名>.md`：已被同一 nodeId 占用 → 原位覆盖（=内容更新）；被不同 nodeId 占用 → 追加 `-<nodeId前8>`。
4. 回稳原则：已登记 `{nodeId → localPath}` 重跑保持不变；幂等以 manifest 校验为准。

## 3. manifest JSONL 格式（`.crwu-manifest.jsonl`）

首行 header；其后 entry/skipped/failure 按发生序追加；重跑覆盖时更新同 nodeId entry 行。

```jsonc
// header（首行）
{ "schema": "crwu.kb-mirror.manifest.v1", "mode": "M2",
  "space": { "name": "…", "workspaceId": "…", "spaceType": "…" },
  "case_dir": "<案例目录绝对路径>", "started_at": "ISO8601" }

// entry（成功，每节点一行）
{ "kind": "entry", "nodeId": "…", "name": "…", "type": "adoc",
  "folderPath": "knowledge/<顶层folder>/…",
  "localPath": "knowledge/<顶层folder>/…/<节点名>.md",
  "exportedAt": "ISO8601",                 // 现场导出完成时刻（时效语义依据）
  "evidence": { "export": { "localPath": "…", "sizeBytes": 1234 } } }

// skipped（非 adoc 非 folder）
{ "kind": "skipped", "nodeId": "…", "name": "…", "type": "axls",
  "reason": "v0.1 不下载该类型正文" }

// failures（单节点失败）
{ "kind": "failure", "nodeId": "…", "name": "…", "error": "…" }
```

- `localPath` 一律相对案例目录；绝对路径只在 header `case_dir` 出现一次。
- 导出回执证据：`dws doc +export` 返回 `localPath` 且 `sizeBytes>0` 即终态（dingtalk-doc 契约：禁 ls/stat 二次验证）；evidence 原样抄录回执，不补造。

## 4. 幂等 / 覆盖 / 残留语义（同 v0.2）

| 远端状态 | 本地动作 | 记录 |
| --- | --- | --- |
| 未变 / 内容更新 | 同 nodeId 原位覆盖导出 | entry 行更新 exportedAt |
| 新增 | 建目录 / 新增文件 | 新 entry |
| 库内重名新增 | 追加 `-<nodeId前8>` | 新 entry |
| 远端已删除 | **本地保留不动** | 摘要列"远端已不存在（本地保留，待人工清理）"；manifest 备注 `remote_deleted: true` |
| 导出失败 | 不产生/不覆盖本地文件 | failure 行；重跑重试 |
| 类型白名单外 | 不下载 | skipped 行 |

- 重跑 = 全量覆盖式镜像（不做增量跳过）：语义简单、保证"镜像时点=钉钉当时版"。
- 收敛判据（P4）：成功+跳过+失败 == 目录树 folder/adoc 相关节点数，且覆盖本次全部遍历节点 → 才可称镜像完成。

## 5. 摘要口径（聊天展示）

1. 首行：`<库名>（<spaceType>，workspaceId=<…>）→ knowledge/ 更新完成/部分完成`；
2. `成功 N / 跳过 S / 失败 F`；跳过/失败各列一行原因；F>0 → "可重跑本技能补齐"；
3. "远端已不存在（本地保留）"条数（≤10 行内联）；
4. **时效行（v0.3 必含）**：`本镜像 = <最新 exportedAt> 快照，仅供本案参考；跨案/需要再最新 → 重跑 M2 或对单篇走 M3 实时拉取`；
5. 产物绝对路径 `<案例目录>/knowledge/`。

## 6. 边界与口径（v0.3 补强）

- **正文永不进入目录缓存层**：M2 产物只落在案例 `knowledge/`；禁止把镜像内容复制到 `~/.crwu/knowledge/dws-dir-cache/`（或任何"缓存"语义目录）充当可复用正文来源——正文复用即过期（红线 D9）。
- 口径：案例 `knowledge/`（本次下载物）= 本次审核实时参考（下载时刻=最新；文件零缓存）；知识库正文**无发布/试点门禁**（口径 2026-09-08：文档即权威、下载即审；`CRWU_KB_ROOT` 静态根仅维护/离线归档、不冒充实时）；目录缓存 = 查找加速（无正文）。本清单 + `.crwu-directory.json` 是本次下载内容与证据的追溯入口。
