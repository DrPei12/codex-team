# 13. 决策日志

这里记录已经接受的项目级决策。新决策只能通过新增记录替代旧决策，不静默改写历史。

## D-001：建立正式工程项目

- 日期：2026-08-09
- 状态：Accepted
- 决策：在 `D:\Desktop\Codex多任务工程系统` 建立独立 Git 项目和主任务。
- 原因：范围已经超过单份提示词或单个 skill，包含原理、范式、worker taxonomy、协议、评测和生命周期治理。

## D-002：只面向 Codex

- 日期：2026-08-09
- 状态：Accepted
- 决策：不设计平台无关核心，不加入 Codex/Claude adapter，也不做 Claude Code 预留。
- 原因：专注把 Codex 当前能力做深；未来 Claude Code 版本若有必要，单独立项。

## D-003：大型多-skill 套件

- 日期：2026-08-09
- 状态：Accepted
- 决策：产品形态参考 gstack/superpowers 的多-skill 工程，不做单一巨型 `SKILL.md`；按用户入口、编排范式和 worker 角色组织，并使用渐进式披露。

## D-004：范式与 worker 正交

- 日期：2026-08-09
- 状态：Accepted
- 决策：编排范式、角色、执行身份、历史来源、workspace、生命周期和模型策略分别建模，再按任务组合。
- 原因：`worker`、同目录 fork、worktree 和 ABC 流水线不是同一类别。

## D-005：默认混合架构

- 日期：2026-08-09
- 状态：Accepted
- 决策：默认由高能力主编排者维护目标和架构；长期任务作为模块 owner；subagent 处理局部短任务；单一 integrator 接收；CI/Gate 提供机械证据。
- 补充：默认开发流是 hub-and-spoke + contract-parallel，默认集成流是 stage pipeline，高风险点插入 maker-checker。项目不同阶段可以切换范式。

## D-006：A2A 语义复用而非重造协议

- 日期：2026-08-09
- 状态：Accepted
- 决策：复用 A2A 的 Task、Message、Part、Artifact、状态和上下文语义；第一版沿用 Codex 原生消息和 Git/artifact，不搭建完整 A2A 网络服务。

## D-007：Artifact-first 和 proof-carrying handoff

- 日期：2026-08-09
- 状态：Accepted
- 决策：消息只承载控制信息和摘要；大型内容与证据进入 artifact。昂贵测试结果绑定 revision、suite 和环境，接收方先验证证据，再运行新事实所需的 affected/integration Gate。

## D-008：模型分层先做方案，后做对照

- 日期：2026-08-09
- 状态：Accepted
- 决策：采用结构化 brief + 高能力编排者 + 按难度选择 worker 模型 + 升级机制作为初版假设。具体模型名、thinking 和阈值必须实验决定。

## D-009：Token telemetry 延后但不忽略

- 日期：2026-08-09
- 状态：Accepted
- 决策：Phase 0 不因缺少 token 记录而停滞；评测 schema 预留 token/成本字段，后续通过产品 telemetry 或外部工具记录。

## D-010：任务完成后的保留政策

- 日期：2026-08-09
- 状态：Accepted
- 决策：主编排者和活动 component owner 保留；一次性任务在产物被接收后归档；上下文老化时通过 artifact + handoff 轮换；任务归档与 worktree 删除分开处理。

## D-011：任务与 subagent 采用混合模式

- 日期：2026-08-09
- 状态：Accepted
- 决策：不把两者做成互斥方案。任务承担长期身份、历史、workspace 和交接；subagent 承担父任务内部短工作。

## D-012：先文档，后实现

- 日期：2026-08-09
- 状态：Accepted
- 决策：立项阶段先保存完整讨论、形成设计和评测基线；未确认第一阶段计划前不直接生成全部 skills。

## D-013：社区开源研究与实践定位

- 日期：2026-08-10
- 状态：Accepted
- 决策：本项目是 Codex-only 的社区开源研究、使用方法与 skills 工程，不是商业产品，不做市场验证，也不以创新性或竞争差异作为成立条件。
- 原因：目标是调查专业实践已达到的上限，复现、组合并分享有价值的方法，同时公开失败边界。
- 替代说明：D-003 中“产品形态”只保留为“交付形态”的历史表述，不再解释为商业产品定位。

## D-014：Prior art 是研究基线，不是兼容目标或竞争对象

- 日期：2026-08-10
- 状态：Accepted
- 决策：系统调查 Codex、Claude Agent Teams、oh-my-codex、gstack、Superpowers、Gas Town 与相关研究；可以复现其机制，但本项目仍只实现 Codex，不建设 Claude adapter，也不做竞品排名。
- 原因：外部实践已经覆盖大量单点机制，忽略它们会重复踩坑；把它们当成需要击败的产品又会错误裁剪社区研究范围。

## D-015：广泛建设与证据晋升并行

- 日期：2026-08-10
- 状态：Accepted
- 决策：长期允许建设与大型社区套件同量级的丰富 skills、references、profiles、scripts、evaluations 和案例；每项按 `research → incubating → stable → deprecated` 管理。
- 补充：编排 pattern 和 worker role 先作为 reference/profile；只有具备独立触发、独立行为和独立验收时才晋升 skill。
- 原因：这不会缩小范围，而是防止把知识分类、目录数量或外部文案误报成稳定能力。

## D-016：先核验 Codex capability，再冻结纵向切片

- 日期：2026-08-10
- 状态：Accepted
- 决策：M1 先实测当前 Codex create/fork/message/wait/handoff/archive/worktree/subagent 组合，形成 capability contract；随后冻结最小 schema 和 benchmark，并对首批 workflow 做 no-skill/single/subagent/multi-task 成对评测。
- 原因：产品原语和 skills 边际效用都会随版本、环境与任务变化，不能直接由官方介绍、社区实现或论文数字推成默认常数。

## D-017：Capability 声明与行为观测分层

- 日期：2026-08-11
- 状态：Accepted
- 决策：每条 Codex capability 使用 `declared_unverified`、`observed`、`contradicted`、`unsupported` 或 `unknown`，并绑定版本、环境、条件和 evidence；禁止使用不带条件的 `verified`。
- 约束：CLI feature flag、官方说明和当前 tool schema 只能支持 `declared_unverified`；`observed` 必须有当前行为 run 的 tool input/output、任务/Git before/after 与 cleanup evidence。历史实验只能支持或限制历史条件下的 claim，不能自动升级当前环境。
- 原因：产品入口存在与组合语义可靠是不同事实；不分层会让 skill 把文档声明或一次旧 smoke test误写成长期保证。
- 当前实现：`schemas/capability-contract.schema.json` 是 `0.1-draft`，静态 snapshot 已通过语义 validator；行为实验完成前不冻结为 stable contract。

## D-018：Workspace 隔离必须分成文件、Git 与运行上下文三层

- 日期：2026-08-12
- 状态：Accepted
- 决策：worker card、preflight 和 evidence 分别记录 `filesystem_boundary`、`git_boundary` 与 `runtime_context_boundary`；不再把独立 cwd/worktree 表述为完整隔离。
- 证据：2026-08-12 pilot 中，两个 `codex exec -C` 会话正确绑定独立 worktree，但仍自动加载全局 memory、skills、plugins 和用户配置，并在并发启动时出现一次 system-skills 目录 access-denied。
- 对 skills 的影响：`team-capability-audit` 采集三层状态，`team-run` 验证允许根目录和上下文策略，`team-benchmark` 增加 normal/minimal profile 对照。worker bootstrap 先作为共享 profile/helper，不因这次发现立即新增 skill 名称。
- 限制：pilot 只运行一次并发启动；告警的稳定复现率和因果来源仍待对照实验。

## D-019：Worker 上下文裁剪不得删除已验证执行规则

- 日期：2026-08-12
- 状态：Accepted
- 决策：不采用 `--ignore-user-config --disable memories --disable plugins --disable skill_search` 作为默认 worker bootstrap。上下文优化必须保留 auth、execution policy、sandbox 和项目规则，一次只改变一个来源，并先通过固定 correctness verifier。
- 证据：相同 prompt/fixture 的串行配对中，normal profile 通过；该 minimal bundle 的 verifier 被 execution policy 拒绝，skills 仍被发现，总 input tokens 约为 normal 的 5.19 倍，耗时约 2.11 倍。
- 限制：单对样本且四个设置同时变化；这只否定该 bundle，不证明不存在安全有效的 curated profile。

## D-020：M1 主线改为真实多 Session 工程闭环

- 日期：2026-08-12
- 状态：Accepted
- 决策：M1 首要目标改为“面向中等偏大工程，如何拆分、分配和管理多条 Codex session 并安全集成”。第一条纵向切片覆盖 `team-plan -> team-run -> team-status -> team-integrate -> team-finish`，用真实功能而不是原语 smoke test验收。
- 顺序修订：D-016 中“先完成 capability contract 再冻结纵向切片”的顺序被本决策替代。已有 capability contract/evidence 继续保留；只有 workflow 真正依赖某个未知语义时，才做最小、按需 probe。
- 原因：前一轮 create/message/fork/profile 实验已经足以确认基础组合方向并暴露若干限制，继续穷举已知功能的边际价值低于直接检验任务拆分、所有权、review、等待和集成。

## D-021：当前实验 Session 固定 Luna + High

- 日期：2026-08-12
- 状态：Superseded for future Desktop task creation by D-023；历史 CLI 实验记录不变
- 决策：实验场新建的执行、审查和集成 session 默认使用 `gpt-5.6-luna` 与 `high` thinking；只有明确任务证据需要时才提高到当前客户端支持的更高 thinking。当前实验不使用 `gpt-5.6-terra` 或 `gpt-5.6-sol`。
- 约束：run 必须记录 requested/effective model 与 thinking；配置不可用时停止并报告，不静默回退到 Terra/Sol。
- 原因：先用经济模型验证工程方法，控制成本并减少模型差异混杂。本决策是阶段性实验政策，不是模型质量排名，也不废除以后跨模型分层研究。
- 后续状态：该策略只解释 2026-08-12 已发生的 CLI run。Desktop 新建任务遵守工具的显式授权规则：用户没有明确指定模型或 thinking 时不代为覆盖；可观测不到的 effective 值记为 `unknown`。

## D-022：组合三套 Prior Art 的方法，不复制其 Runtime

- 日期：2026-08-12
- 状态：Accepted
- 决策：第一版采用 gstack 的阶段化 sprint、Superpowers 的 task brief/worktree/review 纪律，以及 oh-my-codex 的 DAG、owner、ACK、状态和集成语义；执行层只使用 Codex 原生 task/subagent 工具、Git worktree 和仓库 artifact。
- 非目标：不为第一版实现 tmux、daemon、watchdog、自动 heartbeat、自建 mailbox server 或跨平台 adapter。
- 原因：gstack 的多 sprint 依赖外部 session manager；Superpowers 只并行真正独立的 domain；oh-my-codex 的耐久 Team 已是专用 runtime。照抄后者会把本项目从 skills 工程扩成另一套编排平台。

## D-023：以 Codex Desktop 作为权威执行界面

- 日期：2026-08-12
- 状态：Accepted
- 决策：本项目的 worker task、fork、消息、等待、handoff 和 Desktop-managed worktree 只通过 Codex Desktop 原生任务工具创建和管理。Shell/Git/Python 仍可在当前任务内用于确定性检查、测试、hash 和 artifact 生成，但 `codex exec` 不再作为 benchmark worker、编排后端或 Desktop 的替代入口。
- 证据边界：既有 CLI pilot 继续作为“CLI 在当时条件下发生过什么”的历史证据，不能升级为 Desktop capability，也不能与 Desktop run 合并计算结果。2026-08-12 OutputGuard CLI 混合试跑因执行面不符、Python/Git preflight 失败而停止；未运行 single、integrator、reviewer 或隐藏 evaluator，因此没有多任务对照结论。
- Workspace 约束：实验仍应留在 `D:\Desktop\Codex多任务工程系统实验场`。当前 Desktop `list_projects` 未列出实验场或 OutputGuard benchmark；当前 create/fork schema 也没有任意 worktree root 参数。二者冲突时必须停止，由用户选择“把实验场 checkout 注册为 Desktop project 后使用 local task”，或明确允许 Desktop-managed worktree 位于实验场外；不得静默退回 CLI。
- 模型约束：新建 Desktop 任务仅在用户明确指定时覆盖 model/thinking，否则使用用户配置的默认值。run 仍记录 requested/effective 字段；产品未暴露的值保持 `unknown`。

## D-024：既定范围内的可恢复 Desktop 操作由主编排者自主执行

- 日期：2026-08-12
- 状态：Accepted
- 用户授权：对于已经接受的项目计划中，主编排者能通过当前工具直接完成的低风险、可恢复操作，例如选择已注册项目、创建任务、发送消息、等待、读取状态和建立明确边界的实验 workspace，不再要求用户手工代发同一句指令。
- 约束：自主执行不扩大任务范围，也不自动授权删除 worktree、覆盖未提交修改、合并、推送、部署、联网写入、访问隐藏 evaluator 或其他难恢复操作。目标路径/身份不唯一、会触碰未知 dirty 状态、产品要求用户 approval 或选择会实质改变实验条件时仍须停止。
- 对 skills 的影响：`team-run` 和 `team-status` 默认执行计划内机械协调并报告结果；只有材料选择、风险接受、不可逆 cleanup 或 benchmark 条件变化才升级给用户。

## D-025：首个 Desktop 纵向切片采用四任务 DAG 与 permanent worktree

- 日期：2026-08-13
- 状态：Accepted
- 决策：首个 OutputGuard run 冻结为 Core、CLI、Integrator、Reviewer 四条用户可见 Desktop task。Core 与 CLI 基于冻结 contract 并行；单一 Integrator 按 Core → CLI 顺序接收；Reviewer 在 integration tree 上只读审查。主编排者属于控制面，不计入 lane。
- Workspace：所有实际 worktree、run artifact、cache 和 dist 仍位于 `D:\Desktop\Codex多任务工程系统实验场`。Desktop saved project `outputguard-single` 只作为 local task 的控制入口，task brief 指定的 permanent worktree 才是允许写入目录。每条真实 task 必须先自证 common dir、branch、HEAD、clean 与定向执行能力，父任务独立复核；失败时停，不写 hub checkout、不用 CLI fallback。
- 协议：只冻结 session plan、roster、task brief、worker report、integration queue 五类 artifact schema v0.1。真实 handoff 必须有 Git identity、所有权和命令证据；缺 proof 的 completed report 由 validator 拒绝。
- 证据边界：D-025 作出时，Desktop qualification 只覆盖简单 Git index/ref、完整 public pytest、Ruff 和 mypy 外置缓存。后续 Qualification 08 与 09 已分别补齐固定条件下的离线 package build，以及由真实 Desktop local task 在 assigned permanent worktree 创建 marker-only commit 的能力；功能实现、真实 handoff/integration/review、sealed evaluator 和多任务收益仍未验证。

## D-026：实现前 Desktop plumbing 资格检查通过后才启动真实 lane

- 日期：2026-08-13
- 状态：Accepted
- 决策：首轮 lane 使用已资格化的固定 Python、`uv --offline --no-python-downloads`、run-local cache/dist，以及“saved project 作为 task 控制入口、brief 指定 permanent worktree 作为写入目录”的机制。每条写入 task 仍须在变更前验证 cwd/common-dir/branch/HEAD/clean，不能只引用预检结果。
- 证据：Qualification 08 生成一份 wheel 与一份 sdist并保持 checkout clean；Qualification 09 的 Desktop task 在专用 assigned worktree 提交了唯一 marker 文件 `fd81338`，父任务确认其 parent 为 `d235f59`、hub 未变化且两边 clean。
- 限制：Qualification 08 未安装产物、未做网络抓包；Qualification 09 由固定 helper 执行 Git 操作，Desktop thread reader 没有暴露底层 tool-call 明细。它们证明当前记录条件下的 plumbing 可行，不证明 Desktop-managed worktree、自由命令路由、功能正确性或长期可靠性。

## D-027：运行身份采用单一 canonical manifest 和机器派生 projection

- 日期：2026-08-15
- 状态：Accepted
- 决策：revision、tree、路径、文件 bytes/hash、命令、预算和授权只由一个 canonical run manifest 拥有。task brief、preregistration、freeze、handoff 和 acceptance 中的重复字段必须由 deterministic helper 生成或交叉验证，不允许人工补全 hash。聚合 proof 必须冻结唯一的字节生成命令、参数、path order、编码和换行规则。
- 原因：Run05 因“diff hash”算法不明确正确停止；Run08 的 canonical helper 51/51 通过后，worker 又发现父任务手抄的两个 preregistration hash 与 manifest 冲突。两次失败都来自控制面重复表达同一身份，而不是实现代码。
- 对 skills 的影响：schema/validator v0.2 和 manifest generator 先于完整入口 skill；`team-plan` 产出 canonical manifest，`team-run` 只能消费机器派生的 brief/preflight。任何 cross-file identity mismatch 必须在创建 worker 前 fail closed。

## D-028：恢复运行保持历史追加，`team-recover` 晋升首批候选

- 日期：2026-08-15
- 状态：Accepted
- 决策：失败 run 的 status、evidence 和 worktree 现场不被后继结果改写。恢复必须创建新的 run ID，绑定 predecessor、精确 candidate bytes/Git identity/命令、已经成立的 proof、唯一待建立的新事实和独立预算；只运行新事实需要的 Gate。`team-recover` 由后续候选晋升为首批 incubating workflow 候选。
- 原因：Run02–Run10 的恢复链多次需要复用未受阻塞影响的事实。Run10 复用 Run07 已验收 CLI commit 和 Run09 精确 candidate，没有重跑 Run09 RED，也没有由父任务重复 Integrator 的完整 public Gate，最终仍保持 Run08/Run09 为原始 blocked 状态。
- 限制：一次成功恢复链不证明长期可靠率。Run09 RED 缺少原始 pytest log，仍必须作为证据限制保留；proof-carrying 不等于无条件相信 worker 自报。

## D-029：Gate 同时管理目录前置条件与多层 cleanliness

- 日期：2026-08-15
- 状态：Accepted
- 决策：task 创建前必须创建并验证声明的 artifact/test/cache/dist root 初始状态；预授权的 formatter apply 等 mutation step 与 check-only Gate 分开。结束验收分别报告 ordinary tracked status、untracked、ignored、Git operation residue 和 run-local artifact，不把普通 `git status` clean 等同于完全无残留，也不静默清理证据现场。
- 原因：Run09 因父任务没有预创建 `--basetemp` 的父目录而产生 20 个 fixture `FileNotFoundError`；Run10 sealed 功能 37/37 通过且普通状态 clean，但 evaluator 子进程留下 29 个 ignored `.pyc`。两者都说明运行目录条件和产品正确性必须分开取证。
- 对 skills 的影响：`team-run` 负责 root precondition receipt；`team-finish` 负责 ordinary/untracked/ignored/operation-residue receipt。清理是单独授权的生命周期动作，不是为了让报告好看而自动执行。
