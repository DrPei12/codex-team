# 10. Skills 套件架构

## 设计目标

最终交付不是一个巨型 `SKILL.md`，而是一个 Codex 专用、社区开源的多-skill 研究与实践套件。规模可以随已验证能力持续增长，参考 oh-my-codex、gstack 和 Superpowers 的广度；用户按意图触发入口，Codex 只加载当前阶段需要的 workflow、profile、协议和执行资源。

Prior-art 调查带来一个关键修正：知识分类不自动等于 skill 分类。编排范式、worker 角色和 workspace 是重要概念，但只有在具备独立触发、独立行为与独立验收时才应各自成为 skill。

第二轮源码调查又带来一个优先级修正：本项目首先要解决的不是 skill 自动加载或长期上下文管理，而是一个中等偏大的功能怎样被拆成、派给并管理若干条 Codex session，最后安全集成。上下文和生命周期继续保留，但不再主导第一条纵向切片。详细依据见 [大型 Skill 套件的工程方法提炼](research/large-skill-suite-engineering-methods.md)。

D-023 再收紧了执行边界：这里的 “Codex session/task” 默认就是 Codex Desktop 中用户可见的原生任务。套件可以调用 Desktop task/fork/message/wait/handoff 工具，并在任务内运行 Git、测试和确定性 helper；它不以 `codex exec`、tmux 或自建 daemon 充当后台调度器。

## 六类交付物

### A. Workflow entry skills

第一条纵向切片原定五个连续入口。OutputGuard Run02–Run10 表明，恢复不是偶发附属动作，而是具有独立触发、输入、停止条件和验收的正式 workflow，因此首批架构修订为“五个主线入口 + 一个恢复入口”：

| 候选名 | 责任 |
|---|---|
| `team-plan` | 读需求与仓库，先冻结共享契约，再输出任务图、session 数、文件所有权、依赖、worktree、Gate 和集成顺序 |
| `team-run` | 按用户接受的计划通过 Desktop 创建/选择 task 与 workspace，派发 task brief，记录 task/project identity、起始 revision 和可观察的模型配置 |
| `team-status` | 汇总 roster、依赖、阻塞、消息、证据和下一动作；必要时重派或收缩 scope |
| `team-integrate` | 校验 worker report/commit/evidence，按依赖顺序接收，运行独立 review 与 affected/integration Gate |
| `team-finish` | 形成里程碑结论，归档已接收的一次性任务，保留未获授权清理的 worktree，并写明恢复入口 |
| `team-recover` | 从一个明确 blocked run 继续：绑定精确 candidate、旧证据、尚未建立的新事实和新预算；保持旧 run 不变，禁止无关重做 |

`team-review`、`team-benchmark` 和 capability audit 后续可以形成独立入口；第一版仍可作为 `team-integrate`、`team-status` 或项目开发工具的子流程。`team-recover` 的晋升来自重复实测：Run03、Run05、Run06、Run08、Run09、Run10 都需要“保留旧结论，只验证一个新事实”的恢复语义。入口 skill 是路由器和治理者，不应复制每个范式的完整说明。

这五个入口分别对应用户可说出的独立意图。Capability matrix、worker profile 和 pattern catalog 是它们按需读取的支撑资源，不为目录对称强行包装成用户入口。

### B. Execution skills 与 pattern profiles

完整 pattern catalog 继续保留：

- `pattern-hub-spoke`
- `pattern-stage-pipeline`
- `pattern-contract-parallel`
- `pattern-component-ownership`
- `pattern-planner-executor-verifier`
- `pattern-maker-checker`
- `pattern-expert-council`
- `pattern-competing-prototypes`
- `pattern-work-queue`
- `pattern-incident-swarm`
- `pattern-blackboard`

第一阶段把它们实现成可被 `team-plan` 按需读取的 decision profile/reference，而不是立即制造 11 个技能入口。某个 pattern 只有在以下条件成立后才晋升独立 execution skill：

- 用户或 Agent 能独立识别其触发/非触发条件；
- 它会改变 task graph、工具、artifact、停止条件或恢复策略；
- 单独加载比内嵌 reference 更省上下文或更少犯错；
- 存在 no-pattern baseline、正向案例、冲突案例和恢复案例。

晋升后仍只输出可组合 task graph 和运行规则，不硬编码模型或 workspace。

### C. Agent profiles

下列角色优先实现为 Codex agent definition、worker card 和 brief 模板：

- `worker-orchestrator`
- `worker-explorer`
- `worker-implementer`
- `worker-component-owner`
- `worker-reviewer`
- `worker-integrator`
- `worker-recovery`
- `worker-release-owner`

角色只有出现独立用户 workflow 时才再包装为 skill。Workspace 仍不是 role skill；`managed-worktree`、`same-checkout`、`permanent-worktree` 等通过 worker card、capability matrix 和共享安全规则配置，避免“每个角色 × 每种环境”的组合爆炸。

### D. Research 与 evaluation skills

这类能力仍是项目自身保证质量的工具，但排在首个多 session 工程闭环之后：

| 候选名 | 责任 |
|---|---|
| `team-benchmark` | 在固定 repo/task/Gate 上运行 single/subagent/multi-task/混合对照 |
| `skill-evaluate` | 运行 no-skill/skill/版本不匹配 skill 的成对评测 |
| `team-failure-lab` | 注入 stale status、错误 revision、冲突、flaky、失联 worker 等故障 |
| `team-evidence-audit` | 核验 evidence identity、完整性、失效条件和可复现性 |
| `team-replay` | 从固定 artifact 与 revision 重放一次运行或恢复流程 |

它们可以先以 research maturity 发布，帮助社区共同积累证据。

### E. Shared protocol 与 deterministic helpers

套件需要共享但按需加载的资源：

- task、worker card、artifact、handoff 和 evidence schema；
- Codex capability matrix 与版本探针；
- Codex Desktop 任务工具使用规则和行为 snapshot；
- Git/worktree preflight、安全检查与 cleanup plan；
- A2A-aligned 状态和消息映射；
- 模型/thinking policy；
- 评测记录器、evidence collector 与状态汇总脚本；
- compatibility、provenance 和 skill permission manifest。

OutputGuard 首轮实战把共享骨架进一步收紧为以下硬要求：

- 一个 canonical run manifest 是 revision、tree、路径、hash、命令、预算和授权的单一来源；task brief、preregistration、freeze 和 handoff 中的重复身份必须由工具生成或验证，禁止人工补全 hash；
- hash proof 必须绑定唯一的字节生成命令、参数、path order、编码和换行规则，不能只写“diff hash”；
- artifact、pytest basetemp、mypy cache、build cache 和 dist root 必须在 task 创建前按声明的初始状态创建并核验；
- formatter apply、生成文件等已授权 mutation step 与 check-only Gate 分开，check 仍遵守 first-nonzero stop；
- run timeline 和 predecessor 状态 append-only；recovery 产生新的 run ID，不能把旧 `blocked` 改成 `passed`；
- finish audit 分开报告 ordinary、untracked、ignored、Git operation residue 与 run-local artifact。普通 porcelain clean 不等于目录无残留。

Worker preflight 仍把隔离拆成三层，而不是只记录一个 `workspace_mode`：

1. `filesystem_boundary`：允许的 cwd/worktree 根目录和可写路径；
2. `git_boundary`：repository、branch、HEAD、dirty 状态和所有权；
3. `runtime_context_boundary`：user config、memory、skills、plugins、MCP、模型设置和预计上下文预算。

历史 CLI pilot 中，`codex exec -C` 只证明当时 CLI 的 cwd 绑定，不能证明 Desktop 或第三层隔离。`team-run` 必须让即将执行工作的 Desktop task 自己完成 preflight，再由主任务复核路径/branch/HEAD；父任务里先验成功不算 worker 环境成功。上下文加载项只记录，不在第一版继续穷举裁剪。粗暴 minimal profile 已被一次反例否定，后续作为单独优化研究，不阻塞 task 编排。

当前 Desktop 模型政策也是共享 preflight 的一部分：只有用户明确指定时才覆盖 model/thinking，否则使用 Desktop 默认值；run 记录 requested/effective 值，无法观察的字段保持 `unknown`。配置不符时 fail closed，不以 CLI fallback。

Workspace policy 也必须在创建前校验：repository work 只能选择 Desktop saved project。若要求自定义实验根目录，而 create/fork schema 又不能指定任意 worktree root，`team-run` 必须停止并让用户选择“注册实验场内 checkout 后使用 local task”或“允许 Desktop-managed worktree 使用默认位置”。

具体打包方式需用 Codex 当前 plugin/skill 安装与相对路径规则验证。未验证前，不复制同一份协议到十几个 skill，也不假定任意跨目录引用都能在安装后工作。

### F. References、examples 与 failure corpus

深入原理、完整 pattern catalog、decision tables、runbooks、成功 traces、失败 traces、Windows/App/CLI 差异和 prior-art 证据放在按需加载资源中。它们是正式项目产物，不必为了获得价值而全部伪装成 skill。

## 成熟度模型

| 等级 | 含义 | 可以对外声称什么 |
|---|---|---|
| `research` | 有来源、问题定义、假设或实验设计 | “值得研究/已有外部证据”，不能声称可稳定运行 |
| `incubating` | 有可执行实现、固定示例和初步证据 | “可试用”，必须公开兼容范围和失败模式 |
| `stable` | 触发、行为、错误输入、恢复、版本和回归评测达标 | “在已列环境与版本中通过验收” |
| `deprecated` | 被产品变化、协议或实验证据替代 | 保留迁移说明和历史 evidence，不再默认路由 |

每个 skill、profile 和 schema 都单独标成熟度；套件整体不会因为包含 research 项就伪装成全面 stable。

## 渐进式披露

### Level 0：发现

Codex 只看到 skill 名称和一两句触发描述。例如用户说“把这个里程碑分给多个任务并行做”，只需要发现 `team-plan`。

### Level 1：入口流程

加载 `team-plan/SKILL.md`，只包含：检查条件、最小决策树、必须产物和何时停止。保持精炼，避免把全部方法论注入主上下文。

### Level 2：选定范式

决策后只加载 `pattern-contract-parallel` profile 或相关的两三个 reference，而不是读取全部 catalog。只有已晋升的 pattern 才作为独立 skill 调用。

### Level 3：选定角色与 workspace

创建具体 worker 时，只加载对应 agent profile、worker card、capability matrix 和 Git 安全规则。

### Level 4：执行资源

真正需要时才运行 schema validator、worktree preflight、evidence collector 或 status renderer。长示例和边缘情况放 references，确定性操作放 scripts。

## 候选目录结构

这是设计草案，不代表 Phase 0 已创建这些 skills：

```text
codex-multitask-engineering/
├── skills/
│   ├── team-plan/
│   │   ├── SKILL.md
│   │   ├── agents/openai.yaml
│   │   └── references/
│   ├── team-run/
│   ├── team-status/
│   ├── team-integrate/
│   ├── team-finish/
│   └── team-recover/
├── agents/
│   ├── implementer.toml
│   ├── reviewer.toml
│   └── integrator.toml
├── shared/
│   ├── schemas/
│   ├── scripts/
│   ├── references/
│   │   ├── patterns/
│   │   └── runbooks/
│   ├── compatibility/
│   └── examples/
├── evaluations/
│   ├── cases/
│   ├── baselines/
│   └── artifacts/
├── research/
└── docs/
```

后续通过实战证明独立触发价值后，再加入 `team-review`、`team-benchmark`、`skill-evaluate` 等目录。`team-recover` 已由 OutputGuard 的多次 fail-closed recovery 获得首批候选资格，但仍需实现和跨 benchmark 评测，成熟度只能是 `incubating`。

在真正落地前要验证：安装后各 skill 是否能可靠定位 shared 资源；如果不能，则改为生成时注入、专门的 core skill，或最小重复的版本化 schema。不要为结构美观牺牲可运行性。

## 单个 skill 的质量要求

- `SKILL.md` 说明触发/非触发条件、步骤、停止条件和验证，并保持可被渐进加载；在实测前不把行数写成跨 skill 的固定质量阈值；
- 深入原理和长示例放 `references/`，并由主文件明确路由；
- 可确定执行的内容写 script，并提供 `--dry-run` / fail-closed 行为；
- 若有模板/静态文件，放 assets；
- 生成或更新后运行 skill validator；
- 至少做触发测试、正向运行、错误输入、冲突 workspace 和中断恢复测试；
- 对可比较 workflow 做 no-skill baseline，记录 pass、token、wall time、返工和用户介入；
- 声明 Codex Desktop、OS、tool schema、模型或依赖版本兼容范围；CLI 历史证据单列，不混入 Desktop 兼容声明；
- 记录来源、许可、revision 和本地改写，脚本/外部工具接受供应链与权限审查；
- 不增加与执行无关的单-skill README、changelog 或过程日志。

## 第一批实现建议

长期范围可以超过 20 个 skills，但首批实现按证据风险排序，不按目录展示效果排序：

1. 先升级共享 schema/validator：canonical run manifest、生成式 projection、artifact-root precondition、Gate receipt、recovery link 和 ordinary/ignored cleanliness receipt；
2. `team-plan`：仓库调查、contract freeze、DAG、所有权和集成计划，并生成 canonical manifest；
3. `team-run`：从 manifest 派生 brief/preregistration，通过 Desktop 创建 3–5 条可观察的 worker task/workspace，先由 parent 和真实 task 分别通过机器 preflight；
4. `team-status`：等待、消息、阻塞、依赖解锁和 append-only timeline，不把 `DONE` 当作 `ACCEPTED`；
5. `team-integrate`：单一 integrator 接收 commit/evidence，运行合并产生的新事实 Gate，并要求新 Reviewer；
6. `team-finish`：状态收口、sealed authorization、ordinary/ignored audit、归档候选和 worktree 保留/清理边界；
7. `team-recover`：只携带精确 candidate 和旧 proof，声明唯一新增事实，创建 successor run，不重写旧 run；
8. 提供 contract-parallel reference，以及 implementer、reviewer、integrator profiles，并把 OutputGuard Run02–Run10 收入 failure corpus。

OutputGuard 已经验证了手工流程可以恢复到公开、审查和 sealed Gate 全部通过，但它不是 skills 边际效用证据。实现冻结后应换一个未见过的第二 benchmark 做 no-skill/native single 与 skill-assisted 对照；OutputGuard 主要用于回归这些已知失败模式。`pattern-contract-parallel` 和 worker role 在产生独立触发证据前仍不必单独包装成 skill。

## 与 subagent 的组合

任务层负责长期责任、独立历史、workspace 和跨阶段交接；subagent 层负责父任务内部的短搜索、局部实现和并行检查。套件不会强迫二选一，也不会让 subagent 取代项目状态存储。

默认先把短、只读、边界明确的工作交给 subagent；需要独立历史、独立 worktree、跨阶段持续或用户可直接查看的实现 lane 使用用户可见 task。写入型并行必须有文件所有权和独立 worktree；共享 contract 先串行冻结。`team-plan` 根据持续时间、依赖、workspace、可恢复性和协调成本选择 task/subagent/串行，并在无法清楚切分时明确拒绝并行。
