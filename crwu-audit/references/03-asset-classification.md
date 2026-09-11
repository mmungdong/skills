# 资产类型分类

| 版本 | v1.0 | 状态 | 2026-09-09 定稿 | 维护 | `asset_types[]` canonical 词表 |
| --- | --- | --- | --- | --- | --- |

按 `F0000119`、`F0000066`、`F0000049` 及真实读取的对象/范围原文独立检查下列每个标签。每次命中后继续扫描，保留所有命中，不得用“首次命中即停止”或排他 `else-if` 链。

| canonical 资产类型 | 主要信号 | 目标技能 |
| --- | --- | --- |
| 房地产 | `对象大类=房建类`；对象/范围原文命中房地产、房屋、建筑物、构筑物、场地 | `crwu-audit-asset-realestate` |
| 设备 | `对象大类=设备类`；机器、设备、车辆、生产线 | `crwu-audit-asset-equipment` |
| 无形资产 | 无形资产范围；专利、商标、著作权、专有技术、特许经营权 | `crwu-audit-asset-intangible` |
| 存货 | `对象大类=存货类`；存货范围原文 | `crwu-audit-asset-inventory` |
| 债权 | `对象大类=债权类`；债权范围原文 | `crwu-audit-asset-debt` |
| 矿业权 | 采矿权、探矿权，或报告形态为矿业权评估 | `crwu-audit-asset-mining-right` |
| 数据资产 | 数据资产、数据使用权、数据经营权 | `crwu-audit-asset-data` |
| 森林资源 | 森林资源、林木、林地组合 | `crwu-audit-asset-forest` |

`房建类` 的对外展示名可标准化为“房地产”，但定义必须写明“含房屋建筑物、构筑物、场地及附着物”，且标签的 `source/evidence` 必须保留原始字段值 `房建类`。不得因展示名缩写而排除构筑物、场地或附着物。

每个标签都按 00 的标准结构记录 `type/source/evidence/confidence/review_required`。企业价值范围下的底层资产另按 02 记录 `materiality`。没有相应技能不得删除已命中标签；按 07/10 记录能力缺口。
