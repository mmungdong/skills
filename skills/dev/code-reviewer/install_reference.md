# Code Reviewer

- **来源**: https://www.npmjs.com/package/claude-code-templates
- **类型**: npm
- **版本**: 1.29.2

## 安装

**方式一：官方 npm 安装器**

```bash
npx claude-code-templates@latest --skill development/code-reviewer
```

**方式二：vendor 回退（npm 安装器遇 GitHub API 限流时使用）**

`npx` 安装器依赖 GitHub API 匿名调用，易触发 403 限流。回退方案：克隆上游源仓库到本仓库 `vendor/`（已被 `.gitignore` 排除）后软链接，绕过 API：

```bash
# 克隆源仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/davila7/claude-code-templates.git vendor/claude-code-templates

# 软链接 skill 到 Claude Code
ln -s vendor/claude-code-templates/cli-tool/components/skills/development/code-reviewer ~/.claude/skills/code-reviewer
```

## 说明

综合代码审查 skill，支持 TypeScript、JavaScript、Python、Swift、Kotlin、Go。提供自动化代码分析、最佳实践检查、安全扫描和审查清单生成。适用于审查 Pull Request、提供代码反馈、识别问题或确保代码质量达标。
