# Diagnosing Bugs

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/engineering/diagnosing-bugs

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/engineering/diagnosing-bugs ~/.claude/skills/diagnosing-bugs
```

## 说明

Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow.

适用于疑难 bug 和性能回归：用结构化诊断循环代替凭直觉改代码，先定位根因再动手，避免反复试错。

## 选型定位

调试期根因诊断工具。与 superpowers 的 `systematic-debugging` 思路相通但更聚焦诊断循环；定位根因后可交给 `tdd` 修复。
