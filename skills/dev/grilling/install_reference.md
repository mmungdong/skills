# Grilling

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/productivity/grilling

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/productivity/grilling ~/.claude/skills/grilling
```

## 说明

Grill the user relentlessly about a plan or design. Use to stress-test a plan before building, or on any 'grill' trigger phrases.

触发词驱动版澄清：用户说出 "grill" 等触发短语时自动介入，对计划或设计逐层施压测试。

## 选型定位

productivity 分类下的触发词版澄清。与 `grill-me`（纯对话）和 `grill-with-docs`（带文档沉淀）同属 grill 系列，按是否需要沉淀、是否依赖触发词选用。
