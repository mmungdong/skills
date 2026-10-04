# Wait What

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.2.3
- **路径**: skills/productivity/wait-what

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill；此处以 Codex 为例，DSH 可改为 ~/.dsh/skills/wait-what
ln -s "$(pwd)/vendor/mattpocock-skills/skills/productivity/wait-what" ~/.codex/skills/wait-what
```

## 说明

Stop. That last message did not land: re-pitch it.

当上一条信息没有让用户理解时，先停下来识别沟通断点，再换一种更清楚、更贴合用户背景的方式重新说明。

## 选型定位

适用于用户明确表示没听懂、解释没有说清楚或需要换一种说法的场景。它关注沟通修复，不替代技术诊断或任务执行流程。
