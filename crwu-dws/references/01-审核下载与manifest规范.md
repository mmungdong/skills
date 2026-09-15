# crwu-dws references/01 —— M2 审核下载与 manifest 规范

> 版本 v4（2026-09-15，随 crwu-dws v0.6：按节点 `extension` 分流的**双取数通道**——`adoc` 走 `doc +export`，可读原生文本 `md`/`txt` 走 `drive +download`，其余记 `skipped`）。
> 版本 v3（2026-09-08）：钉钉是知识正文唯一来源；M2 仅按本次审核清单下载，支持单文件与目录条目。
> 本文档随技能安装；改前先读 references/00 与 references/02。

## 1. 目标布局

```
<案例目录>/
├── <源审核数据文件…>
└── knowledge/                    # 本次审核工作集，跨审核不得复用
    ├── <顶层folder>/<子folder>/<文档名>.md      # extension=adoc（导出）
    ├── <顶层folder>/<子folder>/<文档名>.md      # extension=md（原件即正文，原样下载）
    ├── <顶层folder>/<子folder>/<文档名>.txt     # extension=txt（同上）
    ├── <文档名>-<nodeId前8>.md   # 仅不同 nodeId 同名冲突时
    ├── .crwu-manifest.jsonl
    └── .crwu-directory.json
```

- 点文件是本次下载的追溯元数据，不映射远端节点；读取正文时跳过。
- folder 映射本地目录；**文档按 `extension` 分流**（SKILL.md §2/§6.2）：
  | `extension` | 通道 | 落地 |
  | --- | --- | --- |
  | `adoc` | `dws doc +export --export-format markdown` | `<节点名>.md` |
  | `md` / `txt` | `dws drive +download` | `<节点名>.<extension>`（**原件即正文，不转换**） |
  | 其余 | 不取正文 | 记 `skipped` + 真实 `extension`，不伪造正文 |
- `knowledge/` 不是知识库副本。它只包含本次清单命中的正文，跨审核或重跑必须重新从钉钉下载。
- `dws-dir-cache/` 只存目录元数据，禁止接收 M2 正文。

## 2. 清单项语义

同一清单允许混合：

1. **单文件路径**：不以 `/` 结尾。精确解析到一个节点后只下载该文件；命中目录、零命中或多命中均记 failure。
2. **目录路径**：以 `/` 结尾。精确解析目录后递归下载该目录下全部支持的正文文件。

清单按声明顺序展开并去重；同一 nodeId 只下载一次。清单外零下载。无法解析或下载失败时，记录原始清单项、节点信息（如有）和原因，不得改读本地正文或推测内容。

**展开范围（v0.6 澄清）**："全部支持的正文文件" = `extension` 为 `adoc`/`md`/`txt` 的节点。目录内其余类型（`pdf`/`docx`/`xlsx`/`exe`…）**必须出现在结果里**，但以 `skipped` + 真实 `extension` 记录——**不得静默丢弃**（静默丢弃会让"清单已覆盖"成为假象），也**不得记为 failure**。

**通道判定**：每条展开项先取 `extension`（缓存命中则直接读；缓存缺 `extension` → 对该 nodeId 补一次 `wiki +node-get`，只读，结果入 evidence），再按 §1 表格选通道。**禁止"先 `doc +export` 试一次、失败再换 `drive +download`"**——原生文件必然失败，试错会制造假 failure 并把通道缺陷掩盖成偶发错误。

## 3. 命名与冲突

1. 本地目录/文件名去除 `\\/:*?"<>|` 与首尾空白；清洗后为空时使用 nodeId 前 8 位。
2. folder 同名冲突时后建者追加 `-<nodeId前8>`。
3. 文档规范名 = `<节点名>.<落地后缀>`：`adoc` → `.md`（导出格式）；`md`/`txt` → 保持原 `extension`。不同 nodeId 同名时追加 `-<nodeId前8>`。
4. 同一审核重跑可依据 manifest 保持 `nodeId → localPath` 稳定，但正文必须重新取回并更新 `exportedAt`（`adoc` 重新导出、原生文件重新下载）。

## 4. manifest JSONL

首行 header，其后按清单展开顺序记录 entry、skipped 或 failure：

```jsonc
{ "schema": "crwu.audit-download.manifest.v1", "mode": "M2",
  "space": { "name": "…", "workspaceId": "…", "spaceType": "…" },
  "case_dir": "<案例目录绝对路径>", "started_at": "ISO8601" }

{ "kind": "entry", "requestPath": "06-规则库/某文件",
  "requestKind": "file", "nodeId": "…", "name": "…",
  "extension": "adoc", "channel": "export",
  "folderPath": "knowledge/06-规则库",
  "localPath": "knowledge/06-规则库/某文件.md",
  "exportedAt": "ISO8601",
  "evidence": { "export": { "localPath": "…", "sizeBytes": 1234 } } }

{ "kind": "entry", "requestPath": "03-评估方法/01-市场法",
  "requestKind": "directory", "nodeId": "…", "name": "01-定义与适用前提",
  "extension": "md", "channel": "download",
  "folderPath": "knowledge/03-评估方法/01-市场法",
  "localPath": "knowledge/03-评估方法/01-市场法/01-定义与适用前提.md",
  "exportedAt": "ISO8601",
  "evidence": { "download": { "savedPath": "…", "sizeBytes": 3631 },
                "extensionSource": "catalog|node-get" } }

{ "kind": "skipped", "requestPath": "相关工具/windows/crwu",
  "requestKind": "file", "nodeId": "…", "name": "crwu",
  "extension": "exe", "reason": "extension 非可读正文类型（adoc/md/txt）" }

{ "kind": "failure", "requestPath": "06-规则库/不存在",
  "requestKind": "file", "nodeId": null, "error": "清单项在库内不存在" }
```

- 目录条目展开出的 entry 保留原始 `requestPath`，并使用 `requestKind:"directory"`。
- `localPath` 相对案例目录；绝对路径只在 header 的 `case_dir` 出现。
- **`extension` 与 `channel` 必填**：`channel ∈ {export, download}`，且必须与 `extension` 分流口径一致（`adoc`→`export`；`md`/`txt`→`download`）。`extension` 为 `null`（补查后仍不可判定）→ 记 `skipped`，不得进 entry。
- `extension` 来自补查（缓存缺字段）时，`evidence.extensionSource` 记 `node-get`；来自目录缓存时记 `catalog`——这是"通道判定有据"的留痕。
- **`requestPath` 必须逐字等于库内节点名**（`by_path` 键 = 原样精确名，不折叠大小写/全半角）：
  目录项以 `/` 结尾；**单文件项不要加 `.md` 后缀**——`.md` 只是导出后的本地文件名
  （§3.3「文档规范名 = `<节点名>.<落地后缀>`」），写进 `requestPath` 会与 `by_path` 键不匹配而记 failure。
  旧库（节点名自带 `.md`）留下的带后缀写法属历史残留，迁移到新库后必须去掉后缀。
- 取数回执 `sizeBytes>0` 才算成功；证据按真实返回记录（`doc +export` 用 `localPath`/`sizeBytes`，`drive +download` 用 `savedPath`/`sizeBytes`）。

## 5. 收敛与摘要

- 原始清单项都必须得到"成功展开"或 failure；目录条目的展开数量单独记录。
- 展开后的唯一 nodeId 集合必须等于 **entry + skipped + failure** 的节点集合。
- manifest 不得出现清单命中项及其目录展开项之外的正文 entry。
- **`skipped` 是正常结论、不是失败**：摘要与 `failures[]` 分开统计，禁止把类型不支持并入 failure（会把真实故障淹掉）。
- 摘要报告成功、跳过、失败数量，逐项列出 failure，并明确"清单外零下载；本工作集只用于本次审核，跨审核重新下载"。

## 6. 边界

- 知识正文唯一来源是钉钉知识库。
- M2 产物不得复制到任何目录缓存或作为后续审核的正文来源。
- 远端节点在审核过程中被删除或改变时，以本次实际导出结果和 `exportedAt` 为准；不使用历史正文补齐。
