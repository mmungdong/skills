# references/01 · 连接器发现与调用规程（crwu-audit-external-data）

> 本文件只规定**怎么找到并调用**外部数据源连接器，以及找不到时怎么办。
> "哪个数据项用哪个源、何时双源"由知识库 `06-规则库/M-外部数据核验/01-模块-外部数据核验`（表 B / 表 D）规定，本文件不复制。

## 1. 发现顺序（逐级降级，不得跳级）

| 级 | 动作 | 判据 |
| --- | --- | --- |
| L1 | 使用**当前会话已暴露的 MCP 工具** | 工具名或服务名含 `ifind` / `iFinD` / `同花顺`（同花顺 iFinD）、含 `wind` / `万得`（万得） |
| L2 | 读**宿主连接器声明**（工具未暴露时） | 见 §2；命令：`python3 scripts/connector_probe.py --format json` |
| L3 | 连接器存在但**未启用 / 未认证** | 按 §3 降级并在交付件声明 |
| L4 | 完全不存在 | 按 §3 降级并在交付件声明 |

L1 成功即用 L1；L1 未暴露**不等于**数据源不可用——WorkBuddy 的连接器工具可能未在当前会话暴露，
必须继续走 L2 读宿主声明，不得直接判"无数据源"。

## 2. 宿主连接器声明位置

默认根 = 环境变量 `CRWU_CONNECTOR_ROOT`；未设置时 = `~/.workbuddy`（WorkBuddy 连接器宿主目录）。
**本仓不提供这些连接器，也不随技能安装**——它们是宿主侧外部工具。

| 位置（相对根） | 内容 |
| --- | --- |
| `mcp.json` | 宿主 MCP 服务清单（`mcpServers`：连接器 id → 端点 / 启用标记） |
| `connectors/*/mcp.json` | 按账号态分目录的连接器声明 |
| `connectors/*/connector-states.json`、`connector-states.v3.json` | 启用状态（`enabled` 列表、`userDisabled` 映射、`everConnected`）与凭据引用（`headerOverrides` 的**键名**） |
| `connectors-marketplace/.codebuddy-connector/connectors.json` | 连接器目录（id / 中英文名 / 是否需要授权） |

已知连接器标识（截至 2026-09 实测）：

| 数据源 | 连接器 id | 授权形态 |
| --- | --- | --- |
| 同花顺 iFinD | `ifind-mcp` | 服务端授权（宿主托管，无需本技能处理凭据） |
| 万得（Wind Alice） | `wind-finance` | token（需在宿主侧完成配置/授权） |

## 3. 兜底：无连接器或未认证时怎么办

1. **不得静默跳过**，也不得事后补写结论。
2. 按知识库表 D 降级：命中 W2（关键参数）/ W4（高风险）的条目降为"单源 + 请说明"；
   W1 / W3 记未检查项与能力缺口。
3. **在交付 HTML 的《外部数据核验》区显式声明**（字段 `externalDataVerification.sources[]`）：

   | 情形 | `configured` | `authenticated` | 必须在 `note` 写明 |
   | --- | --- | --- | --- |
   | 连接器不存在 | `false` | `false` | 未配置该数据源；相关条目未经双源复核 |
   | 连接器存在但未启用 | `false` | `false` | 连接器未启用；相关条目未经双源复核 |
   | 连接器启用但未完成授权 | `true` | `false` | 连接器未认证；相关条目未经双源复核 |
   | 可用 | `true` | `true` | 取数时点与口径 |

4. 声明措辞统一为："本次未配置 / 未认证 <数据源>，相关条目未经双源复核。"
5. 降级不影响其他检查项与轴：外部数据核验失败不得短路方法判断、披露检查或表格勾稽。

## 4. 调用与留痕契约

每次取数必须记录并回执：

```yaml
data_point:
  metric: 【数据项名称】            # 与知识库表 B 的数据项一致
  metric_key: EXT_【…】            # 可选，与库内稳定键一致
  base_date: 【报告基准日】         # 全部取数的锚点
  as_of_date: 【本次取数时点】       # 与基准日不同的必须说明
  source: 同花顺 / 万得
  query_params:                    # 口径参数，按库内表 B 要求的必填项逐项填
    term / window / frequency / benchmark / adjustment / unit / …
  value: 【取回值】
  snapshot_digest: 【快照摘要】      # 对取回内容做规范化摘要，供事后核验
```

- **基准日纪律**：`query_params` 的区间与窗口一律由 `base_date` 推导；禁止"截止最新 / 最近 N 周"这类
  以取数时点为准的滚动窗口。
- **凭据纪律**：只读声明中的**键名与启用状态**；不读取、不输出、不落盘任何令牌、Authorization 头
  或含 token 的 URL。探测脚本已按此实现（URL 只输出主机名）。
- **快照纪律**：外部数据快照按本次审核工作目录落盘并登记摘要，供交付层引用；不写入知识库缓存。
