# Codex Team

[![Release](https://img.shields.io/github/v/release/DrPei12/codex-team)](https://github.com/DrPei12/codex-team/releases)
[![CI](https://github.com/DrPei12/codex-team/actions/workflows/ci.yml/badge.svg)](https://github.com/DrPei12/codex-team/actions/workflows/ci.yml)

Codex Team 是一个只面向 Codex 的 manifest-driven 多任务工程系统。它把需求覆盖、任务切分、workspace/文件所有权、worker 预检、证据交接、阶段检查点、集成、独立审查、完成与恢复固化为七个可移动 skills 和一套可验证的本地 artifact 协议。

项目不会因为“可以并行”就创建更多任务。只有共享契约、依赖、owner、输入输出、Gate 与集成点足够清楚时才允许并行。

## 当前版本

最新版本：`0.1.6`。

- 需求覆盖矩阵：`requirement -> owner -> path -> Gate -> reviewer`；
- `change` 与 `verification-only` requirement；
- visible task / internal subagent、用户语言标题与任务生命周期；
- worker preflight 与 hash-bound backbrief；
- manifest-specific heartbeat、turn budget 与 stage checkpoint；
- exact candidate、ordered integration、Gate receipt 与 reviewer exact target；
- non-destructive finish 与 bounded recovery；
- 7 个 `incubating` skills，148 项源码回归和 16 份离线端到端 artifact schema 验证。

成熟度仍为 `incubating`。当前没有后台 scheduler、自动 live fact collector、自动任务中断/重派或长期稳定性保证。

## 七个 skills

- [`team`](skills/team/SKILL.md)：只读路由到下一 canonical phase；
- [`team-plan`](skills/team-plan/SKILL.md)：验证 requirement coverage、DAG、ownership、Gate 和 checkpoint；
- [`team-run`](skills/team-run/SKILL.md)：生成 preregistration、preflight、prompt/dispatch 与 worker backbrief；
- [`team-status`](skills/team-status/SKILL.md)：从 immutable facts 派生 lane/checkpoint 状态；
- [`team-integrate`](skills/team-integrate/SKILL.md)：冻结候选、按 manifest 顺序集成并运行 exact-target Gate；
- [`team-finish`](skills/team-finish/SKILL.md)：审计最终 Git/artifact/task disposition，不自动清理；
- [`team-recover`](skills/team-recover/SKILL.md)：冻结失败候选并准备一个有界 successor。

## 构建 plugin

要求：Python 3.12+、Git、Windows PowerShell（完整回归目前只在 Windows 验证）。

```powershell
$buildRoot = Join-Path $env:TEMP ('codex-team-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $buildRoot | Out-Null
$output = Join-Path $buildRoot 'codex-team'
python -B scripts\build-team-plugin.py --out $output
python -B "$output\skills\team\scripts\bundle-self-check.py" "$output\skills\team"
```

Builder 不覆盖已存在的输出目录。生成包包含 7 个 skills、7 个 runtime 入口、7 份 schema 与 SHA-256 bundle manifest。

## 本地 marketplace 安装

仓库 marketplace 指向 Git-ignored 的 `plugins/codex-team`，因此先构建到该路径，再安装：

```powershell
New-Item -ItemType Directory -Path "$PWD\plugins" -Force | Out-Null
python -B scripts\build-team-plugin.py --out "$PWD\plugins\codex-team"
codex plugin marketplace add . --json
codex plugin add codex-team@codex-team-local --json
```

卸载：

```powershell
codex plugin remove codex-team@codex-team-local --json
codex plugin marketplace remove codex-team-local --json
```

Codex 的 plugin cache、旧任务和 effective runtime 不保证热刷新。升级前应保存 snapshot/rollback，并用新任务重新验证 discovery、explicit load 与 bundle self-check。

## 验证

```powershell
$tests = @(
  'test_team_finish.py',
  'test_team_integrate.py',
  'test_team_plan.py',
  'test_team_plugin.py',
  'test_team_recover.py',
  'test_team_router.py',
  'test_team_run.py',
  'test_team_status.py',
  'test_team_v01.py'
)
foreach ($test in $tests) {
  python -B "tests\$test"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

## 文档

1. [项目章程](docs/00-project-charter.md)
2. [默认运行架构](docs/04-default-operating-model.md)
3. [决策日志](docs/13-decisions.md)
4. [当前状态](docs/16-project-status.md)
5. [Capability contract](docs/18-capability-contract.md)
6. [ClothingRecycler live 实验](experiments/clothingrecycler-pc-v1/README.md)
7. [Changelog](CHANGELOG.md)

## 范围与证据边界

- 只面向 Codex；不提供 Claude Code adapter 或平台无关 runtime。
- Worker 声称完成不等于验收完成；Git revision、artifact hash、Gate 与 reviewer target必须独立绑定。
- `requested_model/reasoning` 不等于 effective 配置；不可观测时必须记录 `unknown`。
- Source fixture、临时 package 和一次受控实验不能证明长期触发、自动恢复或端到端稳定。
- Superpowers 仅作为历史 prior art 研究对象，不是本项目 runtime 依赖。

## 许可证

本仓库当前**没有开源许可证**。GitHub public visibility 只表示源码公开可读，不授予复制、修改、分发或商业使用权。若后续决定采用 MIT、Apache-2.0 或其他许可证，将通过独立决策与新版本发布。

安全问题请阅读 [SECURITY.md](SECURITY.md)，贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
