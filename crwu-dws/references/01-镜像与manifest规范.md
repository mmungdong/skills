# crwu-dws references/01 —— M2 镜像与 manifest 规范（`knowledge/` 落盘）

> 版本 v1（2026-09-08）。本文档随技能安装（源仓与运行时双份）；改前先读
> `docs/design-crwu-dws.md` §10（D6/D7 决策点）与 `references/00`（快照 schema 引用）。

## 1. 目标布局

```
<案例目录>/                      # = 源审核数据文件所在目录的父级（crwu-audit 材料包旁）
├── <源审核数据文件…>            # crwu-audit 材料包（部署约定注入，与本技能无关，只读不碰）
└── knowledge/                   # ← M2 唯一落点（与源审核数据文件同级）
    ├── <顶层folder>/<子folder>/<文档名>.md
    ├── <文档名>-<nodeId前8>.md   # 仅"不同 nodeId 同名"冲突时
    ├── .crwu-manifest.jsonl     # 镜像清单（下文 §3）
    └── .crwu-directory.json     # 目录快照（references/00 schema，mode="M2"）
```

- 点文件（`.crwu-*`）是镜像元数据，不映射任何远端节点；agent 读取参考文档时跳过它们。
- 只有 folder/adoc 参与镜像：folder → 本地目录；adoc → `.md` 文件；其余类型（axls/able/appt/adraw/amind/未知）→ `skipped`，不落正文（v0.1，决策点 D7=跳过+如实报告）。

## 2. 命名与冲突规则（确定性，可复跑）

1. **清洗**：本地目录/文件名去除 `\/:*?"<>|` 与首尾空白；清洗后为空 → 用 `nodeId` 前 8 位兜底。
2. **folder 目录**：按层级映射为 `<folder名>`（清洗后）；同层重名目录 → 后建者追加 `-<nodeId前8>`（先来后到，第二次及以后运行按 manifest 已登记路径**回稳**——重跑不因顺序漂移产生新目录）。
3. **adoc 文件**：规范名 `<节点名>.md`（清洗后）；冲突时按 nodeId 判定：
   - 规范名已被**同一 nodeId** 占用（=上次运行登记）→ 原位覆盖（内容更新）；
   - 规范名被**不同 nodeId** 占用（库内同名文档）→ 本次节点改为 `<节点名>-<nodeId前8>.md`。
4. **回稳原则**：任何已登记 `{nodeId → localPath}` 的映射在重跑中保持不变（追加/覆盖，不搬移）；幂等性以 manifest 校验为准（§4）。

## 3. manifest JSONL 格式（`.crwu-manifest.jsonl`）

每行一个 JSON 对象；首行必须是 header，其后 entries/skipped/failures 按发生序追加（不重排历史，仅在重跑覆盖时更新同 nodeId entry 行的 localPath/exportedAt）。

```jsonc
// header（首行）
{ "schema": "crwu.kb-mirror.manifest.v1", "mode": "M2",
  "space": { "name": "…", "workspaceId": "…", "spaceType": "…" },
  "case_dir": "<案例目录绝对路径>", "started_at": "ISO8601" }

// entry（成功，每节点一行）
{ "kind": "entry", "nodeId": "…", "name": "…", "type": "adoc",
  "folderPath": "knowledge/<顶层folder>/…",
  "localPath": "knowledge/<顶层folder>/…/<节点名>.md",
  "exportedAt": "ISO8601",
  "evidence": { "export": { "localPath": "…", "sizeBytes": 1234 } } }

// skipped（非 adoc 非 folder）
{ "kind": "skipped", "nodeId": "…", "name": "…", "type": "axls",
  "reason": "v0.1 不下载该类型正文" }

// failures（单节点失败）
{ "kind": "failure", "nodeId": "…", "name": "…", "error": "…" }
```

- **语义**：`localPath` 一律相对案例目录（与 cwd 契约一致、可整体搬移）；绝对路径只在 header `case_dir` 出现一次。
- 导出回执证据：`dws doc +export` 返回 `localPath` 且 `sizeBytes>0` 即终态（dingtalk-doc 契约：禁 ls/stat 二次验证）；evidence 原样抄录回执字段，不补造。

## 4. 幂等 / 覆盖 / 残留语义

| 远端状态 | 本地动作 | 记录 |
| --- | --- | --- |
| 节点未变 / 内容更新 | 同 nodeId 规范路径**原位覆盖导出** | entry 行更新 exportedAt（整行重写最新） |
| 新增 folder/adoc | 建目录 / 新增文件 | 新 entry |
| 库内重名新增（不同 nodeId） | 追加 `-<nodeId前8>` | 新 entry（不覆盖他人） |
| 远端已删除 | **本地保留不动** | 摘要列"远端已不存在（本地保留，待人工清理）"清单；manifest 不删行、备注 `remote_deleted: true` |
| 导出失败 | 不产生/不覆盖本地文件 | failure 行；重跑时重试该节点 |
| 类型白名单外 | 不下载 | skipped 行 |

- 重跑 = 全量覆盖式镜像（不做增量跳过）：语义最简单、保证"实时=钉钉当前版"；性能优化留待路线图（按版本事件跳过未变化节点）。
- 收敛判据（P4）：本次成功+跳过+失败 == 目录树 folder/adoc 相关节点数，且 entry+skipped+failure 覆盖全部本次遍历节点 → 才可称镜像完成。

## 5. 摘要口径（聊天展示）

1. 首行：`<库名>（<spaceType>，workspaceId=<…>）→ knowledge/ 更新完成/部分完成`；
2. `成功 N / 跳过 S / 失败 F`；跳过与失败各列一行：`<名称>（<类型>）：<原因/错误>`；F>0 → 附"可重跑本技能补齐"；
3. "远端已不存在（本地保留）"清单条数（≤10 行内联，超出给计数）；
4. 产物：`<案例目录>/knowledge/`（绝对路径），提示 agent 后续审核参考从该目录读取最新文档。

## 6. 与 crwu-audit 的口径边界（本技能只登记、不执行）

- `knowledge/` = crwu-audit 叶子推理时**实时参考**文档；`CRWU_KB_ROOT=~/.crwu/knowledge/knowledge-base` = **发布/门禁基准**（A 门禁/试点判定仍以其为准）。
- 两套口径的读取优先级与路径约定属 crwu-audit 族维护（走 crwu-audit-optimize 流程），本规范不预先改写任何 audit 文件；本清单 + `.crwu-directory.json` 是"本次拉取内容与证据"的追溯入口。
