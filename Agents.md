# Agent 通用规范

## Git 提交
- commit 时不要添加 `Co-Authored-By` 行
- 使用英文 Angular 规范提交，格式：`<type>(<scope>): <subject>`
  - type: feat | fix | docs | style | refactor | perf | test | chore | ci | build | revert
  - scope 可选，表示影响范围
  - subject 简短描述，不加句号

## 代码风格
- 保持与现有代码一致的风格、命名和缩进
- 注释密度和风格对齐周围代码

## 工作习惯
- 修改前先阅读目标文件，理解上下文
- 不确定时主动询问，不要猜测
- 完成后确认结果，不要含糊其辞
- 每次新增或更新 skill 时，必须同步更新 README.md，README.md 用于展示项目结构和 skill 信息
- Skill 分两类：
  - **自建 skill**：包含 SKILL.md（含 frontmatter）和 skill.json，链接指向 SKILL.md
  - **引用 skill**：只需 install_reference.md，链接指向 install_reference.md
- 引用 skill 如果来自集合仓库（包含多个 skill），install_reference.md 中需列出所有子 skill，包含 description 和"已集成"状态（✅/❌），便于追踪哪些已使用
- README.md 中 skill 展示格式为表格+链接，每个分类一个表格：

```
### <category>

| Skill | Description | Version |
|-------|-------------|---------|
| [skill-name](skills/<category>/skill-name/SKILL.md) | description from SKILL.md frontmatter | x.x.x |
| [ref-skill](skills/<category>/ref-skill/install_reference.md) | description | x.x.x |
```

  - Skill 列：自建 skill 链接 SKILL.md，引用 skill 链接 install_reference.md
  - Description 列：取自 SKILL.md frontmatter 的 `description` 或 install_reference.md 中的说明
  - Version 列：取自 SKILL.md frontmatter 的 `metadata.version` 或 install_reference.md 中记录的版本
