---
name: h3yun-query
description: >-
  当用户想【查/看/浏览/找/搜】氚云（H3Yun）的【系统/应用/表单/记录/数据/附件】，
  或说"我们有哪些系统""打开某系统看看下面有什么""这个表单里有什么记录""找标题含 X
  的记录""下一页/第 N 条"时，自动使用本技能。流程：列系统→选系统→看表单→查记录
  （每页 20 条、支持标题关键词）→可看记录详情/附件。只读。若提示无会话/会话过期，
  先改用 h3yun-login；若是登录/绑定类请求不要使用本技能。
---

# H3Yun 数据查询（h3yun-query）

## 自动触发规则

- **触发**：用户表达"查数据/看应用/打开系统/列表单/查记录/找XX记录/翻页"等查询意图，
  或引用了"氚云/项目/客户/表单名/单号"等业务对象名想要查看其下内容。
- **不触发**：登录/绑定/会话过期类请求（走 `h3yun-login`）；增删改/审批类操作
  （当前不支持，如实说明）。
- **命中后的第一步**：先执行 `crwu h3yun session status` 自检会话（会随附自动
  续期）；无会话/过期则引导用户执行 `crwu h3yun session login` 后再回来查询。


通过 `crwu` CLI，以**当前绑定员工**的权限，按"系统 → 表单 → 记录"逐层帮用户
查询氚云数据。全程只读；命令全部走 `crwu h3yun ...`（网页会话通道）。

> 命令与字段细节以 [`docs/cli-manual.md`](../../docs/cli-manual.md) 为准；
> 本文只描述查询会话的交互流程与纪律。

## 什么时候用

- "现在有哪些系统 / 应用？"
- "打开 XX 系统，看看下面有哪些表单（子集）"
- "在 XX 表单里看看有哪些记录 / 最近 20 条"
- "帮我找标题/名称含 xxx 的记录"
- "这条记录再往下一页 / 我要查第 N 条"

## 前置检查

1. 先确认能读取会话：
   ```bash
   crwu h3yun session status
   ```
   - 成功：输出里出现 `engineCode` 与 `expiresIn`，继续。
   - 失败/提示 no session：**不要猜测或索取 token**，请用户执行
     `crwu h3yun session bind --token '<JWT>'`（浏览器 DevTools 复制）后再来。
2. 命令前缀：直接可用 `crwu`；在仓库内也可用 `./bin/crwu`。

## 主流程（一次只问一个问题）

### 第 1 步：列系统（应用），请用户选择

```bash
crwu h3yun apps list
```

- 从输出 `data`（JSON 数组）中取每个应用的 `displayName` 与 `code`（appCode）。
- 按编号列出（例：`1. 瑞联项目管理系统 [Aeed989f…]`），**一次只问**"选哪个系统"。
- 系统很多时先问关键词，再 `crwu h3yun apps list --keyword <词>` 过滤后列出。

### 第 2 步：选中的系统下钻，看父集/子集（表单），再请用户选择

```bash
crwu h3yun apps children --app <appCode>
```

- 输出为功能节点数组，节点类型 `nodeType`：
  - `230` = 分组/父集 → 可继续下钻：`crwu h3yun apps children --app <该节点 code>`
  - `200` / `210` = 普通表单 / 流程表单（子集，**可查记录**），其 `code` 即
    查询用的 `schemaCode`
- 呈现时给节点标注类型（📁 分组 / 📄 表单 / 🔁 流程表单），编号列出后请用户选择；
  用户选中的若是分组，继续下钻；若是表单，进入第 3 步。
- 用户直接给表单名时，可用 `crwu h3yun forms search --keyword <名称>` 先定位。

### 第 3 步：在表单里查记录（默认每页 20 条，可翻页）

```bash
# 用户没给标题 → 首页 20 条
crwu h3yun records list --schema <schemaCode> --size 20

# 用户给出标题/关键词 → 直接按关键词查
crwu h3yun records list --schema <schemaCode> --size 20 --keyword <标题关键词>
```

- 行数据在 `data`（数组或 `data.returnData`）里；把每条整理成**一行简要**：
  `名称(Name/标题) · 单号(SeqNo 如有) · 更新时间(ModifiedTime) · ID 尾段`。
- 翻页：`--page <n>`（从 1 开始），提示用户"下一页 20 条？"再执行
  `crwu h3yun records list --schema <code> --page 2 --size 20`。
- 无结果：先如实告知，再建议换关键词或换表单/系统，不要猜 ID。

### 第 4 步：查看用户选中记录的具体内容（简要输出）

```bash
crwu h3yun records get --schema <schemaCode> --id <ObjectId>
```

- 输出对象即该记录字段：`Name`、`SeqNo`、业务字段 `F0000xxx`（人员类字段同时有
  `*_Name` 可读名）、`Status`、时间字段等。
- 用**可读的字段对**展示（尽量挑非空、非 `*_Original` 的字段）；值较多时分段展示。
- 若用户想看记录里的附件：`crwu h3yun files list --schema <code> --id <ObjectId>`，
  下载需用户确认后执行 `crwu h3yun file download --schema <code> --id <ObjectId> --out <目录>`。

## 呈现与提问纪律

- 每次列表最多展示 20 条，超出提示翻页；编号从 1 开始，选项与结果严格对应。
- **一次只问一个问题**：选完系统再问表单，选完表单再问记录/翻页。
- 展示给用户的是可读文本/编号，**不要**把整段 JSON 原文直接倒给用户（保留 ObjectId
  尾段作标识即可）。
- 任何 `appCode`/`schemaCode`/`ObjectId` 都必须来自命令输出，**禁止编造或猜测**。

## 安全与边界

- 本 skill **只读**：不新增/修改/删除记录，不提交审批。
- 不在任何输出/日志里暴露 token；员工会话绑定由用户自己执行。
- 遇到与数据面相关的 `h3yun.read.upstream_error`：说明 Agent 网关数据面未开通，
  与本 skill 的网页会话通道无关，照常可用；如实说明即可。
- 遇到 `UnLogin`/`no session` 类错误：提示重新 bind，不重试硬闯。

## 示例会话

```
用户：看看我们有什么系统
助手：crwu h3yun apps list
      1. 瑞联项目管理系统
      2. 瑞联投标报价系统
      3. 签到签退
      请问要看哪个？
用户：1
助手：crwu h3yun apps children --app Aeed989ff20c34c9aaecc054fb64e51c1
      1. [📁] 客户
      2. [🔁] 客户信息
      3. [🔁] 客户修改
      …（共 N 项）要看哪个？
用户：客户信息
助手：crwu h3yun records list --schema Syxwvsuwmyagdm66hdtho11ux4 --size 20
      1. 北京庆丰科贸有限公司 · KH7679 · 2026-09-03 · id…2780edc
      2. …
用户：帮我找标题含"测试"的记录
助手：crwu h3yun records list --schema <code> --keyword 测试 --size 20
      …
```

## 更多

- 完整命令与输出契约见 `docs/cli-manual.md`；命令目录实时源为 `crwu scheme`。
