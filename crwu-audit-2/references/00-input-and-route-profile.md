# 输入与 route_profile

| 版本 | v1.0 | 状态 | 2026-09-09 多维路由定稿 | 维护 | 输入字段与画像 schema 唯一事实源 |
| --- | --- | --- | --- | --- | --- |

## 输入字段

报告审核记录的输入标识与必读字段如下。标识解析只按 [01-report-id-resolution.md](01-report-id-resolution.md) 执行。

| 信号 | 字段 | 用途 |
| --- | --- | --- |
| 报告标识 | `SeqNo`、`ObjectId` | 定位唯一记录 |
| 报告名称 | `F0000049` | 对象与业务弱结构化补充证据 |
| 报告形态 | `F0000056` | `report_form` |
| 业务大类 | `F0000065` | 业务类型主证据 |
| 评估目的 | `F0000064` | 业务类型主证据 |
| 评估范围 | `F0000066` | 范围与底层资产分类 |
| 对象大类 | `F0000119` | 资产类型分类 |
| 价值类型 | `F0000072` | 市场、公允、可收回、清算、残余等口径 |
| 法定性 | `F0000051` | 报告条款强制力 |
| 评估基准日 | `F0000067` | 时效性和冲突核查 |
| 报告文号 | `F0000092` | 披露一致性 |
| 监管归属 | `F0000082` | 国资覆盖层 |
| 金融标志 | `F0000124` | 金融/银行覆盖层 |
| 司法标志 | `F0000126` | 司法覆盖层 |
| 证券标志 | `F0000127` | 证券覆盖层 |
| 附件字段 | `F0000076` 等所有附件键 | 文件清单、下载和材料路径准备；文件名只是提示 |

`F0000020`、`F0000158`、`F0000178` 等风险等级/级次/状态只是背景或对照信号，不参与范围、资产、业务、方法或覆盖层路由。业务大类/评估目的为空时可读 `F0000049` 推断；名称仍含混时记录“画像歧义，需人工确认”，不猜测分发。

`F0000056` 的报告形态先于五个分发轴记录，并决定表述强制力：评估业务可使用评估结论等法定口径；咨询/估值文书使用参照口径，不得表述为“评估结论”或虚构结论有效期；矿业权评估同时继续识别 `asset_types[]=矿业权`。报告形态不能替代任何轴标签。

## route_profile

```jsonc
{
  "route_profile": {
    "identity": {
      "input": "用户提供的标识",
      "input_type": "SeqNo|ObjectId|material-package",
      "seq_no": "真实输入或查询返回值|null",
      "object_id": "用户提供或精确查询所得|null"
    },
    "report_form": "资产评估业务",
    "record_context": {
      "report_name": "F0000049 原值",
      "value_type": "F0000072 原值",
      "legal_status": "F0000051 原值",
      "base_date": "F0000067 原值",
      "document_number": "F0000092 原值",
      "recorded_risk_level": "F0000020 原值，仅作对照"
    },
    "scope_types": [],
    "asset_types": [],
    "business_types": [],
    "methods": [],
    "conclusion_method": null,
    "overlays": [],
    "review_risk_class": {},
    "material_gaps": [],
    "conflicts": [],
    "weak_structured": false,
    "confidence": {"overall": "high|medium|low", "note": ""}
  }
}
```

`scope_types[]`、`asset_types[]`、`business_types[]`、`methods[]` 和 `overlays[]` 中的每个分类标签必须具有：

```jsonc
{
  "type": "清算",
  "source": ["F0000064", "报告目的原文"],
  "evidence": ["企业清算", "为破产清算提供价值参考"],
  "location": ["record.F0000064", "评估报告·摘要·评估目的段(L60-68)"],
  "confidence": "high|medium|low",
  "review_required": false
}
```

`source/evidence/location` 是不可拆分的数组三元组：`source[]` 说明来自记录字段、报告文件或名称推断，`evidence[]` 保留实际字段值或原文，`location[]` 给出字段键或文件·章节/页/行号；文件未读取时用 `evidence=["未抽验（文件未读取）"]`、`location=[]`，不得伪造。企业价值范围下的 `asset_types[]` 另必须包含 `materiality: key|non-key|unknown`，并保留判定理由。字段直读或真实报告原文为高置信度；报告名称推断为中或低置信度；来源冲突、弱信号或 `materiality=unknown` 时 `review_required=true`。

## 文件级读取与溯源

评估目的原文、评估方法、结论方法及其位置只能来自真实读取的文件：

1. 用真实 schema code 和 `ObjectId` 下载附件，并确认文件存在且字节数非零。
2. 先用 `file` 识别格式：旧 `.doc` OLE 可用 `textutil -convert txt`；`.docx` 读 OOXML；`.pdf` 用文本提取工具；`.xlsx/.xls` 用相应表格工具。先探测现有工具，不得凭印象宣称不可读。
3. 在文件中定位原文，为文件级字段回填数组 `source`、`evidence` 与 `location`。没有定位不得用于冲突定论。
4. 文件未下载或不可读时，字段显式标记 `未抽验（文件未读取）`，不填定位。

附件名只能标记为提示或待抽验，不能据此表述“已采用某法”。严禁从氚云字段、附件名、行业经验补写报告原文，或编造章节、页码、行号。

## 方法角色概要

`methods[]` 保留报告披露/采用的全部方法。每项严格使用 00 的通用标签 schema：canonical 方法写入 `type`，`source/evidence/location` 均为数组，并保留 `confidence/review_required`；方法项额外使用 `role=采用-作结论|采用-未作结论|测算-参考`。`conclusion_method` 单独保留结论所用方法并引用相同 canonical `type` 和证据结构。详细判定与多方法检查见 [05-method-classification.md](05-method-classification.md)。

## KB 装配输入

五轴 `route_profile` 是 router 的唯一画像契约。**装配清单不再由本仓工具生成**：命中某个轴标签后，下载清单 = 命中叶子 `references/01-kb-assembly.md` 中该轴的路径键（一级目录根 `request_kind=directory`/`recursive=true`，或明确的单文件路径）＋公共执行契约路径并集。

router 只负责把五轴画像映射成轴标签并选出 available 叶子；不得为兼容而生成旧画像键，也不得自行挑选叶子装配表以外的知识库文件。叶子按自身装配表声明的一级目录根，经 `crwu-dws` 递归实时下载该根下全部支持正文并准备材料；下载失败、空目录或不支持导出的节点记 capability gap，不静默忽略。

## Excel 隐藏数据隔离

对下载的 `.xlsx/.xls` 在任何解析、提取或勾稽前制作工作副本：

- raw 原件保留不动；手动隐藏的 sheet、行、列、折叠分组是脏数据，隐藏内容禁读、禁引用、禁输出。可读结构元数据以识别并剔除隐藏区；隐藏状态无法判定时按隐藏剔除，并记录“隐藏状态未知 · 已剔除”。
- 只能用“重建法”：新建簿并只复制可见 sheet × 可见行 × 可见列的值/公式串。禁止用 openpyxl `delete_rows`/`delete_cols` 逐行列删除，因其会残留维度元数据。
- 保存后重新打开工作版，验证隐藏区数量为 0。失败则按重建法重做；仍残留则挂起，不继续审核。
- 工作版剔除行列后坐标会收缩，而公式串仍保留 raw 坐标。公式/引用/合计范围类勾稽以 raw 坐标为准，只读可见单元格；纯数值勾稽可在工作版执行。
- raw 原件只由编排层持有，叶子/下游只接收工作版路径。唯一例外是公式/引用坐标核查可对 raw 可见区做限定只读访问。叶子整簿读 raw、读 raw 隐藏区或读仍含隐藏区的工作文件时立即阻断并记录违规。

## 材料缺口与降级

缺失材料、未抽验字段、未注册标签或 pending 能力按标签分别写入 `material_gaps[]`。不可用的单个技能不得导致其他 available 技能短路；不得以“无能力”空返，应附非审核结论的能力缺口说明。
