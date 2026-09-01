# Contributing

Codex Team 仍处于 `incubating`。贡献应优先提交可复现失败、边界测试和小范围协议修正，而不是未经实测的大型抽象。

## 开始前

1. 阅读 `AGENTS.md`、`docs/13-decisions.md` 与 `docs/16-project-status.md`。
2. 区分 confirmed fact、experiment observation、decision、inference 与 unknown。
3. 核对变更是否会改变核心协议、默认范式或生命周期；若会，必须同步决策日志与状态页。
4. 不提交 API Key、Authorization header、真实业务隐私、Codex session 文件或本机 credential。

## 修改要求

- 只面向 Codex，不增加平台无关 adapter。
- 公共 schema/runtime保持单一事实源，不在多个 skill 复制实现。
- Manifest、receipt、Gate 与 evidence必须fail closed且不可静默覆盖。
- 新行为需要正向、负向和篡改/失败测试。
- 不把 fixture、package self-check 或单次 live run描述为长期稳定能力。

## 本地验证

运行 README 中的九组测试。修改 skill 后还应执行：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills\team-plan
```

将路径替换为所有受影响的 skill。Plugin 修改还必须构建到新的、此前不存在的临时目录并运行 bundle self-check。

## Pull Request

PR 应包含：

- 问题与可复现证据；
- 变更边界和未改变内容；
- exact test commands/results；
- breaking schema/lifecycle changes；
- 未验证能力与后续 forward-test建议。

本仓库当前没有开源许可证；提交贡献前请确认你有权提交相关内容。合并贡献不自动改变仓库许可证状态。
