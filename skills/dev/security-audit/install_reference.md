# Security Audit

- **来源**: https://github.com/cloudflare/security-audit-skill
- **类型**: git
- **版本**: c1c8a8c (main, 2026-09-14)
- **路径**: skills/security-audit

## 安装

仓库只托管这一个 skill，但仍按本仓库约定克隆到 `vendor/` 后软链接（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆源仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/cloudflare/security-audit-skill.git vendor/cloudflare-security-audit-skill

# 软链接 skill 到 Claude Code
ln -s "$(pwd)/vendor/cloudflare-security-audit-skill/skills/security-audit" ~/.claude/skills/security-audit
```

## 说明

面向编码 agent 的多阶段安全审计 skill：先找违反真实信任边界的漏洞，再给出源码证据、可安全复现的步骤、优先级与最小有效修复。除入口 `SKILL.md` 外，按领域拆成 12 份参考文档（Web 协议与认证、客户端、云与部署、数据隔离与生命周期、供应链与发布、AI/LLM、内存安全与二进制、协议与消息、资源耗尽、侦察、狩猎、验证与报告），并用 `report-schema.json` 约束机器可读的发现格式。

两种模式：**guidance**（默认，只答安全问题和做局部审查，不产出文件）与 **full audit**（仅在被明确要求审计/渗透测试时启用，走完六阶段流程并写出报告与覆盖台账）。

## 依赖

自带的两个校验器是 Node 脚本（`validate-findings.cjs`、`validate-coverage-ledger.cjs`），需要 Node.js 运行时；已在本机 node v24.19.0 跑通其 65 个内置测试。

## 选型定位

与 `code-reviewer` 的分工：后者面向日常 PR 的功能/质量审查并顺带安全扫描；本 skill 是专门的安全视角，覆盖威胁建模、攻击面枚举与多阶段验证，适合发版前审计、渗透测试准备或专项安全研究。
