# Codex Team

[![Release](https://img.shields.io/github/v/release/DrPei12/codex-team)](https://github.com/DrPei12/codex-team/releases)
[![CI](https://github.com/DrPei12/codex-team/actions/workflows/ci.yml/badge.svg)](https://github.com/DrPei12/codex-team/actions/workflows/ci.yml)

Codex Team 是只面向 Codex 的工程协作系统。0.2 Auto 从自然语言目标生成可审阅方案，通过本地控制程序组织独立会话，维护工作笔记与可检索历史，并在约定检查点收口。原有七个 skills 和0.1.x证据/集成协议继续保留。

项目不会因为“可以并行”就创建更多任务。只有共享契约、依赖、owner、输入输出、Gate 与集成点足够清楚时才允许并行。

## 当前版本

本地开发版本：`0.2.0`，仍为 `incubating`，里程碑1–5已完成本地验收。仓库记录的上一公开版本为 `0.1.9`；本轮没有发布新Release或更新全局安装。

0.2新增：真实Codex App Server执行、单/多会话规划、版本化授权、原生沙箱Gate、持久状态与事件、本地中文看板、协作请求、纠偏、暂停/恢复、工作笔记/历史检索、Session接替和中途方向审查。Team核心不依赖第三方Skill或插件。CheckCSV单会话与LabLedger双会话真实工程闭环均已完成，见[里程碑5验收记录](docs/22-milestone5-acceptance.md)。

以下是保留的0.1.x基础：

- 需求覆盖矩阵：`requirement -> owner -> path -> Gate -> reviewer`；
- `change` 与 `verification-only` requirement；
- visible task / internal subagent、用户语言标题与任务生命周期；
- worker preflight 与 hash-bound backbrief；
- manifest-specific heartbeat、turn budget 与 stage checkpoint；
- exact candidate、ordered integration、Gate receipt 与 reviewer exact target；
- non-destructive finish 与 bounded recovery；
- 7 个 `incubating` skills，149 项源码回归和 16 份离线端到端 artifact schema 验证。

长期无人值守可靠性、多任务收益、跨环境兼容和正式安装升级仍须独立验证。运行时必须保留控制程序及其状态目录；界面活跃、测试通过和最终用户接受分别记录。

## Team Auto 本地运行

需要Python 3.12+、Git、已登录的官方Codex。使用与产品仓库分离的状态目录：

```powershell
python -B scripts/team-auto.py --state "D:/TeamState/my-project" serve
```

打开 `http://127.0.0.1:8765`，填写仓库路径与目标，审阅方案/资源/权限后运行。新项目可以指定尚未创建的空目录，实际写入在Run授权之后发生。程序调用现有Codex认证，不要求OpenAI API Key或第三方插件。

命令行也可使用 `propose`、`approve`、`run`、`snapshot`、`notes`、`history`、`pause`、`resume`。`reconcile`核对控制器中断后的原生状态；`supervise`检查暂停目标的方向；`replace-session`依据中断回执、源码和笔记转移责任；`requalify`重新资格化更新后的解释器。完整用法见[Auto工作流](skills/team/references/auto-workflow.md)和 `python -B scripts/team-auto.py --help`。

## 七个 skills

- [`team`](skills/team/SKILL.md)：Auto入口；已有0.1.x manifest继续只读路由到下一 canonical phase；
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

Builder 不覆盖已存在的输出目录。生成包包含 7 个 skills、8 个 runtime 入口、7 份 schema 与 SHA-256 bundle manifest。

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
