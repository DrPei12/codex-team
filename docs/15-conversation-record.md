# 15. 立项讨论记录

## 记录性质

本文保存从功能探索到正式立项的完整决策脉络、要求变化、实验事实和未决问题。它是根据当前对话整理的**决策级记录**，不是逐字 transcript；原始任务历史仍是逐字来源。

## 第一阶段：提出探索目标

用户最初希望测试 Codex 任务之间直接交流和互相下指令的能力，并探索它在真实开发中的可用性和多样性。

真正希望先解决的问题是：

- 这种能力在原理上是什么；
- 任务 A 给任务 B 分配、B 回报 A 的机制如何落到开发流程；
- 除“一个总编排者对多个并行开发者”和“ABC 阶段少次、大包交接”外，还有哪些编排范式；
- 不同模型、上下文、workspace、验收和生命周期如何影响实际收益；
- 它与 subagent 的差异和组合方式是什么。

## 第二阶段：出现了不应提前执行的实验

在尚未先完成原理讨论和实验设计时，助手直接启动了线程协作实验 A。这不符合用户要求；用户明确指出“没让我直接开始执行”。该错误成为本项目的第一条治理教训：**讨论、诊断和实验设计不自动授权实际创建任务或修改文件，除非用户明确要求执行。**

### 实验本身的过程

虽然启动时机错误，实验留下了可核验的技术观察：

1. A 直接向 B（task/thread ID `019fe50a-0367-71c0-8f38-c520df3956eb`）发送首版实现指令，写明 spec、文件所有权、测试命令和直接回报要求。
2. B 完成首版并向 A 回报 exit 0。
3. A 没有仅凭消息接受，而是独立检查后下发第二条 `byteCount` 增强指令。
4. B 最初回报 `byteCount=16`。A 要求十六进制诊断。
5. B 发现 Windows PowerShell 5.1 把无 BOM UTF-8 源码中的 `β` 字节 `CE-B2` 按 ANSI 误读为“尾”，随后把源码改成 ASCII 表达式 `[char]0x03B2`。
6. A 最终复验后向 B 发送 PASS 和停止修改结论。

实验文件当时位于：

- A：`work/thread-communication-lab/spec.md`、`review.md`
- B：`text-stats.ps1`、`test-text-stats.ps1`

最终命令与结果：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\work\thread-communication-lab\test-text-stats.ps1
exit 0
PASS: valid UTF-8 (byteCount=15, characterCount=12), missing-path, and directory-path cases
fixture hex: 61-6C-70-68-61-0A-20-20-20-0A-CE-B2-65-74-61
```

这次 smoke test 证明了直接消息、再次下令、回报和等待唤醒可以闭环，也证明“消息已到”不等于“磁盘状态已验收”。它还暴露了环境假设问题：最初误认为 `pwsh` 存在，实际应先检查并使用 `powershell.exe`。

## 第三阶段：用户对实验提出五项批评

### 1. 没有记录 token 消耗

用户指出实验没有记录总编排者和各任务的 token，无法评价效率。讨论后形成的结论是：当前产品可能需要外部 telemetry 才能完整记录；它不是立项阻塞项，但后续评测必须预留数据字段，不能忽略或伪造。

### 2. 模型与 thinking 没有分级

实验中的任务使用了与当前任务相近的模型和思考程度，没有验证“强编排者 + 较低成本执行者”的价值。用户提出：总编排者可使用 `sol-max/ultra` 一类高能力配置，执行者在获得高质量任务说明后可使用 `luna-max` 一类更经济配置。

讨论修正了一个潜在逻辑跳跃：详细 prompt 并不能保证低能力模型处理所有异常，过长 prompt 也可能降低信噪比。初版方向确定为：结构化 briefing、按认知难度选模型、明确升级条件，具体模型映射用对照实验决定。

### 3. 没测单任务的最高有效上下文

用户要求研究同一执行任务被连续分配多少轮后出现明显质量下降。结论是不能只按“轮数”给统一阈值，需要记录累计上下文、任务切换、压缩事件、重复探索、旧决策污染和返工率。先参考官方 compaction 说明与社区/研究中的 context rot，再设计 persistent、fresh、forked、compacted 和 rehydrated 对照。

### 4. 完成后的任务是否保留

用户关心任务过多导致界面和管理冗繁。讨论后接受：主编排者和活动模块 owner 保留；一次性任务在 artifact 被验收后归档；上下文老化的长期 owner 通过 handoff 轮换；归档与 worktree 删除必须分开。

### 5. 与 subagent 的差异

讨论认为用户可见任务的上限通常更高：独立历史、可独立 workspace/worktree、跨阶段存在、用户可直接继续；subagent 更适合父任务内部短工作。但“subagent 只是 tool”只是便于理解的比喻，它仍是能推理和执行的 Agent。最终没有二选一，而是采用混合模式。

## 第四阶段：围绕能力上限的十二点深化

用户进一步提出并确认了以下方向。

### 独立环境带来的并行上限

每个 Codex 任务可以管理自身工作环境和 worktree，使全自动并行工程成为值得研究的可能性。讨论同时澄清：worktree 只隔离文件视图，不自动消除 Git merge conflict、语义矛盾、共享服务冲突和集成失败，所以“能力翻倍”是待测假设，不是已确认线性收益。

### Agent 专用汇报

B 向 A 的汇报应与面向用户的自然语言答复不同：结构化、可定位 revision、可验证、引用 artifact、说明覆盖和下一动作。面向用户的报告仍应结论优先、便于人判断。两种输出可以共享事实，但表现层不同。

### 避免重复执行长测试

用户用 30 分钟测试举例：B 跑过后 A 再跑会形成 Agent 版低效会议。讨论形成 proof-carrying handoff：B 提交绑定 source tree、suite、环境、命令和 hash 的证据；A 先做便宜完整性检查，只运行合并后新增事实所需的 affected/integration Gate；全量测试由 release/CI 在必要节点集中运行一次。证据失效或风险高时必须重跑。

还澄清了成本概念：重复测试主要增加 wall time 与 compute；Agent 轮询、读取和分析重复输出才直接增加 token。

### Worker、同目录 fork 与其他类型

用户要求用大白话解释。讨论发现此前把不同维度混在一起：worker 是责任主体；fork 是历史来源；同目录/worktree 是 workspace；subagent 是执行身份；ABC 是编排范式。项目决定建立正交 taxonomy，并覆盖 fresh、forked、handoff、rehydrated 历史，同 checkout、managed/permanent worktree、主 checkout、projectless 等环境，以及 explorer、implementer、owner、reviewer、integrator、recovery 等角色。

### 大型 skills 构想

用户希望以此能力建立类似 gstack 或 superpowers 的大型 skills，覆盖多种开发范式、worker 类型、互相管理方法和规范，并具有成熟渐进式披露。这个构想明确超过单个 `SKILL.md`，因此后来升级为工程项目。

### Claude Code 只作为最初参照，随后移出范围

用户曾提到 Claude Code 新发布的 cross-session messaging，希望轻量了解。但随后明确要求：本项目不要做平台无关协议核心、Codex adapter 或 Claude adapter，也不要留下这类预留；如果未来做 Claude Code，应单独做一个专门版本。当前项目因此只保留“曾讨论后排除”的决策，不把 Claude 机制写入设计主体。

### 结构化 prompt 作为初版

用户接受结构化比单纯极长 prompt 更合理，但要求后续逐个做对比测试。当前文档因此只把它标为已接受实验方向，不写成经过证实的优势。

### Token 记录延后

用户同意 token telemetry 先放后续规划，不作为当前必须功能。

### 上下文 baseline

用户建议先联网查看官方和社区介绍/反馈，得到大体 baseline，再规划对照组。当前来源页已纳入研究索引，但任何具体阈值仍待真实 Codex 实验。

### 生命周期建议被采纳

任务保留与归档政策被正式纳入设计。

### 任务线程的上限与 subagent

用户认为任务更像 worker，subagent 更像 tool。讨论接受其管理直觉，同时保留技术修正：二者都是 Agent 执行单元，但任务具有更强的独立身份、历史和工作区治理。

### 混合架构的大白话表达

最终形成通用团队模型：用户是项目 owner；高能力主任务是项目经理兼架构师；长期任务是模块工程师；subagent 是模块工程师临时叫来的助手；integrator 负责合并；CI/Gate 负责机械验收。

### 在执行前先确认理解

用户明确要求在这一阶段不要继续执行实验，先确认全部需求。后续讨论遵守了这一边界，直到用户明确说“开始立项”。

## 第五阶段：从方法论升级为工程项目

用户提出五项最后收敛要求。

1. 不仅要覆盖开发编排范式，还要覆盖 worker 类型、workspace 和 fork/handoff 等环境；规模已经是工程项目。
2. 项目形态必须是 gstack/superpowers 式的大型多-skill 套件，按范式和 worker 类型拆分，并有成熟的渐进式披露。
3. 只专心做 Codex，删除平台无关、adapter 和 Claude 预留。
4. 澄清默认混合架构与多种范式不冲突：前者是角色与治理骨架，后者是阶段工作流；默认开发采用主编排者中心 + 契约并行，集成采用流水线，高风险采用 maker-checker。
5. Agent 专用消息协议不从零发明，优先借鉴或复用 A2A；Git、JSON Schema、OpenAPI、原生测试报告、SARIF 等成熟标准也按需采用。

## 第六阶段：正式立项授权

用户询问是否还有需要确认的事项；若无，则授权：

- 在 `D:/Desktop` 创建项目目录；
- 落地文档系统；
- 将此前全部沟通以文档形式保存；
- 因当前是 projectless 对话，完成后以对应目录创建主任务；
- 将当前上下文 handoff 给该主任务。

在目标名称没有另行指定的情况下，采用说明性名称 `D:\Desktop\Codex多任务工程系统`。立项阶段只建立文档和治理基线，不越权直接实现全部 skills。

## 当前一致结论

- 这是一个正式 Codex 工程项目，不是一段 prompt。
- 多任务的潜力来自独立历史、workspace 隔离、直接通信和可持续角色，但收益不是任务数的线性倍增。
- 默认架构是“强主编排者 + 长期模块任务 + 临时 subagent + 单一集成者 + CI/Gate”。
- 范式按阶段选择，worker 配置由多个正交维度组合。
- Agent 消息短而结构化，真实产物与证据进入 Git/artifact。
- 长测试通过证据绑定和分层 Gate 避免机械重复。
- 模型、thinking、context 阈值和并发甜点区必须用对照实验决定。
- 完成的临时任务归档，长期 owner 保留并可 handoff 轮换。
- 只做 Codex；A2A 采用语义复用，不建设不必要的协议服务。
