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

## 第六阶段结束时的一致结论

- 这是一个正式 Codex 工程项目，不是一段 prompt。
- 多任务的潜力来自独立历史、workspace 隔离、直接通信和可持续角色，但收益不是任务数的线性倍增。
- 默认架构是“强主编排者 + 长期模块任务 + 临时 subagent + 单一集成者 + CI/Gate”。
- 范式按阶段选择，worker 配置由多个正交维度组合。
- Agent 消息短而结构化，真实产物与证据进入 Git/artifact。
- 长测试通过证据绑定和分层 Gate 避免机械重复。
- 模型、thinking、context 阈值和并发甜点区必须用对照实验决定。
- 完成的临时任务归档，长期 owner 保留并可 handoff 轮换。
- 只做 Codex；A2A 采用语义复用，不建设不必要的协议服务。

## 第七阶段：重新明确社区开源与 prior-art 定位

接管主任务后，用户要求在实现前先全面理解最终效果，并调查 Claude Code Agent Teams、Codex 官方能力和社区方案。一次早期总结错误地把问题带向“产品价值、创新性、竞争差异和规模收缩”，用户明确纠正：

- 项目不商业化、不出售，也不以创新点作为成立条件；
- 它是社区开源项目，用于分享功能的使用方法并研究应用上限；
- 调查外部信息是为了知道专业实践已经走到哪里、哪些坑仍未补上；
- oh-my-codex 是规模和实践参照，不是竞品，也不是要求项目刻意做得更轻；
- 长期仍希望尽可能多做有价值的内容，但形态边界是 Codex plugin/skills 能合理承载的范围。

据此完成第一轮 prior-art 与能力上限调查，纳入 Codex、Claude Agent Teams、oh-my-codex、gstack、Superpowers、Gas Town、长时 Agent harness、多 Agent failure 研究和 skills 实证/安全研究。新的项目结论是：

- 外部已经实现大量单点机制，本项目无需声称发明它们；
- 多 Agent 的有效性取决于任务拓扑、状态、verifier 和恢复，而不是数量；
- skills 的边际效用可能为零或为负，必须逐项做 no-skill 与版本兼容评测；
- 本项目价值在于 Codex-only 的复现、组合、教学、证据和失败边界；
- 长期范围可以很大，但每项通过 research、incubating、stable、deprecated 管理；
- pattern 和 worker role 先作为 reference/profile，出现独立触发、行为和验收后再晋升 skill；
- M1 先核验当前 Codex capability contract，再冻结最小 schema 与纵向切片。

本阶段没有实现 skill，也没有运行多任务行为实验；只修改研究、架构、路线、决策与状态文档。

## 当前一致结论

- 这是 Codex-only 的社区开源研究、实践与 skills 工程，不是商业产品，也不需要证明创新性。
- prior art 用于了解已达到的能力上限、复现成熟机制和发现未补坑点，不用于竞品排名或跨平台兼容。
- “强主编排者 + 长期模块任务 + 临时 subagent + 单一 integrator + CI/Gate”仍是默认治理骨架，但是否并行、采用何种拓扑必须由任务可分解性和风险决定。
- 长期可以建设丰富的 skills、profiles、references、scripts、evaluations 和案例；每项按证据独立管理成熟度。
- 任务消息保持短而结构化，真实产物、项目状态和 proof 进入版本化 artifact。
- 首要下一步是 Codex capability contract、最小 schema、固定 benchmark 和 no-skill/single/subagent/multi-task 对照，不是批量生成全部 skills。

## 第八阶段：M1 capability contract 静态 preflight

用户要求继续推进。主任务先固定当前 Windows 环境、Codex AppX/CLI、相关 feature flag、Git 和 repo snapshot，并读取当前 Desktop task 与 session subagent tool schema。这里发现一个必须保留的边界：CLI 把 `multi_agent` 标为 stable 且启用，只证明功能旗标声明；create/fork/message/wait/handoff/archive 的 schema 存在，也不证明具体组合行为。

据此建立 `0.1-draft` capability contract、JSON Schema、只读 PowerShell probe、Python 标准库 validator 和预注册行为实验计划。每个 capability 只允许 `declared_unverified`、`observed`、`contradicted`、`unsupported` 或 `unknown`。随后完成不创建任务的 list/read pilot：当前项目 task 可定位和读取，不存在 ID 显式失败；因此只有 `codex.task.inspect` 成为有条件的 `observed`，其余八项保持 `declared_unverified`。

实验计划加入 native single/Git/native subagent baseline、invalid thread/stale cursor/untracked marker 等负对照、版本与 workspace 泄漏审计、最多 3 个测试任务和 2 个 worktree 的 pilot 预算，以及遇到状态不明或用户修改时 fail closed 的停止规则。

本阶段没有创建、fork、handoff、归档任何任务或运行 subagent，因为这些动作会创建用户可见状态，当前“继续推进”不被解释为明确创建任务授权。下一步需要用户明确授权 disposable test tasks/worktrees 后，才能把相应 claim 从声明推进到行为观测。

## 第九阶段：独立实验场与第一轮多会话行为 Pilot

用户明确授权继续，并要求所有派发会话和 worktree 使用项目外的独立目录，不能污染当前项目 checkout。主任务建立 `D:\Desktop\Codex多任务工程系统实验场`，其中 `source` 是零依赖干净 fixture，两个手工 worktree 位于 `worktrees\worker-a` 和 `worktrees\worker-b`；项目原有 dirty 文档没有被复制进去。

按预注册预算运行两个持久 CLI 会话和一个 same-directory fork，共 3 个会话、2 个 worktree。两个 CLI 会话都在各自 `-C` 目录完成只读 fixture 验证，主任务独立复查后仍保持共同 HEAD 和 clean。worker A 又通过 Desktop direct message 被唤醒，`wait` 收到新 nonce；随后 fork child 在相同 cwd 继承两个已完成父回合并恢复父任务 nonce。

实验同时暴露重要限制：cwd/worktree 隔离并不隔离全局 memory、skills、plugins、MCP 和用户配置；两个极小任务初始 input tokens 分别约 11.3 万和 6.4 万，并发启动时一方出现 system-skills 目录 access-denied。CLI session 也不会自动把新 repo 注册进 Desktop saved projects，所以 managed-worktree create/worktree-fork/handoff 尚不能在用户指定根目录内安全测试。

据此接受 D-018，把 workspace 隔离拆成文件、Git 与运行上下文三层。实验到达预算后停止，没有追加第 4 个会话；三个任务和两个 worktree保留，未归档、未删除。

## 第十阶段：Worker Profile 配对反例

在首轮 pilot 已停止后，另行预注册两个串行会话、零新增 worktree 的 profile 对照。两个会话使用同一 prompt、fixture、sandbox 和默认模型；normal 使用当前配置，minimal 同时使用 `--ignore-user-config` 并关闭 memories、plugins 和 skill_search。

Normal 在约 43 秒内通过，input tokens 为 42,231。Minimal 因用户配置中的执行规则消失，多条只读命令和固定 verifier 被 execution policy 拒绝；Agent 拆分和改写命令后仍无法运行 verifier，约 91 秒、input tokens 219,179。skills loader 仍然扫描了技能，因此该组合既没有达到上下文隔离，也破坏了可执行性。

实验按两会话预算停止，没有追加 flag 组合。接受 D-019：worker context 优化必须保留 auth/rules/sandbox，一次只裁剪一个来源，正确性优先于 token；本结果只否定该 bundle，不外推为“所有 minimal profile 都无效”。

## 第十一阶段：把主线拉回多 Session 工程开发

用户指出前一轮工作的优先级出现偏移：skill/plugin 自动加载目前不是主要问题，profile 实验虽然有观察价值，但测试的大多是已知能力，不能继续占据主线。当前最重要的问题应是：面对稍微大型的工程开发，如何分配和管理多条 session 并行工作。

用户同时给出当前成本政策：实验场 session 使用 `gpt-5.6-luna`，thinking 至少 `high`；暂不使用 Terra 或 Sol 做实验。该要求被记录为阶段性实验默认，而不是模型质量结论；运行时必须取证 effective 配置，不可静默 fallback。

为补足大型工程经验，主任务对 gstack、Superpowers 和 oh-my-codex 的固定源码快照做了第二轮方法级调查：

- gstack 的核心是让单条 session 经过 Think、Plan、Build、Review、Test、Ship、Reflect 的完整阶段；它的多 sprint 并行主要由外部 Conductor 提供 workspace/session 管理；
- Superpowers 通过精确 task brief、接口、worktree、逐任务双重审查和最终 review 控制质量；它只并行真正无共享状态的 domain，计划型写入任务默认不并行实现者；
- oh-my-codex 的 Team 已拥有 DAG、task claim、mailbox、状态、worktree、重分配和 Git 集成证据，但依赖 tmux、CLI、hooks 和专用 runtime，不能原样塞进纯 skills。

据此接受 D-020 至 D-022：

1. M1 改为真实的多 session 工程纵向切片，剩余 capability probe 按需进行；
2. 当前实验固定 Luna + high，不做 Terra/Sol 对照；
3. 第一版组合 gstack 的阶段、Superpowers 的任务/review 纪律和 oh-my-codex 的轻量状态语义，但只依赖 Codex 原生任务工具、Git worktree 和仓库 artifact。

第一批主线入口收敛为 `team-plan`、`team-run`、`team-status`、`team-integrate` 和 `team-finish`。上下文裁剪、长期轮换、完整 lifecycle fault matrix、watchdog/lease 等继续保留为后续研究，不再阻塞第一条闭环。

## 第十二阶段：冻结无效 CLI 试跑并改为 Desktop-first

用户要求 benchmark 不随意选择，应便于客观判定且防止通过搜索目标项目原实现“作弊”。主任务据此选择 OutputGuard 的 JSONL streaming 功能，固定 upstream、公共 scaffold、公开 task/contract 和 sealed evaluator，并预注册 managed-first 与 single 对照、反泄漏规则、成本字段和停止条件。

随后发生的 CLI 混合试跑只启动了 core 与 CLI 两个实现回合。两个 worker 都只交付 partial：Ruff 通过，但真实 worker sandbox 的 Python launcher 无效，pytest/mypy 没有运行；linked-worktree Git metadata 不可写，因而没有 commit；记录器也没有完成 retry manifest。integrator、reviewer、single condition 和 sealed evaluator 均未运行。

用户追问 CLI 与 Codex Desktop 的关系，并最终明确“以后以 Codex Desktop 为准”。因此接受 D-023：后续 worker 只通过 Desktop 原生 task/fork/message/wait/handoff 工具创建和管理；Shell 仍可运行 Git、测试和确定性 helper，CLI 不再是 Agent 执行后端。前述 run 被冻结为 `stopped_invalid_for_comparison`，保留 token、文件状态和失败证据，但不得据此评价单任务或多任务优劣，也不得通过补跑 CLI 把它救成正式结果。

新的只读检查确认，Desktop saved projects 中有主项目，却没有实验场或 OutputGuard benchmark；当前 create/fork schema 也不能指定任意 worktree root。这使“所有实验都位于自定义实验场”和“直接使用 Desktop-managed worktree”产生真实冲突。下一步不自动创建任务，而是等待用户选择：在 Desktop 注册实验场内的干净 checkout 后创建 `local` 只读 task，或明确允许 managed worktree 位于 Desktop 默认位置。两种方案都必须由用户明确要求创建测试任务后才执行。

## 第十三阶段：Desktop local 只读任务通过

用户把实验场内 `outputguard-single` checkout 注册为 Desktop project，并进一步授权：既定范围内能由主编排者直接完成的项目、任务和会话操作应自主完成，不再让用户代发机械指令。由此接受 D-024，但删除、覆盖 dirty 状态、合并、推送、部署、隐藏 evaluator 等高风险或改变实验条件的操作仍不在默认授权内。

主编排者复核 saved project、`codex/outputguard-single`、`d235f59` 和 clean 后，通过 Desktop `local` 创建只读任务 `019ff93b-d3a1-7cf3-8ee5-14a6e0561b65`，未指定 model/thinking。任务在一个回合内确认 cwd、Git root/branch/HEAD、开始与结束 clean、Git common dir 和 Python 3.12.1 无 bytecode导入；主编排者随后用 Desktop read/list 与 Git 独立验收，结果为只读范围 PASS。

该任务没有验证 Git metadata 写入、commit、pytest/mypy/Ruff 或 sealed evaluator，因此不能声称实现环境已完全就绪。下一步应先做独立 write/test qualification，再写首个 task plan，不能从“只读 PASS”直接跳到正式 benchmark。

## 第十四阶段：Desktop qualification 与首个 task plan 冻结

主编排者按预注册 stop rule 进行了四轮 Desktop write/test qualification。第一轮因 worker 在父任务要求停止后自行改写命令继续，整体标为无效；没有因后续 cleanup 成功而翻案。第二轮证明简单 Git index/ref 写入、核验和删除，但系统 Python 缺 pytest。第三轮在固定 lab venv 中得到 `2048 passed, 28 skipped`，随后因 Ruff 参数位置错误停止。第四轮的 Ruff、mypy 和 Git 命令均 exit 0，但 mypy 在 checkout 生成 `.mypy_cache`，所以整体仍为 BLOCKED；缓存被完整移动进 run artifact。第五轮只验证外置 cache，mypy exit 0，19 个 cache 文件全部位于 run 目录，父任务确认仓库 clean，结果 PASS。

基于这些条件化事实，项目冻结了 OutputGuard 四任务 DAG：Core 与 CLI 并行，Integrator 串行接收，Reviewer 只读复核；同时冻结 session plan、roster、task brief、worker report、integration queue schema v0.1、正向样例、缺 proof 负对照和无第三方依赖 validator。正向五类 artifact 与引用 hash 检查通过，负对照按预期非零。

随后进行了三轮离线 package build qualification。第六轮因父任务给出的 PowerShell wrapper 与 cache tree digest 规范有歧义，在 build 前停止；第七轮用确定性 helper 通过边界检查，但 `uv` 读取 `.python-version=3.10` 后因本机没有 3.10 失败；第八轮只增加显式固定 Python 3.12.1 与 `--no-python-downloads`，使用原始 seed 的新 run-local cache，成功生成一份 wheel 与一份 sdist，父任务确认 checkout clean。失败轮次没有翻案。

第九轮先在实验场新建专用 preflight worktree，再通过 saved project `outputguard-single` 创建真实 Desktop local task。任务只运行一个预先锁定 hash 的 helper；helper 验证 task cwd、Git common dir、branch/HEAD/tree/clean 后，只在 assigned worktree 写入并提交 marker。父任务独立确认新 commit `fd81338` 的 parent 是 `d235f59`、只改一个预定文件、两边 clean。Desktop task reader 未暴露底层 tool-call 明细，因此“没有额外只读命令”只能依据任务自报；核心跨-worktree 写入事实不依赖该自报。至此实现前 plumbing 已就绪，但功能、handoff、integration、review、sealed Gate、single baseline 和 skills 效用仍未验证。

## 第十五阶段：真实功能、连续 fail-closed 与最终 recovery lineage

真实 OutputGuard 功能没有按“第一次四任务就全部通过”的理想路径结束。Run02 的集成代码通过实质 public 命令，却被父任务错误的 `dist/.gitignore` boundary helper 判为失败；Run03 修正 helper 后由新的 Reviewer 找到 high R-001。Run04 的 Core repair 逻辑测试已绿，又因为 brief 把 formatter apply 与 check-only Gate 混淆而停止；Run05 因 aggregate diff proof 没定义唯一字节算法停止。Run06 完成 canonical recovery 和完整 public Gate后，Reviewer 继续发现 R-002 数值溢出 ID、R-003 surrogate UTF-8、R-004 decoder `RecursionError` 三个 high。

后续恢复继续保留原状态。Run07 得到可复用的独立 CLI RED commit，但 Core free-form preflight 无证据 false negative；Run08 的 canonical helper 51/51 通过，worker 又正确发现父任务手抄的两个 preregistration hash 错误；Run09 改用 outer manifest，完成一轮 RED 和精确三文件 candidate，却因父任务没有预创建 pytest `--basetemp` 父目录出现 20 个 fixture error。每个 run 都在第一个不满足条件的位置停止，没有访问 sealed evaluator，也没有用后继结果把旧 run 改成 PASS。

Run10 只修复 parent-owned artifact-root 前置条件，复用 Run09 exact candidate，不重跑 RED也不再改源码。Core recovery `59 passed` 后提交 `cde5592`；Integrator 复用 Run07 CLI commit，实际按 CLI → Core 合并，得到 final commit `b67c8e` / tree `41de967`。affected tests `64 passed`，完整 public suite `2093 passed, 28 skipped`，Ruff、mypy、offline build 和最终身份边界通过。fresh Reviewer 关闭 R-002/R-003/R-004，critical/high/medium 为 0，保留 low L-001。父任务随后只运行一次 sealed evaluator，`37 passed in 1.18s`。

sealed 子进程同时在隔离 worktree 留下 29 个 ignored `.pyc`。普通 Git status clean、commit/tree 未变，但目录不能称为完全无残留；主编排者没有静默删除现场。最终表述因此是“一条 exact Desktop recovery lineage 通过 public/review/sealed，并带 evaluator harness cleanliness 限制”，不是“一次四任务无中断成功”或“多任务优于 single”。

## 第十六阶段：从实录反推 skills 架构

用户要求继续推进并用人话汇报。项目据此把实战中最常见的控制面失败直接纳入架构：接受 D-027 的 canonical manifest 与机器派生 projection、D-028 的 append-only proof-carrying recovery、D-029 的 artifact-root 与 ordinary/ignored 分层 Gate。`team-recover` 因多次出现独立触发、输入和验收，从后续构想晋升为首批 incubating 候选。

OutputGuard 自此主要作为 failure corpus 和回归任务，不再承担 skills 泛化价值的唯一证明。下一步先实现 schema/validator v0.2 与 deterministic helpers，再实现主线 skills；冻结后选择第二个未见 benchmark 做主要 no-skill 对照。OutputGuard single 若补做，必须使用不含 lane solution refs/objects 的独立 Git object store，并明确执行顺序已经带来污染风险。

## 第十七阶段：`team-plan` v0.1 从计划变成可执行 skill

用户要求后续实验必须直接围绕目标 skills 形态产生实质进展，并要求所有分配的 Desktop 任务请求 `gpt-5.6-luna` + `max`。主编排者在项目外实验场建立独立 feature worktree，采用 skill TDD：先运行没有 `team-plan` 的 RED 规划任务，再写失败测试、实现 schema/validator/projector，最后用 fresh task 和独立 Reviewer 反复验收。Desktop 没有暴露 effective model/thinking，因此记录只能证明 requested 配置，不能宣称运行时严格生效。

RED baseline 虽然给出了可用的 Core/CLI/Integrator 拆分，却读取了七条历史 solution refs 并使用其他 planning guidance，且只产出自然语言计划，没有 canonical manifest 和机器派生 brief。它因此被判为污染，只进入 failure corpus，不能计算 no-skill 对照收益。代码侧从 9 个预期失败测试起步；由于现有 Python 环境没有 pytest，测试改用标准库 runner，没有安装新依赖。

首个 GREEN 实现随后接受了多轮 fresh review。Reviewer 没有因测试变绿而直接批准，而是依次发现 mutable workspace 指向控制 checkout、Reviewer 拓扑不安全、Windows ownership alias、projection 越界、symlink/祖先子孙重叠、worktree root 逃逸和 lane workspace 物理别名等七类 P1 边界。每个确认问题先加入失败测试再做最小修复，最终达到 19/19，终审对实现 commit `9254d1d` / tree `bd4eb2b` 给出 `approve`。

两次 forward test 分别验证了失败与成功路径：第一次漏写 `objective`，validator 非零并在生成 brief/派发前停止；第二次首次 validate PASS，生成 Core、CLI、Integrator、Reviewer 四份 digest-bound brief。最终 manifest digest 为 `sha256:da72149fd716f7c2284064dda3cc6ff7dd2232a77bbc1fddb06542283a5b4261`，canonical bytes 为 13,511。整个演示没有创建实现 lane、访问 sealed evaluator 或修改 OutputGuard 功能。

`team-plan` v0.1 与实验实录、机器 evidence 最终快进合并到 `main` 功能基线 `17d71bc` / tree `0a2bbebd`。合并后的主目录重新通过 19 项回归、skill validator、真实 forward manifest、三份 capability contract、五类 workflow artifact、负例拒绝、严格 UTF-8、JSON/YAML/schema 和 Markdown 本地链接检查。

当前结论是：项目已经有第一个可执行但仅属 `incubating` 的 skill；它只负责冻结并验证计划，成功后停止，不派发任务。安装后的共享路径、隐式触发、Windows junction、真实 dispatch、第二个 blind benchmark 和公平 skill 边际效用仍未验证。下一入口固定为 `team-run` 的最小 Desktop dispatch/preflight 切片，而不是继续在 OutputGuard 上添加真实功能。

## 第十八阶段：吸收近邻项目的优势并冻结 Codex 原生组合

用户提供一份对 Gas Town、Agent Orchestrator、CCPM、Parallel Code/Conductor、Claude `/batch` 等系统的检索结果，并要求判断哪些机制可以融入“创建多个 Codex 原生线程、统一管理和分发 Prompt”的场景。主任务重新核验官方仓库与文档后纠正了一个范围风险：AO 和 Gas Town 都是带 daemon/adapter/workspace 管理的独立 runtime，直接套在本项目上会形成第二控制面；CCPM 的 Epic 内多个 stream 还可能共享一个 worktree，弱于本项目的写入隔离政策。

用户接受的组合是：任务拆分学习 CCPM，但继续由 canonical manifest 做唯一真相；状态和 Prompt 学习 AO 的持久事实、派生显示状态和可信/不可信分层；集成与恢复学习 Gas Town 的状态机和失败分类，但第一版不复制 batch-then-bisect 自动合并；未来任务可视化学习 Parallel Code/Conductor 的一任务一 workspace 卡片。所有 task、worktree、message、wait 和 handoff 仍使用 Codex 原生入口，不引入外部 Agent CLI launcher、tmux、Beads/Dolt、SQLite/CDC 或跨平台 adapter。该决定记录为 D-032。

## 第十九阶段：`team-run` v0.1 非 live 准备层

用户选择 `team-run` 的 A 范围并明确禁止使用 Superpowers：本轮只能准备 dispatch，不得创建真实 Codex task、worktree、subagent 或消息。主任务在 clean `codex/team-run-v01` 分支上先写标准库行为回归，初始 `0 passed, 9 failed`；随后实现 schema/helper/skill，并增加 Brief symlink 逃逸负例，经历 `9 passed, 1 failed` 后修复到 `10 passed, 0 failed`。最终自审又发现 global `require_clean_start=true` 未覆盖 lane 自己的 false；新增单测先失败，再修复到 `11 passed, 0 failed`。

最终代码 commit `c5ead87` / tree `8589357` 生成 preregistration、空的 cache/dist/logs/pytest roots、parent preflight receipt、每 lane 分层 prompt、dispatch bundle 和 worker-preflight receipt。Prompt 把 manifest/brief/runtime binding 作为可信控制信息，把 Issue、评论和粘贴文本标成不可信背景。输入或 symlink Brief 在 output 创建前失败；global/lane clean policy 统一收紧 dirty workspace；失败保留 parent receipt但没有 dispatch；ignored inventory 与 ordinary status 分开；错误 worker cwd写 failed receipt；所有 run root 和 receipt 都不覆盖。

该切片没有调用 Desktop create/message/wait/handoff，也没有修改 OutputGuard。旧 `team-plan` 19 项、三份 capability snapshot、五类 workflow artifact、skill validator、JSON 和四类新 artifact schema 校验均通过。当前结论只是“非 live 准备层可执行且能 fail closed”，不是实际 dispatch 已完成；下一步先审查该功能分支并实现 read-only `team-status`，再由用户单独授权两条真正独立 lane 的 live pilot。

## 第二十阶段：`team-status` v0.1 只读事实派生

用户继续授权沿 Codex 原生组合方向推进，但没有授权 merge main 或创建真实 task。主任务因此从 clean `codex/team-run-v01@79d8934` 建立 stacked branch `codex/team-status-v01`，只实现 artifact-to-status renderer，不调用 list/read/wait/message，也不修改 Git workspace。

代码先以 11 个缺失入口 RED 开始，随后实现 `status-facts` / `status-snapshot` schema、`init-facts`、`render` 和 skill/reference。自审继续加入 parent preparation failure、facts 路径逃逸、完成时 dirty workspace、dispatch binding 篡改、accepted/archive 依赖语义、矛盾 integration facts与跨-run report/evidence 等负例，最终达到 `18 passed, 0 failed`。

最终规则记录为 D-033：持久 facts 与显示状态严格分离；依赖只认 `acceptance_state=accepted`，不认 `archived` 或 worker 自报；高风险事实优先于 active/idle；Manifest、dispatch、Prompt、Brief、receipt、facts、report/evidence 的 identity/hash 在派生前闭合；当前 run 外的 handoff 文件不能复用。实现 commit `08892eb` / tree `5de613b`。

该结果仍不证明 live task 状态准确。下一步是独立的 Codex-native observation adapter：只读取 list/read/wait 与 Git/artifact并写新 facts，不发送消息。完成后才考虑用户单独授权的两 lane live pilot。

## 第二十一阶段：Team v0.1 离线完整工作流

用户要求“持续推进，完成第一版整个 team”，同时既有边界仍然有效：禁止使用 Superpowers，不为并行而并行，“继续”不自动授权创建真实 Desktop task/worktree/message，也不授权合并 `main`。主任务因此在 stacked `codex/team-v01` 分支上串行完成剩余 workflow，没有创建 subagent 或用户可见任务。

`team-integrate` 首先实现 exact candidate、manifest-order plan、显式授权 Git apply 和显式授权 Gate receipt；自审将 plan/candidate 篡改、所有权、dirty target 和 first-nonzero stop 变成 12 项回归。`team-finish` 把 Gate、review、ordinary/ignored/operation residue、run inventory 和 milestone result 分开，对 archive/cleanup 只输出 `authorized=false` 建议，11 项回归通过。

`team-recover` 实现 clean descendant commit 和 dirty patch + deterministic ZIP 两种 candidate，绑定 immutable predecessor、proof hashes、一个新事实、allowed paths/commands 和命令预算。首轮测试因 argparse 的 subcommand `command` 与 `--command` 目的字段冲突为 3/8；修正后加入候选篡改和越权无半成品回归，最终 10/10。恢复产物始终不创建 successor task 或执行命令。

最后增加统一 `$team` 只读入口。它只读 run 中的 canonical artifact 名称，返回 `next_skill/next_action`、证据 SHA-256 和是否仍需单独授权，所有 task/Git/command/cleanup 授权字段恒为 false。一条临时 Git/worktree 端到端测试从 run preparation 走到 candidate、真实临时合并、离线 Gate、review、audit 和 milestone completion；模拟 thread ID 只是 facts 测试数据，没有调用 Desktop task 工具。

最终八组共 `90 passed, 0 failed`，16 份端到端产物通过 Draft 2020-12 schema，7 个 skill validator、9 份 schema meta-validation、3 份 capability contract 和 5 类历史 workflow artifact 全部通过。代码基线为 `codex/team-v01@e497188` / tree `9930abf`；`main` 仍为 `db3b810`。项目因此可以声称“Team v0.1 repo-local 离线工作流已完成”，但不能声称“真实 Codex 多任务已由套件自动运行”或“已 stable”。下一阶段是安装面、只读 live observer、需用户单独授权的最小 pilot 和第二 blind benchmark。

## 第二十二阶段：可移动 skills-only plugin 打包

用户要求继续。主任务保留“继续不等于安装、创建真实 task 或合并 main”的边界，将 M1.4 的第一步限定为 repo-local 打包与临时隔离验证。审计发现当时 6 个 phase 脚本都以“脚本上两级是仓库根目录”为运行假设，SKILL.md 也使用 `python scripts/...`；单独复制 skill 目录必然失效。

主任务核对官方 OpenAI plugin/skill 文档：plugin 是 ChatGPT/Codex 可安装分发单位，可包含一组 related skills；skill 可携带 scripts/references/assets，仅本地资源的 workflow 无需 MCP server；`.codex-plugin/plugin.json` 用 `./skills/` 指向打包入口。因此接受 D-038：将 Team v0.1 构建为一个 skills-only `codex-team` plugin，不把 7 个 skill 分别复制成七份 runtime，不引入 MCP。

标准库 RED 测试首轮 `0 passed, 6 failed`，全部因 builder 不存在。实现 `build-team-plugin.py` 后，生成包包含 manifest、7 个 skill、bundled `team/scripts`、7 份 runtime schema 和 SHA-256 bundle manifest/self-check。Builder 强制目录名 `codex-team`、父目录已存在、输出不存在，在同父目录 staging 构建成功后 rename。打包时才将 repo-local 命令改写为 `<TEAM_SKILL_DIR>`，源码仍只维护一份。

最终 plugin tests `8 passed, 0 failed`：两次构建 bytes 一致，错误名/覆盖拒绝，篡改被 self-check 捕获，并在源码仓库外实际运行 plan/run/status/router、candidate/merge/Gate/review/audit/finalize 和 dirty recovery。九组全回归 `98 passed, 0 failed`；临时生成包通过官方 plugin validator、7/7 packaged skill validator 和 37-file/7-entrypoint self-check。实现 commit `e4fa221` / tree `62c2820`。

一次检查命令误将构建输出放到 `D:\Desktop\codex-team`，超出了承诺的临时目录范围。主任务立即报告，核对绝对路径和 plugin manifest 后删除该纯生成目录，确认路径不存在。没有 marketplace、全局 skill 或 Codex 配置被改动，但该事故保留为 scope-discipline 记录。

当前结论是“plugin package 可移动且 runtime 可运行”，不是“Codex 已安装并可触发”。实际 marketplace/UI 安装、新会话 discovery、显式/隐式/非触发、升级/卸载和 live task 仍需用户单独授权。

## 第二十三阶段：真实安装、新任务触发与 rollback

用户明确授权创建 repo-scoped marketplace、实际安装/refresh `codex-team`、创建新任务测试 7 个 skill 的发现、显式/隐式/非触发，并卸载回滚。主任务重新核对 OpenAI 官方 plugin 文档和 `plugin-creator` 安装/更新规则，然后记录安装前快照：Codex CLI `0.146.0`，目标 marketplace/source/plugin 不存在，现有 marketplace 只有 primary/curated/chatcut，Git ordinary clean。

仓库新增 `.agents/plugins/marketplace.json` 和 `.gitignore` 生成包规则，marketplace name `codex-team-local`，source `./plugins/codex-team`。该 contract 与第 9 项 plugin test 提交为 `19c8152` / tree `a548cc3`。生成包再次通过 official plugin validator、marketplace-name validator 和 37-file/7-entrypoint self-check。

第一个安装周期中，`codex plugin marketplace add . --json` 返回 `alreadyAdded=false`，`codex plugin add codex-team@codex-team-local --json` 将 `0.1.0` 安装到用户 plugin cache，CLI 显示 `installed, enabled`。安装缓存与 repo source 的 38 份文件 SHA-256 一致，缓存内 self-check 37/7 PASS。本轮未重启 Desktop 进程；新任务已直接拾取 plugin，因此只记录“当前环境新任务边界可拾取”，不声称所有版本无需重启。

三条 managed-worktree 新任务并行执行只读验证。显式任务 `01a03c22-5838-76c3-8e74-1ee6c9666de0` 发现 7 个 `codex-team:*` 名称，显式加载总入口，从安装 cache 运行 self-check，Git 前后 clean。隐式任务 `01a03c22-58e9-75b0-aba6-0b15bb0b1694` 的 prompt 未点名 skill，它选择 `codex-team:team`，因 checkout 无 canonical run artifact 而路由到 planning / `team-plan`，self-check/Git clean 通过。负触发任务 `01a03c22-58db-7311-81c4-27ba1cc399ab` 只返回 README 标题与 clean status，无 bundle output；由于 thread reader 无 skill invocation telemetry，该结果只记为行为相符，不写成内部绝对未加载。

第一次 remove plugin/marketplace 后，版本 cache 消失，projectless thread `01a03c2a-77c8-7552-905e-cbc14c39b855` 从新 skill catalog 返回 `ABSENT`。一条 worktree post-uninstall create 只返回 client ID `89d96e50...`，建立 root `6387`但未在等待窗口得到 thread ID，不计入证据。

为覆盖全部 7 个 phase skill 的显式加载，主任务运行第二个同版重安周期。Projectless thread `01a03c2b-cc74-7a53-b374-9107a629d755` 在一个回合显式读取 7 个 installed SKILL.md，逐个返回独有命令/边界，只运行一次共享 self-check。再次 remove plugin/marketplace 后，最终 projectless thread `01a03c2d-a3ea-7a80-ba20-d6c3842400aa` 再次返回 `ABSENT`。

最终 configured marketplace/plugin 无目标，版本 cache 不存在，`codex-team-local` cache 父目录存在但为空。Repo marketplace 文件和 ignored 生成 source 保留。本轮 6 条可读测试任务保留 idle，没有 archive 授权。`git worktree list` 已无本轮 4 个 managed worktree，但 `4d8c/551e/fdba/6387` 容器目录仍存在且为空，本轮不手工删除。

项目因此接受 D-039：当前环境中 repo marketplace 注册、同版重安、新任务 7-skill discovery/显式加载、单次隐式路由和卸载后不发现均已观察。长期触发准确率、旧任务热刷新、版本升级/cachebuster、真实 worker dispatch/handoff/archive 和第二 benchmark 仍未完成，成熟度不晋升。
