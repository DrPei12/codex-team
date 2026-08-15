# Codex Capability Contract 行为实验计划

> 2026-08-12 路线修订：本文件继续保存原语级测试设计和历史证据，但不再是 M1 的主执行顺序。主线已改为真实多 session 工程纵向切片；只有该 workflow 依赖某个仍为 `unknown` 的语义时，才从本计划选取最小 case。不要为了补满矩阵继续创建低边际价值的测试任务。

> 2026-08-12 Desktop-first 修订：后续 Agent 回合只由 Codex Desktop 原生任务工具启动。CLI pilot 是历史证据，不是后续执行后端。用户未明确指定 model/thinking 时不覆盖 Desktop 默认设置；run 记录可观察值，缺失值保持 `unknown`。

## 决策与范围

本轮要决定：当前 Windows Codex Desktop 暴露的多任务原语，是否足以支撑第一条纵向 workflow；哪些语义可以进入 skill，哪些只能保留为人工 runbook 或 `unknown`。CLI 只保留独立历史矩阵，不参与 active Desktop 判定。

本计划只测试 Codex 原生 task、subagent 与 Git workspace 行为，不实现 skill，不测试 Claude Code，不把社区 runtime 的能力写成本项目能力。

## 预注册解释规则

- 工具入口、feature flag 或说明文字只产生 `declared_unverified`。
- 当前环境的成功 run 必须同时保存 tool input/output、任务状态、Git before/after、异常和 cleanup evidence，才产生有条件的 `observed`。
- 一次成功不证明可靠性；首次 run 是 mechanism pilot。关键 case 至少在干净 fixture 上复现一次，才可用于 stable skill 的设计输入。
- 历史通信 smoke test只说明 2026-08-09 的受控 shared-directory 场景曾完成消息闭环；它没有当前 App 版本、任务拓扑、模型、token、生命周期或故障注入，不能升级当前状态。
- 声明与行为不同则记 `contradicted`，不通过改写 claim 来隐藏失败。
- 未运行的平台、host、模型、workspace 组合保持 `unknown`。

## Claim-to-test 矩阵

| Claim ID | 要验证的原子声明 | 最强相关 baseline | 行为测试 | 通过条件 |
|---|---|---|---|---|
| `CAP-INSPECT-01` | list/read 能定位当前任务，且无效 ID 显式失败 | 当前 UI 中人工定位任务 | `T-LIST-CURRENT`、`T-READ-INVALID` | 任务 identity/status 可读取；不存在 ID 不返回空成功 |
| `CAP-CREATE-01` | Git project 的 worktree task 从指定 starting state 创建隔离 workspace | 手工记录同一 ref 的 `git worktree add` Git 事实 | `T-CREATE-DEFAULT`、`T-CREATE-WORKING-TREE` | 新任务 identity、目录、HEAD、branch/detached、tracked/untracked 状态与声明一致 |
| `CAP-FORK-01` | same-directory fork 只复制已完成历史并共享目录 | fresh task + 同一 brief | `T-FORK-SAME-IDLE`、`T-FORK-SAME-RUNNING` | 历史边界与目录 identity 都被读取验证，活动未完成 turn 不被误报为已复制 |
| `CAP-FORK-02` | worktree fork 产生隔离 checkout | create worktree task | `T-FORK-WORKTREE` | child task/workspace 可定位，父子文件状态互不物理污染 |
| `CAP-MSG-01` | direct message 能把 follow-up 送到目标任务 | 用户手动进入目标任务发送同一 prompt | `T-MESSAGE-IDLE`、`T-MESSAGE-RUNNING` | target 收到一次可识别 nonce，状态转换和回复可由 read/wait 取回 |
| `CAP-WAIT-01` | wait 的 cursor 和唤醒语义符合当前 schema | 轮询 read_thread | `T-WAIT-FINAL`、`T-WAIT-CURSOR` | final/input-required 唤醒；已交付 final 不被最新 cursor 重复返回 |
| `CAP-HANDOFF-01` | handoff 能移动其他任务及其 Git 状态 | task 内人工读取 handoff artifact 后继续 | `T-HANDOFF-CLEAN`、`T-HANDOFF-DIRTY` | destination 复核 cwd、HEAD、status、变更范围；源/目标状态明确且无丢失 |
| `CAP-ARCHIVE-01` | archive 改变任务可见生命周期，但不被假设为 worktree cleanup | archive 前后 list + `git worktree list` | `T-ARCHIVE-PRESERVE` | task archive 状态与目录存在性分别记录；没有隐式删除假设 |
| `CAP-SUBAGENT-01` | subagent 是当前任务内的独立短命执行上下文，并遵守 workspace/所有权 | 主任务直接执行同一只读 brief | `T-SUBAGENT-READONLY` | context、cwd、可见文件、消息、结束状态和写入限制都有证据 |

## Baseline、负对照与故障注入

### Baseline

1. **强 baseline**：native single task，不加载本项目 skill，使用同一 repo、brief 和 acceptance Gate。
2. **简单 baseline**：用 Git 命令直接记录 branch、HEAD、worktree 和 status，不借助 Agent 解释。
3. **机制 baseline**：native subagent 或 native multi-task，只使用当前原生工具。
4. **资源 baseline**：记录 task 数、tool calls、wall time、人工干预和 cleanup 操作；token 不可得时明确缺失。

### 负对照

- 对不存在的 thread ID 执行只读 read/wait，确认错误不会被当作空成功；
- 使用已消费 cursor，确认不会重复交付旧 final；
- 在 fixture 中放置唯一 untracked marker，确认默认 worktree 不会被误判为复制了 working tree；
- 对 active turn 做 fork，确认未完成 turn 不会被误判为 completed history；
- 在 handoff artifact 中故意遗漏一个必填证据引用，validator 必须拒绝接收。

负对照只在 disposable fixture/task 中运行，不拿当前包含未提交文档的主工作区做破坏性测试。

## 混杂、泄漏与测量风险

- **版本混杂**：App package、CLI、工具 schema 可能独立更新；每次 run 都单独记录。
- **workspace 泄漏**：same-directory、startingState=`working-tree` 和新 worktree 的可见内容不同；不能共用结论。
- **历史泄漏**：fork child 可能因继承 prompt 得分更高；与 fresh task 对照时使用同一显式 brief。
- **Agent 解释偏差**：Agent 自报 cwd/HEAD 不够；主编排者用 Git/任务工具独立读取。
- **消息非事务性**：消息到达不等于 artifact 已持久化；验收读取 repo evidence。
- **UI/tool 差异**：App 工具声明不能外推到 CLI TUI；CLI 单列环境矩阵。
- **评估者泄漏**：maker 不获知负对照 nonce 的判定细节；verifier 按固定规则验收。
- **缓存/残留**：每个 case 使用唯一 ID，先记录已有 worktree/branch/task，cleanup 后再次读取。

## Run funnel 与预算

1. **Static preflight**：运行 probe + validator；零 task、零 workspace mutation。
2. **Read-only pilot**：list/read/wait 错误语义；不创建任务。已完成 list/read、invalid-ID、completed CLI wait 和 cursor case。
3. **Disposable mechanism pilot**：最多创建 3 个明确命名的测试任务，其中最多 2 个 worktree；只用 fixture repo 或用户明确批准的 starting state。2026-08-12 已用满预算并停止。
4. **Critical reproduction**：只重复第一轮成功且会影响 skill 安全的 create/message/handoff case。
5. **Fault injection**：仅在 fixture 上执行 dirty/untracked/active-turn/invalid-evidence case。

进入第 3 步前必须获得用户对“创建测试任务和 worktree”的明确授权。创建是用户可见的外部状态，不能由“继续研究”推断为已授权。

## 2026-08-12 Pilot 结果

- 用户明确要求建立项目外实验目录并授权继续；实验场、两个 worktree 和三个会话均在预算内创建。
- `codex exec -C` 在两个手工 worktree 中完成只读 fixture 检查，cwd/branch/HEAD/clean 均由主任务复核。
- idle direct message + wait 完成一个唯一 nonce 回合；same-directory fork 继承两个已完成父回合和 cwd。
- 已消费 cursor 会隐藏旧 final body，但 completed/notLoaded CLI task 仍以 `inactiveStatus` 唤醒；编排者必须同时检查 `changed` 和 turn 状态。
- 目录隔离没有阻止全局 memory/skills/plugins 注入；两个极小任务的初始 input tokens 分别为 113,136 和 64,308。
- 并发启动出现一次 system-skills 目录 access-denied，另有多项非致命启动告警；需要 serial-start 与 minimal-profile 对照。
- 新 fixture repo 不会因 CLI session 自动出现在 Desktop `list_projects`；在保持自定义实验根目录的前提下，managed-worktree create/fork/handoff 暂未运行。

完整报告见 [2026-08-12 capability pilot](capability-pilot-2026-08-12.md)。本轮按 stop rule 停止，没有看到结果后追加第 4 个会话。

## 下一条 Desktop 原生 preflight

OutputGuard 试跑已经证明“父任务里准备好的环境”不能替代“真实 worker sandbox 内的 preflight”。下一条实验因此只创建一个只读 Desktop task，不做功能实现。其 preregistration 位于实验场 `runs/2026-08-12-desktop-native-preflight-01/plan.json`。

运行前必须同时满足：

1. 用户明确要求创建该测试任务；“继续研究”或“继续推进”不等于任务创建授权；
2. 用户选择路径方案：把实验场内的干净 checkout 注册为 Desktop saved project 并使用 `local`，或明确允许 Desktop-managed worktree 位于实验场外；
3. 目标 checkout 为 `d235f59dcb7eb853043117402d3a1c8ef267b9af` 且 clean；
4. prompt 只要求读取 task/project/cwd/branch/HEAD/status 和基础执行条件，不改文件、不装依赖、不提交；
5. 父任务能用 Desktop read/wait 和 Git 只读检查复核结果。

任何一项不满足都停止，不以 `codex exec`、手工搬运 worker 结果或主任务代跑来补齐。

### 2026-08-12 结果

用户注册实验场内 `outputguard-single` checkout 后，Desktop 以 `local` 环境创建任务 `019ff93b-d3a1-7cf3-8ee5-14a6e0561b65`。一个 170,990 ms 的只读回合核验了正确 cwd、branch、`d235f59`、开始/结束 clean、Git common dir 和 Python 3.12.1 无 bytecode导入；主任务又通过 Desktop read/list 与 Git status 独立复核。预注册只读范围判定为 PASS。

一次探针异常也被保留：PowerShell 默认编码误读无 BOM 的 `.git` 指针中的中文路径，严格 UTF-8 重读并与 `git rev-parse` 交叉验证后排除仓库异常。后续 helper 不得用默认 `Get-Content` 解析这类 Git file。

没有运行 Git 写入、commit、pytest、mypy、Ruff 或 sealed evaluator。因此下一个 case 是独立 write/test qualification；它必须预注册唯一临时 ref/index 操作与 cleanup，并保持功能评分和隐藏测试不可见。

## Stop rule

满足任一条件立即停止当前 case，记录为 blocked/failed，不尝试绕过：

- 目标 task、project、host、worktree 或 cleanup path 无法唯一解析；
- 当前主工作区出现无法归属的未提交变化；
- 操作可能覆盖、移动或删除用户/其他任务状态；
- 权限或产品保护要求用户确认；
- before snapshot 缺失，因而无法证明 after/cleanup；
- 同一声明连续两次出现不可解释的不一致；
- 预计超出 3 个测试任务或 2 个 worktree 的预注册 pilot 预算。
- active run 不是由 Codex Desktop 原生任务工具创建，或需要 CLI fallback；
- saved project 与用户批准的实验根目录策略冲突且尚未得到选择。

不使用递归删除作为默认 cleanup。归档任务和删除 worktree 是两项独立操作，分别授权、执行和取证。

## 产物与判定

每个 run 保存：环境 snapshot、claim ID、tool input/output、task/thread identity、Git before/after、结果、异常、coverage/not-covered、cleanup before/after 和 evidence hash。数据写入版本库前移除凭据、token、环境变量值和无关用户路径。

第一条纵向 workflow 只有在以下条件同时满足后才进入 spec：

- 所依赖的 capability 在目标环境为 `observed`，或 workflow 对 `unknown` 明确 fail closed；
- no-skill/native baseline 已定义；
- 至少一个负对照能被 verifier 拒绝；
- cleanup 和生命周期边界可证明；
- 尚未验证的 App/CLI/OS 组合保持 unknown。
