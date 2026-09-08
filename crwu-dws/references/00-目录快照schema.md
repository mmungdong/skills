# crwu-dws references/00 —— 目录快照 schema / 渲染规则（M1/M2 共用）

> 版本 v1（2026-09-08）。本文档随技能安装（源仓 `skills/crwu-dws/references/00-目录快照schema.md` 与
> 运行时双份）；改前先读 `docs/design-crwu-dws.md`。

## 1. 用途

M1 与 M2 共用的"知识库层级目录"机器可读形态：

- M1：产物 `目录快照.json`（落盘 `~/.crwu/kb-catalog/<精确库名>/`）。
- M2：收尾写入 `knowledge/.crwu-directory.json`（该库遍历快照，evidence 与 failures 复用于审计追溯）。

## 2. 快照 JSON schema（`crwu.kb-catalog.snapshot.v1`）

```jsonc
{
  "schema": "crwu.kb-catalog.snapshot.v1",
  "generated_at": "2026-09-08T10:30:00+08:00",   // ISO8601 带时区
  "profile": { "id": "…", "isOrgCurrent": true }, // 执行 profile 证据（真实返回）
  "mode": "M1|M2",                                // 产出方
  "space": {
    "name": "中瑞世联 AI 测试知识库",
    "workspaceId": "…",                            // 来自真实返回
    "spaceType": "orgWikiSpace|myWikiSpace",        // 只取服务端真实返回；缺席=null，不按请求值伪造
    "scope_evidence": {
      "requestedType": "orgWikiSpace",              // 顶层请求范围（dingtalk-wiki 语义）
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

- **名称不替代 ID**：所有后续操作只认 `nodeId`；`name` 仅展示与本地文件命名。
- **type 白名单**：`folder/adoc/axls/able/appt/adraw/amind`；白名单外**原样保留字符串**，禁止归入任何已知类型或猜测（如"看起来像文档"→ 不算 adoc）。
- **parentFolderId**：根层 null；服务端未提供 → null 且 `evidence` 注明"parentFolderId 未返回"，不得用名称/层级推断补值。
- **hasChildren**：服务端返回或规范化别名；缺席为 null。**遍历以实际 `+node-list` 展开结果为准**：hasChildren=true 但展开为空 → 如实记录"元数据与展开不一致"，不当作异常失败，也不反向用 false 跳过展开。
- **complete 判定**：仅当遍历全部完成且 `failures=[]` 且每页 `autoPageComplete=true` 时 `stats.complete=true`；否则 false，且摘要必须呈现部分结果说明。

## 4. 渲染规则（`目录树.md`）

```
# <库名> 目录树
> workspaceId: <…> ｜ spaceType: <…> ｜ 扫取: <ISO8601> ｜ profile: <…>
> 节点 <total>（folder <folders> / 文档 <docs>）/ 深度 <max> ｜ complete: true|false

<顶层folder或文档>/
├─ <子folder>/                    [F]
│  └─ <文档名>                    adoc
└─ <根层文档名>                    axls
   └─ …（type=未知原值 → 原样输出 + 注"type 未识别"）
```

- folder 缩进名后接 `/` 并在行尾标 `[F]`；文档节点行尾标类型（adoc/axls/…）。
- 树内任何条目不得超出快照 nodes 内容；渲染只是视图，快照才是事实源。
- 顶层（摘要前的头块）必须带 workspaceId/spaceType/时间/统计与 complete 标记——**库身份标注不允许缺失**（多库并存时不混库）。

## 5. 摘要口径（聊天展示）

- M1：`命中 <n> 库` → 每库一行：`<库名>（<spaceType>）workspaceId=<…>：节点 <total>/folder <folders>/深度 <max>，产物 <绝对路径>`；`failures` 非空 → 附"部分失败：<每项一行>"；`complete=false` → 显式"目录未完整（见 failures）"。
- M2：`knowledge/ 更新：成功 N / 跳过 S / 失败 F`，失败逐项一行原因；另附"远端已不存在（本地保留）"清单条目数。
- 全部产物给出**绝对路径**（便于用户直接打开/后续步骤引用）。

## 6. 命名与落盘（M1）

- 落盘目录：`~/.crwu/kb-catalog/<精确库名>/`；库名清洗非法字符 `\/:*?"<>|` 与首尾空白（空结果 → 用 workspaceId）。
- 文件：`目录树.md`、`目录快照.json`（同名已存在 → 覆盖写，不带时间戳；"最新一次"语义由调用方负责）。
- 多库命中 → 每库独立子目录（同名不同 spaceType 时子目录追加 `-<spaceType>`），互不覆盖。
