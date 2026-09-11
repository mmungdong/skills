# 资产类型分类

| 版本 | v1.0 | 状态 | 2026-09-09 定稿 | 维护 | `asset_types[]` canonical 词表 |
| --- | --- | --- | --- | --- | --- |

按 `F0000119`、`F0000066`、`F0000049` 及真实读取的对象/范围原文独立检查下列每个标签。每次命中后继续扫描，保留所有命中，不得用“首次命中即停止”或排他 `else-if` 链。

| canonical 资产类型 | 主要信号 | 目标技能 |
| --- | --- | --- |
| 房地产 | `对象大类=房建类`；对象/范围原文命中房地产、房屋、建筑物、构筑物、场地 | `crwu-audit-asset-realestate` |
| 机器设备 | `对象大类=设备类`；机器、设备、生产线（车辆、船舶另归交通运输设备） | `crwu-audit-asset-equipment` |
| 企业价值 | 股东全部/部分权益、企业整体价值、企业资产负债范围 | `crwu-audit-asset-enterprise-value` |
| 无形资产 | 无形资产范围；专利、商标、著作权、专有技术、特许经营权、数据资产、商誉 | `crwu-audit-asset-intangible` |
| 矿业权 | 采矿权、探矿权，或报告形态为矿业权评估 | `crwu-audit-asset-mining-right` |
| 存货 | `对象大类=存货类`；存货范围原文 | `crwu-audit-asset-inventory` |
| 债权 | `对象大类=债权类`；债权范围原文 | `crwu-audit-asset-debt` |
| 资产组合 | `F0000066`、对象说明或明细显示多项资产/资产组合 | `crwu-audit-asset-portfolio` |
| 交通运输设备 | 车辆、船舶、飞机等交通运输工具 | `crwu-audit-asset-transport-equipment` |
| 资产组-含商誉 | 资产组、含商誉的资产组、商誉减值测试 | `crwu-audit-asset-asset-group-goodwill` |
| 废旧物资 | 废旧物资、报废物资、残余价值 | `crwu-audit-asset-scrap-materials` |
| 其他 | 非标准资产对象、上述类型未覆盖的其他资产 | `crwu-audit-asset-other` |

`数据资产` 不再是一级资产标签：库内已并入 `无形资产` 的细分对象 `02-细分对象/05-数据资产/`，由 `crwu-audit-asset-intangible` 叶子内选用。`森林资源` 一级目录已从库内移除，不再登记。

`房建类` 的对外展示名可标准化为“房地产”，但定义必须写明“含房屋建筑物、构筑物、场地及附着物”，且标签的 `source/evidence` 必须保留原始字段值 `房建类`。不得因展示名缩写而排除构筑物、场地或附着物。

每个标签都按 00 的标准结构记录 `type/source/evidence/confidence/review_required`。企业价值范围下的底层资产另按 02 记录 `materiality`。没有相应技能不得删除已命中标签；按 07/10 记录能力缺口。
