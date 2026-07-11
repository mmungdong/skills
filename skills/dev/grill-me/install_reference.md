# Grill Me

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/productivity/grill-me

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/productivity/grill-me ~/.claude/skills/grill-me
```

## 说明

A relentless interview to sharpen a plan or design.

轻量版澄清工具：不带文档沉淀，纯对话式追问。适合已有一定想法、只想快速压测思路漏洞的场景。

## 选型定位

productivity 分类下的纯对话澄清。与 `grill-with-docs`（带 ADR/glossary 沉淀）和 `grilling`（触发词驱动）互补。
