---
name: crwu-dws
description: >-
  中瑞世联 AI 测试知识库（钉钉 wiki）【只读域】技能：M1 查询/导出该知识库（按精确库名解析
  组织+个人全范围，多命中全导）的完整层级目录（聊天摘要+目录树+JSON 快照，带分页证据）；
  M2 把 crwu-audit 及子 skill 推理时依赖的参考知识文档按库内目录结构批量导出
  （adoc→markdown 正文）到与源审核数据文件同级的案例目录 knowledge/ 下，供审核实时参考
  （员工在钉钉更新 → AI 取到最新版）。对钉钉零写操作。泛化钉钉知识库/doc 管理走
  dingtalk-wiki/dingtalk-doc；本地 CRWU_KB_ROOT/kb_tool、审核意见不属本技能。
  命令前缀：dws wiki / dws doc。设计见 docs/design-crwu-dws.md。
metadata:
  cli_version: ">=0.2.14"
  category: crwu
  requires:
    bins:
      - dws
---

# crwu-dws（钉钉知识库只读域：M1 目录查询 / M2 知识文档批量下载）

## 0. 目录结构与加载
- `SKILL.md`（本文件，入口；双模式流程 + 只读白名单）
- `references/00-目录快照schema.md` —— 快照 JSON schema / 字段语义 / 渲染规则（M1/M2 共用）
- `references/01-镜像与manifest规范.md` —— M2 落盘布局 / 命名冲突 / manifest JSONL / 幂等与残留语义
- 改前必读 `docs/design-crwu-dws.md`（§10 决策点）；改动按仓库纪律源仓+运行时 `~/.dsh/skills` 双份同步（diff -r 为空）

## 1. 触发与模式消歧

| 用户意图（例） | 模式 | 主要产物 |
| --- | --- | --- |
| "看/查/列 中瑞世联 AI 测试知识库 的 目录/层级/树/结构"、"某文档在哪个目录" | **M1 目录查询** | 摘要 + `目录树.md` + `目录快照.json` → `~/.crwu/kb-catalog/<精确库名>/` |
| "下载/同步/镜像 知识文档到本次审核材料旁"、"要最新/实时参考文档（knowledge）" | **M2 批量下载** | `<案例目录>/knowledge/` 镜像 + `.crwu-manifest.jsonl` + `.crwu-directory.json` |

- 目标库名默认固定「中瑞世联 AI 测试知识库」；用户显式给出其他库名时按同流程处理（流程与产物不变，产物目录以实际库名为准）。
- **不触发**：泛化钉钉知识库/doc 管理（→ `dingtalk-wiki` / `dingtalk-doc`）；本地 `~/.crwu/knowledge/knowledge-base` 规则查询或 kb_tool 操作（→ 对应本地工具/部署）；审核报告材料本身（→ `crwu-audit`）。
- M2 通常由 crwu-audit 编排者在审核前调用（给 AI 装实时参考）；也可独立按需调用。

## 2. 执行契约（dws 最小集）
- 只通过 `dws` CLI；结构化读取用 `--format json`，按真实返回判断；已知命令直接执行，只有 leaf 参数/flag 不确定时读一次精确 Schema/Help；不加载产品级 Catalog 选路。
- 不猜命令、flag、字段、ID、名称；后续 ID 必须来自真实返回；解析/读取/导出全程同一 profile（多账号只用 `isOrgCurrent=true` 默认账号或用户明确指定）。
- 不输出或记录 token 等凭据；认证/权限/profile/未知错误 → 只读 `dingtalk-shared` 对应 reference，不连续猜测。
- 时间戳面向用户时转当前时区可读时间。
- **对钉钉零写（硬白名单）**：wiki 域仅允许 `space-list/space-search/space-get/node-list/node-search/node-get`；doc 域仅允许 `+export`（远端只读、产物落本地）。**禁止** wiki `+space-create/+node-create/+node-copy/+move/+move-to-drive/+node-delete/+member-*/+feed` 及 doc 一切写命令——本技能任何情况不执行。
- 本技能唯一的"写" = 本地产物文件（M1 快照 / M2 镜像），均按用户意图落盘。

## 3. P1 库解析（M1/M2 共用，只读）
1. 确认 profile；M2 额外先确认案例目录（§6.1）。
2. 分范围全量取空间并**精确名匹配**：
   `dws wiki +space-list --type orgWikiSpace --limit 50 --page-all --format json`；
   `dws wiki +space-list --type myWikiSpace --limit 50 --page-all --format json`。
   （`+space-search` 只作候选浏览，不作唯一性证据。）
3. 判据（dingtalk-wiki 语义）：
   - 列表顶层 `requestedType` 必须等于本次请求范围；`autoPageComplete=true` 才可用"缺席"证无；
   - 命中 0 → 报告扫描范围 + 分页完成证据 + 相似候选名（若有），**不编造**；可询问是否换名/换范围再跑；
   - 命中 ≥1 → **全部**进入处理列表，各自保留真实 `workspaceId`、`spaceType`（只取服务端真实返回）与来源范围标注；不合并、不猜唯一。

## 4. P2 目录遍历（M1/M2 共用，只读，DFS 递归）
1. 根层：`dws wiki +node-list --workspace <workspaceId> --page-all --format json`（不带 `--folder`）。
2. 对返回中 `type=folder` 的节点递归：`dws wiki +node-list --workspace <workspaceId> --folder <folderId> --page-all --format json`，直至无 folder。
3. 纪律：
   - 每层记录分页证据（`autoPageComplete/pagesFetched/条目数`）并写入快照；
   - `hasChildren`/`extension.hasChildren` 仅作提示，**不作剪枝依据**（防服务端元数据滞后漏枝）；
   - folder 按 nodeId 去重：同一 folder 第二次展开即停止该支并标注"异常环/重复"；
   - 节点字段（nodeId/名称/type/parentFolderId/hasChildren）只取真实返回；未知 type 原样保留，不归类不猜测；
   - 体量防护：节点总数 > 10,000 或深度 > 20 → **停止**，如实报告部分结果与原因（不宣称全量）。
4. 遍历结果 = 内存树（前序展开序），M1/M2 共用同一棵树做产物。

## 5. P3-M1 目录查询产物
1. 快照 JSON：按 `references/00` schema（`crwu.kb-catalog.snapshot.v1`），含 space 元数据与证据、nodes（children 嵌套或平铺+depth，按 00 定稿）、failures。
2. `目录树.md`：缩进树 + 行尾类型标注（folder 标 `[F]`，文档标 adoc/axls/…）；库头附 库名/workspaceId/spaceType/扫取时间/统计。
3. 落盘目录：`~/.crwu/kb-catalog/<精确库名>/`（库名含路径非法字符时清洗，规则见 references/01 §2 命名口径）；已存在则覆盖写。
4. 聊天摘要：命中库数；每库 总节点/folder 数/最大深度/产物路径；failures 非空时附结构化失败清单。

## 6. P3-M2 批量下载（镜像；远端只读 + 本地写）

### 6.1 目标目录决议（禁止猜）
`knowledge/` 的父目录 = **案例目录**（= crwu-audit 源审核数据文件所在目录的**父级**，二者同级）。决议顺序：
1. 编排者/用户在对话中显式给出案例目录路径 → 用之；
2. 部署环境注入的案例目录变量（当前约定名 `CRWU_CASE_DIR`；若注入的是材料包目录则取其父级）→ 用之；
3. 都没有 → **询问用户**案例目录路径，禁止随意落盘。
（M2 由审核编排触发时通常路径已随材料包目录一并注入。）

### 6.2 下载执行
1. 在案例目录下建 `knowledge/`；按 §4 内存树**镜像 folder 结构**为本地同名子目录（目录名/文件名清洗非法字符 `\/:*?"<>|` 与首尾空白；冲突/空名追加 `-<nodeId前8>`）。
2. 对每个 adoc 节点（串行、不并发）：`dws doc +export --node <nodeId> --export-format markdown`（cwd = 案例目录；导出到临时区防同名覆盖），回执含 `localPath` 且 `sizeBytes>0` 即**终态**（不二次 ls/stat 验证）；随后把该文件移动为规范路径 `<folder路径>/<节点名>.md`：
   - 与 manifest 已有登记比对：同 nodeId → 原位覆盖（=内容更新）；不同 nodeId 同名文件 → 本节点追加 `-<nodeId前8>` 后缀；
   - 移动是纯本地操作，移动后不额外 stat（以 +export 回执为终态证据，规范路径记入 manifest）。
3. 结果记账（写入 `.crwu-manifest.jsonl`，schema 见 references/01）：
   - 成功 → entry：`{nodeId, name, type:"adoc", folderPath, localPath, exportedAt, evidence{export{localPath,sizeBytes}}}`；
   - 失败 → failures 追加 `{nodeId, name, error}`，**继续后续节点不中断整批**；认证/权限/profile 类系统性错误 → 停止整批，读 `dingtalk-shared` 对应 reference；
   - 非 adoc 非 folder 节点（axls/able/appt/adraw/amind/未知）→ skipped 追加 `{nodeId, name, type, reason:"v0.1 不下载该类型正文"}`，如实报告。
4. 收尾写入：`.crwu-directory.json` = 本库目录快照（references/00 schema，含 evidence/failures）；manifest 写入模式标识与 space 信息。
5. 远端已删除文档：本地保留旧文件，摘要列出"远端已不存在（本地保留，待人工清理）"清单；**不自动删除**。
6. 摘要：成功 N / 跳过 S / 失败 F（+每项一行原因）与目录树统计核对；产物路径（`<案例目录>/knowledge/`）。

## 7. P4 一致性自查
- M1：快照节点计数 == 遍历完成计数（失败分支如实减除）；不一致 → 不宣称全量并附证据。
- M2：成功+跳过+失败 == 目录树中 folder/adoc 相关节点数；manifest 可复跑（重跑全量覆盖、幂等、条目稳定）；不满足 → 不宣称完成，附部分结果与证据。

## 8. 边界与纪律
- 结果只读自钉钉、不推断：缺 type/父子/导出回执字段 → 如实标注"服务端未返回/未取得"；
- 目录快照与正文内容是**企业数据**：产物路径按约定落盘，不向第三方外传；
- 口径：案例 `knowledge/` = crwu-audit 推理**实时参考**；`~/.crwu/knowledge/knowledge-base`（CRWU_KB_ROOT）= **发布/门禁基准**；两者差异由人工/复核判定（本技能不合并、不互相覆盖）；
- 变更登记纪律：改本技能需同步运行时拷贝并在 `docs/CHANGELOG.md` 记纪要（无 crwu CLI 命令变更时也记 docs 条目）。

## 9. 错误最短路径
1. 空响应/缺失集合/分页未完成：停止后续并返回证据；不拿 `+space-search` 首页唯一候选断言。
2. 认证/权限/profile 错：只读 `dingtalk-shared` 对应 reference（wiki/doc 分册）；不重试猜测命令。
3. 单个节点导出失败：记 failures 继续；系统性失败（连续 >10 或认证类）→ 停止，报告已得部分。
4. 未知 flag/命令：只查当前 leaf Help / 一次 shortcut 清单；不跨产品试探近似命令。
5. 目标目录不可写/不存在父目录：报告路径问题并请用户给可写路径；不静默改落点。
