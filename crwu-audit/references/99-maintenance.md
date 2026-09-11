# 多轴路由维护说明

| 版本 | v1.0 | 状态 | 2026-09-09 守门文档 | 适用 | `crwu-audit` router、references 与叶子能力维护 |
| --- | --- | --- | --- | --- | --- |

## owner 映射

| 改动 | 唯一 owner |
| --- | --- |
| 输入字段、route profile schema、溯源与隐藏数据隔离 | `00-input-and-route-profile.md` |
| `SeqNo` / `ObjectId` 定位 | `01-report-id-resolution.md` |
| `scope_types[]` 分类与企业价值 materiality | `02-scope-classification.md` |
| `asset_types[]` 分类 | `03-asset-classification.md` |
| `business_types[]` 分类 | `04-business-classification.md` |
| `methods[]`、方法角色与结论方法 | `05-method-classification.md` |
| `overlays[]` 与 ROUTE001–004 | `06-overlay-classification.md` |
| `axis+label` 技能名、状态与加载行为 | `07-skill-registry.md` |
| 稳定并集、pending/冲突执行边界与结果来源 | `08-union-dispatch-rules.md` |
| A/B/C 机构审核风险分类 | `09-review-risk-classification.md` |
| 能力 gap 与待建提案 | `10-capability-gap-proposal.md` |
| 送达与交付层（AuditResult/单文件 HTML、双证据链、两阶段门禁、验收清单） | `11-html-delivery-spec.md` |
| 总体 workflow、加载指针与输出步骤 | `SKILL.md` |

规则正文和检查点不属于本技能族的 owner；只允许按编号和知识库层级路径引用。**例外**：送达与交付层正文（CRWU 审核意见 HTML 送达规范 v1.0）为本技能内正式规范，owner 是 `11-html-delivery-spec.md`，不经知识库下载。

## 维护流程

0. 用户反馈驱动的优化先经 `crwu-audit-optimize` 形成含文件清单和回归项的方案；经用户确认后再修改。用户已经明确批准的范围可直接执行。
1. 先按上表确定唯一 owner，只在该文件改定义；上层文件只保留指针，不复制完整词表或规则。
2. 改动只落源仓的本技能目录（`crwu-audit`）。运行时技能布局、软链与部署由用户的 skills 管理机制负责；维护者不得直接对运行时目录执行写入、复制、链接或删除。
3. 标签变更同步其分类 owner 与 07；分发语义变更同步 08；workflow 指针变更才同步根 `SKILL.md`。
4. 按变更影响同步源仓的设计文档、技能清单、变更纪要（均由源仓维护、不随技能安装）和相应测试。若用户明确把一次迁移限制为 references，则记录其他同步为后续任务，不越界修改。
5. 运行 router contract、DWS source contract、BG8169/300673 等相关叶子回归和 `git diff --check`；验证失败不得宣称完成。字段或统计口径变化时重跑相应基线画像。
6. 只提交源仓中已授权范围；检查提交内容和工作区状态，不夹带凭据、下载材料或其他任务改动。

## DWS live reference 与反编造

- 推理引用遵守 R1–R5：目录可以缓存，正文零缓存；以本次清单驱动，经 `crwu-dws` 实时下载；按 RULE/CHK 编号与库内层级路径寻址。
- 技能文件只写编号和库内层级路径，不写知识库名、本地根路径或 nodeId。出处必须是本次下载文件的行号和 `exportedAt`。
- 下载失败时显式报告路径和原因，对应检查点不引用、不编造；目录缓存不能替代正文。
- 评估目的、方法、结论方法与其 location 必须来自真实读取和定位的报告文件。字段、附件名、行业经验不能补写原文或伪造章节、页码、行号。
- 新增任何 available 能力必须完成 07、设计文档、skills README 等登记，叶子 SKILL 自带“仅经 crwu-audit 编排调用、禁止单独调用”门禁。

## 隐藏数据隔离

下载的 Excel 在任何解析前按 00 制作只含可见 sheet、行、列的重建工作版，并重开验证隐藏区为零。raw 原件只由编排层持有；叶子只接收工作版。公式/引用坐标核查仅可对 raw 可见区做限定只读访问。发现读取隐藏区、叶子整簿读取 raw 或工作版仍含隐藏区时立即阻断并记录违规。

## 自查

- 正式 route profile 字段仍是 `scope_types[]/asset_types[]/business_types[]/methods[]/overlays[]`。
- 分类保持多标签，技能以 available 稳定并集装载；pending 每个 `axis+label` 独立 gap。
- A/B/C 只影响审核风险提示，不改变 business skills。
- 来源字段完整，未读取材料不冒充已抽验；隐藏数据没有进入叶子上下文。
- references 集合、根指针、注册表、设计/README/CHANGELOG 与测试在对应任务中同步。
- 根 `SKILL.md` 只保留 workflow、reference 指针和执行契约，避免复制大表，并维持不超过 300 行的目标（极限 500 行）。
- 变更只存在于 source repo，验证输出可复现，提交范围准确。
