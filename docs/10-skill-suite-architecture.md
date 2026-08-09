# 10. 大型 Skills 套件架构

## 设计目标

最终产品不是一个巨型 `SKILL.md`，而是一个 Codex 专用的多-skill 工程，像 gstack 或 superpowers 一样：用户按意图触发一个入口，系统只加载当前范式、worker 和阶段需要的细节。

## 三类 skills

### A. 用户入口 skills

这些是用户最常调用的高层能力：

| 候选名 | 责任 |
|---|---|
| `team-init` | 识别项目状态，建立治理文件和能力清单 |
| `team-plan` | 分析依赖与风险，选择范式、worker 和 workspace，输出待确认计划 |
| `team-run` | 按已接受计划创建/唤醒任务、派发和等待 |
| `team-status` | 汇总 active roster、阻塞、证据和下一事件 |
| `team-integrate` | 校验 handoff、安排合并和分层 Gate |
| `team-review` | 运行独立 reviewer / maker-checker 工作流 |
| `team-recover` | 处理失败、冲突、stale task 和 incident swarm |
| `team-close` | 完成里程碑、归档任务、标记 worktree 清理候选和生成项目总结 |

入口 skill 是路由器和治理者，不应复制每个范式的完整说明。

### B. 编排范式 skills

每个范式 skill 负责一个协作拓扑、触发条件和失败模式：

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

它们输出可组合的 task graph，不亲自硬编码某个模型或 workspace。

### C. Worker role skills

每个 role skill 规定该角色如何读取任务、工作、产出和上报：

- `worker-orchestrator`
- `worker-explorer`
- `worker-implementer`
- `worker-component-owner`
- `worker-reviewer`
- `worker-integrator`
- `worker-recovery`
- `worker-release-owner`

Workspace 不是 role skill。`managed-worktree`、`same-checkout`、`permanent-worktree` 等通过 worker card 和共享安全规则配置，避免产生“每个角色 × 每种环境”的组合爆炸。

## 共享能力

套件需要共享但按需加载的资源：

- task、worker card、artifact、handoff 和 evidence schema；
- Codex 任务工具使用规则；
- Git/worktree 安全检查；
- A2A-aligned 状态和消息映射；
- 模型/thinking policy；
- 评测记录器与状态汇总脚本；
- 示例任务图、失败案例和恢复 runbook。

具体打包方式需用 Codex 当前 plugin/skill 安装与相对路径规则验证。未验证前，不复制同一份协议到十几个 skill，也不假定任意跨目录引用都能在安装后工作。

## 渐进式披露

### Level 0：发现

Codex 只看到 skill 名称和一两句触发描述。例如用户说“把这个里程碑分给多个任务并行做”，只需要发现 `team-plan`。

### Level 1：入口流程

加载 `team-plan/SKILL.md`，只包含：检查条件、最小决策树、必须产物和何时停止。保持精炼，避免把全部方法论注入主上下文。

### Level 2：选定范式

决策后只加载 `pattern-contract-parallel` 或相关的两三个范式 reference，而不是读取全部 11 种。

### Level 3：选定角色与 workspace

创建具体 worker 时，只加载对应 role instructions、worker card 和 Git 安全规则。

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
│   ├── pattern-contract-parallel/
│   ├── pattern-stage-pipeline/
│   ├── worker-component-owner/
│   └── worker-integrator/
├── shared/
│   ├── schemas/
│   ├── scripts/
│   ├── references/
│   └── examples/
├── evaluations/
└── docs/
```

在真正落地前要验证：安装后各 skill 是否能可靠定位 shared 资源；如果不能，则改为生成时注入、专门的 core skill，或最小重复的版本化 schema。不要为结构美观牺牲可运行性。

## 单个 skill 的质量要求

- `SKILL.md` 说明触发/非触发条件、步骤、停止条件和验证，尽量低于约 500 行；
- 深入原理和长示例放 `references/`，并由主文件明确路由；
- 可确定执行的内容写 script，并提供 `--dry-run` / fail-closed 行为；
- 若有模板/静态文件，放 assets；
- 生成或更新后运行 skill validator；
- 至少做触发测试、正向运行、错误输入、冲突 workspace 和中断恢复测试；
- 不增加与执行无关的单-skill README、changelog 或过程日志。

## 第一批实现建议

不要同时实现全部 20 多个 skills。首个纵向切片应闭环：

1. `team-plan`
2. `team-run`
3. `pattern-contract-parallel`
4. `worker-implementer`
5. `worker-integrator`
6. `team-status`
7. task/handoff/evidence schema 与 validator

用一个中型真实仓库验证创建任务 → worktree 实现 → artifact handoff → evidence reuse → 集成 → 归档，再扩展其它范式。

## 与 subagent 的组合

任务层负责长期责任、独立历史、workspace 和跨阶段交接；subagent 层负责父任务内部的短搜索、局部实现和并行检查。套件不会强迫二选一，也不会让 subagent 取代项目状态存储。
