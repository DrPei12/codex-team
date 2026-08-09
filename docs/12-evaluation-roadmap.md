# 12. 评测路线

## 为什么必须做对照实验

多任务系统很容易在演示里显得强大：多个任务同时输出、消息互相到达、worktree 都有代码。但真实收益必须扣除 briefing、重复探索、等待、审查、合并、重测、失败恢复和任务管理成本。

评测单位应是“一个可验收的工程结果”，不是单个 worker 的输出数量。

## 已完成的最小通信实验

### 实验内容

任务 A 向任务 B 分配 PowerShell 文本统计脚本工作，B 实现并运行测试，A 独立验收后要求 `byteCount` 增强；B 报告后，A 要求十六进制诊断，最终定位 Windows PowerShell 5.1 对源码编码的误解，并用 ASCII 源码表达式 `[char]0x03B2` 修正。

最终本地证据：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\work\thread-communication-lab\test-text-stats.ps1
exit 0
PASS: valid UTF-8 (byteCount=15, characterCount=12), missing-path, and directory-path cases
fixture hex: 61-6C-70-68-61-0A-20-20-20-0A-CE-B2-65-74-61
```

### 证明了什么

- 任务 A 可以直接给 B 发送后续指令；
- B 的消息能唤醒/通知 A；
- 共享目录变化可以被另一任务读取和验收；
- Agent 间可以形成“实现 → 质疑 → 诊断 → 修正 → 接收”的闭环；
- 环境假设需要先验证：实验最初误假定 `pwsh` 存在，后改为 `powershell.exe`。

### 没有证明什么

- 没记录 token、算力和完整 wall time；
- 编排者与 worker 没做模型/thinking 分级；
- 没测单任务多轮分配后的性能衰减；
- 没测任务保留/归档和 UI 复杂度；
- 没与 subagent、fresh task、worktree 隔离进行对照；
- 任务很小，不能证明大型并行工程收益；
- 同目录实验不能证明自动 merge 或冲突治理。

因此它只是通信 smoke test，不是系统可用性结论。

## 评测矩阵

### E1：模型与 thinking 分配

对照：

- 全员高能力/高 thinking；
- 高能力主编排者 + 常规模型 worker；
- 常规模型主编排者 + 强 reviewer；
- 自动升级策略。

指标：首次通过率、缺陷、返工、总 wall time、token（可取得时）、用户介入和升级正确率。

### E2：Briefing 形式

对照短结构化 brief、长叙述 prompt、结构化 brief + 按需 references。控制任务、模型和 workspace 一致。

### E3：单任务有效上下文

同一个 worker 连续领取 1/3/5/8 个同类和异类任务，并与每次 fresh task、forked task、rehydrated task 对比。不能只统计轮数；记录累计输入、压缩事件和 task switching。

观察：需求引用准确率、重复探索、旧决策污染、执行错误、handoff 完整度和单位有效产出。

### E4：Workspace 隔离

对照同一 checkout、managed worktree、permanent worktree；设置文件无重叠、同文件重叠、共享生成物和共享外部服务四类场景。

### E5：编排范式

在同一中型功能上对照：单任务、hub-and-spoke、stage pipeline、contract-parallel。任务必须有相同 acceptance Gate。

### E6：Proof-carrying handoff

设置 30 分钟模拟/真实 suite，对照：接收方全量重跑、只读声明、验证 evidence + affected Gate。注入错误 revision、过期 lockfile、伪造 exit code、flaky 和 merge 后组合失败。

### E7：任务 vs subagent vs 混合

对照：

- 单主任务；
- 主任务 + subagent；
- 多个用户可见任务；
- 多任务 + 各自 subagent。

关注独立历史、隔离、用户可见性、handoff、成本和恢复能力，不预设谁一定更好。

### E8：任务生命周期

建立大量一次性任务，比较全部保留、自动归档、长期 owner + 临时任务归档。测状态查找时间、误投消息、恢复任务所需信息和 worktree 泄漏。

### E9：自动集成上限

逐级提高：无重叠文件 → 同契约不同模块 → 同文件可机械合并 → 语义冲突 → 数据迁移。记录系统何时能自动完成、何时正确停下、何时错误自信。

## Baseline 来源

- Codex 官方 worktree、subagent 和 compaction 文档提供能力与限制 baseline；
- A2A 官方规范提供任务/消息/artifact baseline；
- “Lost in the Middle”和 Context Rot 等研究提供长上下文风险假设；
- 实际阈值必须用当前 Codex 模型和真实代码库重测，不能直接照搬论文中的模型结论。

## 最低实验质量

- 固定代码库 snapshot、task spec 和 acceptance Gate；
- 至少重复多次并记录随机性；
- 保存所有 prompt/task artifact、revision、环境和证据；
- 区分执行时间、等待时间、模型时间和人工时间；
- 记录失败与撤销，不只展示成功 run；
- 不用同一 Agent 既设计评分又在不知道标准的情况下随意判分；
- 结论标注适用范围，不把单仓库结果外推到所有工程。

## Phase 1 推荐实验

先选一个 2–4 小时、中等规模、包含两个可并行模块和一个集成点的真实任务，完成 E1、E4、E6、E7 的最小矩阵。它比继续做微型通信 demo 更能决定第一批 skills 的设计。
