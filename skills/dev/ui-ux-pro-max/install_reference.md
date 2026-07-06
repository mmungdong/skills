# UI/UX Pro Max

- **来源**: https://www.npmjs.com/package/claude-code-templates
- **类型**: npm
- **版本**: 1.29.2

## 安装

**方式一：官方 npm 安装器**

```bash
npx claude-code-templates@latest --skill creative-design/ui-ux-pro-max
```

**方式二：vendor 回退（npm 安装器遇 GitHub API 限流时使用）**

`npx` 安装器依赖 GitHub API 匿名调用，易触发 403 限流。回退方案：克隆上游源仓库到本仓库 `vendor/`（已被 `.gitignore` 排除）后软链接，绕过 API：

```bash
# 克隆源仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/davila7/claude-code-templates.git vendor/claude-code-templates

# 软链接 skill 到 Claude Code
ln -s vendor/claude-code-templates/cli-tool/components/skills/creative-design/ui-ux-pro-max ~/.claude/skills/ui-ux-pro-max
```

## 说明

UI/UX 设计智能 skill。内置 50 种风格、21 套配色、50 组字体搭配、20 种图表、9 种技术栈（React、Next.js、Vue、Svelte、SwiftUI、React Native、Flutter、Tailwind、shadcn/ui）。适用于规划、构建、设计、实现、审查、修复、改进或优化各类 UI/UX 代码，覆盖网站、落地页、仪表盘、管理后台、电商、SaaS、作品集、博客和移动端应用。
