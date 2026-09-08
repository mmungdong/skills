# crwu-dws references/00 —— 目录快照 schema / 渲染规则（M1/M2/M3 共用）

> 版本 v2（2026-09-08，随 crwu-dws v0.3：落点迁移到目录缓存层 + M3 支持）。
> 本文档随技能安装（源仓 `skills/crwu-dws/references/00-目录快照schema.md` 与运行时双份）；
> 改前先读 `docs/design-crwu-dws.md`（§6 缓存与实时性模型、§10 D8–D11）。

## 1. 用途

"知识库层级目录"的机器可读形态，三模式共用：

- M1：写目录缓存（`~/.crwu/knowledge/dws-dir-cache/<库名>/目录快照.json`）并展示。
- M2：收尾写入 `knowledge/.crwu-directory.json`（案例副本，同 schema）。
- M3：node-index 的数据源（快照更新后重建索引，见 references/02）。

**内容红线**：本 schema 只承载目录元数据；任何正文内容（文档正文/单元格/附件内容）不属于本文件及本缓存层（红线：references/02 §1.2 正文不缓存）。

## 2. 快照 JSON schema（`crwu.kb-catalog.snapshot.v1`）

```jsonc
{
  "schema": "crwu.kb-catalog.snapshot.v1",
  "generated_at": "2026-09-08T10:30:00+08:00",   // ISO8601 带时区（=本次在线遍历完成时刻）
  "profile": { "id": "…", "isOrgCurrent": true }, // 执行 profile 证据（真实返回）
  "mode": "M1|M2",                                // 产出方
  "space": {
    "name": "中瑞世联 AI 测试知识库",
    "workspaceId": "…",                            // 来自真实返回
    "spaceType": "orgWikiSpace|myWikiSpace",        // 只取服务端真实返回；缺席=null，不按请求值伪造
    "scope_evidence": {
      "requestedType": "orgWikiSpace",              // 顶层请求范围
      "autoPageComplete": true,
      "pagesFetched": 1
    }
  },
  "stats": { "total_nodes": 0, "folders": 0, "docs": 0, "max_depth": 0, "complete": true },
  "nodes": [                                        // 前序展开序（根层在前，children 紧跟父节点）
    {
      "nodeId": "…",                                // 服务端 ID，名称永不替代 ID
      "name": "…",                                  // 原文
      "type": "folder|adoc|axls|able|appt|adraw|amind|未知原值",
      "parentFolderId": null,                        // 根层=null
      "depth": 0,                                    // 根层=0
      "children": [ … ],                             // 嵌套子节点（同构）
      "evidence": {
        "hasChildren": null,                          // 服务端/规范化别名；缺席=null，不作剪枝依据
        "page": { "autoPageComplete": true, "pagesFetched": 1, "itemsInPage": 20 }
      }
    }
  ],
  "failures": []                                     // 空=完整；否则逐条 {nodeId?, step, error}
}
```

## 3. 字段语义（不变量）

- **名称不替代 ID**：所有在线操作只认 `nodeId`；`name` 仅展示与本地文件命名（M2）。
- **type 白名单**：`folder/adoc/axls/able/appt/adraw/amind`；白名单外原样保留字符串，禁止归类/猜测。
- **parentFolderId**：根层 null；服务端未提供 → null 且 evidence 注明，不推断补值。
- **hasChildren**：只提示，**不作剪枝依据**；与实际 `+node-list` 展开不一致时如实记录，不当作失败也不反向剪枝。
- **complete 判定**：仅当遍历全部完成、`failures=[]`、每页 `autoPageComplete=true` → `stats.complete=true`；否则 false。
- **快照绝不携带正文**：任何字段不得内嵌/外链"取到的正文内容"（临时文件路径若被记录，仅作一次性传递用，随临时区清理）。

## 4. 渲染规则（`目录树.md`）

```
# <库名> 目录树
> workspaceId: <…> ｜ spaceType: <…> ｜ 扫取: <ISO8601> ｜ profile: <…>
> 节点 <total>（folder <folders> / 文档 <docs>）/ 深度 <max> ｜ complete: true|false

<顶层folder或文档>/
├─ <子folder>/                    [F]
│  └─ <文档名>                    adoc
└─ <根层文档名>                    axls
```

- folder 名后接 `/` 且行尾标 `[F]`；文档行尾标类型；未知 type 原样输出 + 注"type 未识别"。
- 树内条目不得超出快照 nodes；快照是事实源、树是视图；库身份标注（workspaceId/spaceType/时间/统计/complete）不允许缺失（多库并存不混库）。

## 5. 摘要口径（聊天展示）

- M1：`命中 <n> 库` → 每库一行：`<库名>（<spaceType>）workspaceId=<…>：节点 <total>/folder <folders>/深度 <max>，缓存 <绝对路径>（fetched_at=<…>）`；failures 非空附"部分失败"清单；`complete=false` 显式"目录未完整（缓存未更新）"。
- M2：`knowledge/ 更新：成功 N / 跳过 S / 失败 F`，失败逐项一行；附"远端已不存在（本地保留）"条数；**附镜像时点**："本镜像 = <exportedAt> 快照，仅供本案参考；需最新请重跑或 M3 单篇拉取"。
- M3：见 references/02 §6 报告口径。
- 全部产物给出绝对路径。

## 6. 命名与落盘（M1 = 目录缓存层，v0.3 起）

- 缓存根：`~/.crwu/knowledge/dws-dir-cache/`（**与 CRWU_KB_ROOT=knowledge-base 子树同级隔离**；kb_tool 不扫描此层；此层不是事实源）。
- 每库子目录：`dws-dir-cache/<精确库名>/`；库名清洗非法字符 `\/:*?"<>|` 与首尾空白（空 → workspaceId）；同名不同 spaceType 多库 → 子目录追加 `-<spaceType>`。
- 文件：`目录快照.json`、`目录树.md`、`node-index.json`（references/02 §3 schema）、`.cache-meta.json`（references/02 §3 schema；身份语义见 §2）。
- 缓存身份与清理：缓存目录身份 = `.cache-meta.json.space`（name+workspaceId，真实返回）；身份与目标库名不一致 → 目录被清理层整体删除后在线重下（references/02 §2 / SKILL.md §5.0）。
- **原子替换**：先写 `.tmp-*` 再 rename 覆盖；写失败不得留下半截"正式"文件（宁可保留旧缓存并在 meta 说明）。
- 旧落点 `~/.crwu/kb-catalog/`（v0.1/0.2）：不再写入；既有文件保留待人工清理，本技能不迁移不删除。
