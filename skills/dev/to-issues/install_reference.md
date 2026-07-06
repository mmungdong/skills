# To Issues

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/engineering/to-issues

## 安装

mattpocock/skills 是集合仓库，需克隆整个仓库后软链接单个 skill：

```bash
# 克隆集合仓库
git clone https://github.com/mattpocock/skills.git ~/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s ~/mattpocock-skills/skills/engineering/to-issues ~/.claude/skills/to-issues
```

## 说明

Break a plan, spec, or PRD into independently-grabbable issues on the project issue tracker using tracer-bullet vertical slices.

适用于 PRD 完成后：把 PRD 拆成可独立领取、独立验证、独立交付的 issue。一个合理的粒度是：一个 issue 能在一个明确上下文里完成一个可验证的垂直切片。

## 选型定位

探索期任务拆分工具。承接 to-prd 的产出，拆出可被 implement 执行的 issue。
