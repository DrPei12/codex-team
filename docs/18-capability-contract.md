# 18. Codex Capability Contract

> 路线说明：本 contract 继续约束事实表述和按需安全检查，但自 D-020 起不再要求先补齐全部矩阵才进入真实工程纵向切片。Workflow 依赖某条 `unknown` 时才运行对应最小 probe；其余组合保持 `unknown`。

## 目的

Capability contract 用来回答一个窄问题：**在指定 Codex、操作系统、工具 schema 和 Git 快照下，哪些多任务原语只是被声明存在，哪些已经由可重复行为实验观察到，哪些仍未知或与声明矛盾？**

它不是功能宣传页，也不是对未来版本的保证。它先于 skills：如果底层 create、fork、message、wait、handoff、archive、worktree 或 subagent 语义没有被正确识别，skill 只会把错误假设自动化。

## 证据状态

每条 capability 只能处于以下状态之一：

| 状态 | 含义 |
|---|---|
| `declared_unverified` | 当前官方文档、CLI flag 或工具 schema 声明入口/语义存在，但尚未完成当前环境的 before/after 行为核验 |
| `observed` | 当前环境按预注册步骤运行，保存了输入、输出、Git/任务 before/after 与 cleanup evidence |
| `contradicted` | 行为实验与声明或已有观测冲突，且冲突条件已记录 |
| `unsupported` | 当前固定环境明确没有该能力；必须有直接证据，不能由“没找到”推断 |
| `unknown` | 证据不足，或存在尚未消除的环境/权限/版本混杂 |

禁止使用无条件的 `verified`。一次 `observed` 必须绑定环境和条件；历史实验不能直接把当前 capability 升级为 `observed`。

## 数据构成

- JSON Schema：[`schemas/capability-contract.schema.json`](../schemas/capability-contract.schema.json)
- 只读环境探针：[`scripts/probe-codex-capabilities.ps1`](../scripts/probe-codex-capabilities.ps1)
- 语义校验器：[`scripts/validate-capability-contract.py`](../scripts/validate-capability-contract.py)
- 静态 preflight snapshot：[`evidence/capabilities/2026-08-11-windows-local-preflight.json`](../evidence/capabilities/2026-08-11-windows-local-preflight.json)
- 当前行为 snapshot：[`evidence/capabilities/2026-08-12-windows-local-pilot.json`](../evidence/capabilities/2026-08-12-windows-local-pilot.json)
- 首轮人类可读报告：[`research/capability-pilot-2026-08-12.md`](research/capability-pilot-2026-08-12.md)
- 当前最新 snapshot：[`evidence/capabilities/2026-08-12-windows-local-profile-comparison.json`](../evidence/capabilities/2026-08-12-windows-local-profile-comparison.json)
- Worker profile 对照：[`research/profile-comparison-2026-08-12.md`](research/profile-comparison-2026-08-12.md)
- 行为实验计划：[`research/capability-experiment-plan.md`](research/capability-experiment-plan.md)
- 首个真实工程 lineage：[`research/outputguard-vertical-slice-2026-08-15.md`](research/outputguard-vertical-slice-2026-08-15.md)
- 工程 lineage 机器 evidence：[`evidence/experiments/2026-08-15-outputguard-vertical-slice.json`](../evidence/experiments/2026-08-15-outputguard-vertical-slice.json)

当前两份 snapshot 合起来包含四层事实：

1. 探针可重现的本机 App、CLI、OS、shell、Git 和 repo 状态；
2. 当前会话暴露的工具 schema 声明。
3. 当前项目任务的只读 list/read pilot，包括不存在 ID 的显式失败负例。
4. 独立实验场中的 CLI cwd、idle message/wait、wait cursor 与 idle same-directory fork 行为。

2026-08-12 的初始 Desktop 只读观测确认：主项目是 saved Git project，而当时实验场和 OutputGuard benchmark 不在 `list_projects` 中；create/fork 工具 schema 没有任意 worktree-root 字段。用户随后把实验场内 `outputguard-single` checkout 注册为 saved project，因而初始“未注册”只是带时间的观测，不是永久限制。

第二层不能由 PowerShell 探针自动获取，因此必须在 snapshot 中以 `tool_schema` evidence 单独记录，并注明采集时间和局限。

## Desktop-first 证据边界

D-023 之后，active capability claim 的目标环境是 Codex Desktop。CLI run 只能保留为单独的历史环境行，不能与 Desktop run 合并，也不能因为 task ID 可被 Desktop 读取就改名为 Desktop-native evidence。Shell/Git 检查仍可作为 Desktop task 的辅助证据，但 Agent 回合必须由 Desktop 创建和管理。

只读机制 claim 已于 2026-08-12 有条件地观察到：Desktop 在 saved project `outputguard-single` 中创建了 `local` 任务 `019ff93b-d3a1-7cf3-8ee5-14a6e0561b65`；任务完成一个只读回合后，父任务通过 Desktop read/list 与 Git 独立复核 task cwd、project 映射、branch、`d235f59` 和 clean。结果记录在实验场 `runs/2026-08-12-desktop-native-preflight-01/result.json`。

该只读 claim 的边界本身不变。后续 2026-08-13 qualification 又在相同 saved project/local checkout、固定 HEAD 和解释器条件下观察到简单 Git index/ref 写入与 cleanup、完整 public pytest、Ruff、mypy 外置缓存、固定条件下的离线 package build，以及由真实 Desktop local task 在 assigned permanent worktree 创建 marker-only commit；失败 run 仍保持 `BLOCKED/INVALID`，只复用不受失败影响的命令事实。

2026-08-15 OutputGuard Run02–Run10 又观察到：多条 Desktop local task 可从 saved project 作为控制入口，在 brief 指定的 assigned permanent worktree 执行真实功能修改、commit、artifact handoff、integration 和 read-only review；Run10 的 exact tree 最终通过 public/review/sealed。这里的 handoff 是仓库 artifact + Desktop 消息协调，不是正式 `handoff_thread` 产品操作；也不证明 Desktop-managed worktree、任意 cwd 绑定、archive、subagent、模型/usage telemetry、多任务收益或重复可靠性。普通 Git clean 与 ignored clean 的差异也在 sealed 后被实际观察到。

这些工程证据尚未改写 2026-08-12 capability snapshot 的统计计数。后续若需要把具体 claim 晋升为 active `observed`，应生成新的 dated snapshot，引用 Run10 task/tool/Git before-after，而不是覆盖旧 JSON。

## 最小验证

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/probe-codex-capabilities.ps1
python scripts/validate-capability-contract.py evidence/capabilities/2026-08-11-windows-local-preflight.json
python scripts/validate-capability-contract.py evidence/capabilities/2026-08-12-windows-local-pilot.json
python scripts/validate-capability-contract.py evidence/capabilities/2026-08-12-windows-local-profile-comparison.json
```

探针只读取版本、相关 feature flag、Git identity/status 和 AppX package metadata，结果输出到 stdout；不读取 Codex 配置内容、凭据或环境变量值，也不创建、fork、handoff、归档任务或写入文件。

Validator 使用 Python 标准库，检查结构和项目语义不变量：ID 唯一、evidence 引用闭合、状态合法，以及 `observed` 必须由当前 `behavior_run` 支撑。它不是通用 JSON Schema 引擎；schema 文件仍是跨工具的机器契约。

## 更新规则

以下任一条件变化都要生成新 snapshot，而不是覆盖旧结论：

- Codex App/CLI 或相关 feature flag 改变；
- 当前工具 schema 改变；
- OS、shell、Git 或权限模型改变；
- 行为实验的 project、repo HEAD、workspace mode 或 starting state 改变；
- 新证据支持、限制或反驳既有 claim。

行为实验可以把单条 capability 从 `declared_unverified` 改为 `observed`，但不能顺带升级其他未运行组合。清理动作本身也是实验的一部分；目标不精确、存在用户未提交修改或无法证明可恢复时必须停止。

截至 profile 对照，13 条 capability 中 5 条为有条件的 `observed`、2 条假设被 `contradicted`、6 条仍是 `declared_unverified`。`-C` 能约束 cwd，但不能隔离全局 memory、skills、plugins 或 Codex 自己的 session store；而 `--ignore-user-config` 组合又会移除必要执行规则且仍保留 skill discovery。这些边界必须分开记录。
