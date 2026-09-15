# references/01 · 取数路径发现与调用规程（crwu-audit-external-data）

> 本文件只规定**怎么找到并调用**同花顺 iFinD 的取数入口，以及找不到时怎么办。
> 本技能不启用万得。要核哪些数据项、每项的口径要求与结论档位由知识库
> `06-规则库/M-外部数据核验/01-模块-外部数据核验`（表 A / 表 B / 表 C）规定，本文件不复制；
> 库内表 D 为取数失败与降级口径（单源），双源复核不适用（见 §6）。

## 1 唯一数据源 = 同花顺 iFinD，但入口随宿主而异

同花顺 iFinD 在不同宿主以不同形态提供，**不要用一个宿主的事实推断另一个宿主**：

| 宿主 | 取数路径 | 形态与调用 | 凭据归属 |
| --- | --- | --- | --- |
| WorkBuddy | 宿主内置连接器 | MCP 服务，连接器 id `ifind-mcp`（服务端授权）；会话可能直接暴露其 MCP 工具，否则读宿主连接器声明 | 宿主托管 |
| DeepSeek Harness | `ifind-finance-data` 技能 | 技能自带 `call.py` / `call-node.js`，直连同花顺 MCP HTTP 服务；按该技能 `SKILL.md` 调用 | 技能自身的 `mcp_config.json` |

- 两条路径取的是**同一上游 iFinD 服务**，取回值可视为同一数据源；进入 `sources[]` 时统一写
  `同花顺 iFinD`，本次实际走哪条路径写进 `note`。
- `ifind-finance-data` 技能由第三方（同花顺）提供，**本仓不提供、不随本技能安装**；运行时按该技能
  自身的 `SKILL.md` 与 `references/` 调用，本技能不复制其工具清单。
- 禁止把万得列为数据源，也禁止声称已做双源复核（本环境无万得）。

## 2 发现顺序（逐级降级，不得跳级）

| 级 | 动作 | 判据 |
| --- | --- | --- |
| L1 | 使用**当前会话已暴露的取数入口** | 会话已暴露同花顺 iFinD 的 MCP 工具（多为 WorkBuddy），或会话技能清单含 `ifind-finance-data`（DeepSeek Harness） |
| L2 | 读**宿主 / 技能声明**（L1 未暴露时） | 见 §3（WorkBuddy 连接器声明）与 §4（Harness 技能目录）；命令：`python3 scripts/connector_probe.py --format json` |
| L3 | 入口存在但**未启用 / 未认证** | 按 §5 降级并在交付件声明 |
| L4 | 完全不存在 | 按 §5 降级并在交付件声明 |

L1 成功即用 L1；L1 未暴露**不等于**数据源不可用——必须继续走 L2，不得直接判"无数据源"。
两条路径任一可用即视为可取数；优先用当前会话已直接暴露的那条（少一次发现成本）。

## 3 WorkBuddy：宿主连接器声明位置

默认根 = 环境变量 `CRWU_CONNECTOR_ROOT`；未设置时 = `~/.workbuddy`（WorkBuddy 连接器宿主目录）。
**本仓不提供这些连接器，也不随本技能安装**——它们是宿主侧外部工具。

| 位置（相对根） | 内容 |
| --- | --- |
| `mcp.json` | 宿主 MCP 服务清单（`mcpServers`：连接器 id → 端点 / 启用标记） |
| `connectors/*/mcp.json` | 按账号态分目录的连接器声明 |
| `connectors/*/connector-states.json`、`connector-states.v3.json` | 启用状态（`enabled` 列表、`userDisabled` 映射、`everConnected`）与凭据引用（`headerOverrides` 的**键名**） |
| `connectors-marketplace/.codebuddy-connector/connectors.json` | 连接器目录（id / 中英文名 / 是否需要授权），**不作为"已声明"依据** |

已知连接器标识：同花顺 iFinD = `ifind-mcp`（服务端授权，宿主托管，无需本技能处理凭据）。

## 4 DeepSeek Harness：`ifind-finance-data` 技能目录

DeepSeek Harness 没有 WorkBuddy 连接器目录。同花顺 iFinD 以 `ifind-finance-data` 技能提供，
本技能按**已安装 skills 根**查找该技能目录（存在 `SKILL.md` + `call.py` / `call-node.js` + `mcp_config.json`）：

- 查找顺序：环境变量 `CRWU_SKILLS_ROOT`（如设置）→ **本技能所安装到的 skills 根的同级目录**
  → 常见位置（`~/.agents/skills`、`~/.dsh/skills`、`~/.codebuddy/skills`、`~/.claude/skills`）。
- 调用方式：按该技能 `SKILL.md` 说明取数。注意 `call.py` / `call-node.js` 是**模块而非命令行入口**
  （直接执行只会打印提示）：需在技能目录内写一个**临时请求脚本**，`import call`（或
  `require("$SKILLS_ROOT/ifind-finance-data/call-node.js")`）后调用
  `call(server_type, tool_name, params)` 取数、`list_tools(server_type)` 查当前权益下的工具清单，
  用完即删除临时脚本（遵循该技能自身「核心函数」「注意事项」的约定）；
  `$SKILLS_ROOT` = 本技能所安装到的 skills 根。该技能的参考文档加载、工具名与参数一律以它自己的
  `references/` 与 `SKILL.md` 为准，本技能不复制。
- 凭据：存放在该技能自身的 `mcp_config.json`；本技能**不读取、不输出、不落盘**其内容，只判断文件是否存在。
  密钥无效/缺权益时由该技能报错，按 §5 降级。
- 免费/个人/企业版权益对应的并发上限由该技能规定；取数时控制并发，避免因限流误判为"无覆盖"。

## 5 兜底：入口不可用时怎么办

1. **不得静默跳过**，也不得事后补写结论。
2. 按库内降级口径降级：命中关键参数 / 高风险的条目降为"单源 + 请说明"；其余记未检查项与能力缺口。
   本环境无万得副源，**所有条目一律单源**，不得声称已复核。
3. **在交付 HTML 的《外部数据核验》区显式声明**（字段 `externalDataVerification.sources[]`，
   数据源统一写 `同花顺 iFinD`）：

   | 情形 | `configured` | `authenticated` | 必须在 `note` 写明 |
   | --- | --- | --- | --- |
   | 两条路径都不存在 | `false` | `false` | 未配置同花顺 iFinD 取数入口；相关条目未经外部数据核验 |
   | 入口存在但未启用 | `false` | `false` | 取数入口未启用；相关条目未经外部数据核验 |
   | 入口启用但未完成授权 | `true` | `false` | 取数入口未认证；相关条目未经外部数据核验 |
   | 可用 | `true` | `true` | 本次取数路径（WorkBuddy 连接器 / Harness 技能）与取数时点、口径 |

4. 声明措辞统一为："本次未配置 / 未认证 同花顺 iFinD，相关条目未经外部数据核验。"
5. 降级不影响其他检查项与轴：外部数据核验失败不得短路方法判断、披露检查或表格勾稽。

## 6 调用与留痕契约

每次取数必须记录并回执：

```yaml
data_point:
  metric: 【数据项名称】            # 与知识库表 B 的数据项一致
  metric_key: EXT_【…】            # 可选，与库内稳定键一致
  base_date: 【报告基准日】         # 全部取数的锚点
  as_of_date: 【本次取数时点】       # 与基准日不同的必须说明
  source: 同花顺 iFinD
  access_path: 宿主连接器 / ifind-finance-data 技能
  query_params:                    # 口径参数，按库内表 B 要求的必填项逐项填
    term / window / frequency / benchmark / adjustment / unit / …
  value: 【取回值】
  source_note: 【可选】取数路径（宿主连接器 / ifind-finance-data 技能）或口径变更说明
  snapshot_digest: 【快照摘要】      # 对取回内容做规范化摘要，供事后核验
```

- **基准日纪律**：`query_params` 的区间与窗口一律由 `base_date` 推导；禁止"截止最新 / 最近 N 周"这类
  以取数时点为准的滚动窗口。
- **单源纪律**：本环境不启用万得，数据源一律为同花顺 iFinD，**不得声称双源复核**；
  取数路径与口径变更在 `source_note` 如实登记。
- **凭据纪律**：只读声明的**键名与启用状态**；不读取、不输出、不落盘任何令牌、Authorization 头、
  含 token 的 URL 或 `ifind-finance-data` 技能的 `mcp_config.json` 内容。探测脚本已按此实现
  （URL 只输出主机名）。
- **快照纪律**：外部数据快照按本次审核工作目录落盘并登记摘要，供交付层引用；不写入知识库缓存。
