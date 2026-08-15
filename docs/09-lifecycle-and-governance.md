# 09. 任务生命周期与治理

## 为什么不能把所有任务一直留着

任务保留几乎不占 Git 合并成本，但会占据人的注意力和控制平面复杂度：侧边栏冗繁、owner 不清、旧任务被误唤醒、过时上下文继续传播、worktree 和 branch 无人清理。

因此“保留历史”与“保持活跃”必须分开。归档不是删除证据，而是退出活动 roster。

## 生命周期状态

| 状态 | 含义 | 是否接新任务 |
|---|---|---|
| proposed | 已规划，尚未创建/启动 | 否 |
| active | 正在承担明确责任 | 是 |
| waiting | 等依赖或外部事件 | 原则上否 |
| blocked | stop rule 已触发，原因和证据已固化；不能在原 run 中继续试错 | 否 |
| handoff-ready | 输出完成，等待接收 | 否 |
| accepted | 主编排者已验收 handoff identity/evidence，等待或允许集成 | 原则上否 |
| integrating | 由集成者处理 | 仅修复集成问题 |
| reviewed | 精确 integration tree 已得到独立 review 决定 | 否 |
| retained | 阶段完成，但作为长期 owner 保留 | 可唤醒 |
| rotating | 正在向后继任务交接 | 否 |
| archived | 历史可查，不在活动 roster | 否 |
| canceled/superseded | 停止或被替代 | 否 |

这些是项目控制平面状态，不替代 A2A Task 的规范状态。

## 默认保留策略

### 应保留

- 主编排任务；
- 仍对活动模块负责的 component owner；
- 当前阶段的 integrator 或 incident owner；
- 即将被依赖且重建上下文成本很高的专家任务。

### 应归档

- 已被接收的一次性实现任务；
- 完成只读调查且 artifact 已持久化的 explorer；
- 未被选中的竞争原型；
- 已完成 handoff 的旧 owner；
- 长期 waiting 且没有明确唤醒事件的任务；
- 被新任务或新方案 supersede 的任务。

### 不应直接删除

只要任务参与了关键决策、代码产生或验收，就应保留可审计历史，至少直到项目策略允许清理。优先 archive，而非物理删除。

## Active roster

主编排者维护一个小而明确的活动名单：

- task/thread ID 和名称；
- 当前角色与 owner 范围；
- workspace/branch；
- 当前 task ID、状态、依赖和最后事件；
- 下次唤醒条件；
- 计划保留、轮换或归档。

不先规定固定最大数量。合理上限取决于主编排者能否在不漏掉状态、契约和集成顺序的前提下管理；评测应找出不同范式的甜点区。

## 命名规则

建议格式：

```text
<project>:<role-or-component>:<phase-or-purpose>
```

例如：

- `codex-team:orchestrator:main`
- `codex-team:protocol:task-model`
- `codex-team:evaluation:context-rot`
- `codex-team:integrator:phase-1`

名称帮助人浏览，稳定关联仍使用 task/thread ID。

## 等待与唤醒

- 等待必须绑定事件：某 task 完成、某 approval 到达、CI 结束或某时间点；
- 不用高频 read/poll 模拟管理；优先使用可以返回状态变化的等待能力；
- 无变化的 snapshot 不向用户重复播报；
- worker 请求用户输入时，不让另一个任务代替用户作风险决策。

## 上下文轮换流程

1. 冻结旧 owner 的新任务分配；
2. 将当前目标、决策、revision、workspace、未决风险和下一步写成交接 artifact；
3. 新任务从仓库 rehydrate 或接收 handoff；
4. 新任务独立确认路径、Git 状态和关键 contract；
5. 用一个小的 continuation task 验证接班质量；
6. 通过后归档旧任务，失败则补交接而不是让两者长期双 owner。

## Blocked run 与 recovery lineage

任务生命周期和实验 run 生命周期不能混为一个可覆盖状态。某个 task 可以结束并归档，但它参与的 run 仍永久保持 `blocked`；后续成功只能通过新的 successor run 建立。

恢复流程：

1. 冻结 predecessor 的 status、timeline、artifact hash 和 worktree 现场；
2. 区分仍有效的 proof、未知事实和明确失效的 evidence；
3. 对 dirty candidate 绑定 exact bytes/hash、Git identity 和唯一生成算法；
4. 创建新的 run ID、预算和 task，不复用旧 run 的“继续按钮”隐藏额外尝试；
5. 只授权验证唯一的新事实，遵守新的 first-nonzero stop；
6. successor 成功后引用 predecessor，但不修改 predecessor result；
7. 接收完成后再按任务治理决定 archive/retain，worktree cleanup 仍需单独授权。

OutputGuard Run02–Run10 已在一个案例中观察到这种 append-only lineage 能最终通过公开、审查和 sealed Gate；它尚未证明自动 recovery、长期 lease 或跨机器恢复。

## Worktree 生命周期

任务归档不自动等于可以删除 worktree。删除前必须确认：

- 所有有价值变更已经 commit、合并或另行保存；
- handoff 和证据引用不依赖未保存文件；
- branch/HEAD 归属清楚；
- 没有其他任务仍绑定该路径；
- 删除符合用户授权和 Codex 当前产品规则。

第一版 skills 应建议或标记清理候选，不在无法证明安全时递归删除目录。

## UI 冗繁的解决方式

不是减少项目能力，而是分层展示：默认只显示主任务、活跃 owner、阻塞和待验收；已完成临时任务自动进入 archive 视图；详细历史通过 context/task ID 查询。仓库中的状态页应能在任务 UI 之外重建 roster。
