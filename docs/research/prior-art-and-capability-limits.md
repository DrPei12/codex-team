# Prior art 与能力上限调查

> 快照日期：2026-08-10  
> 状态：第一轮调研完成；结论用于调整研究路线和 skills 信息架构，不代表相关产品的永久能力保证。

## 1. 调查问题

本轮不做市场分析、产品竞争或创新性证明。要回答的是：

1. Codex、Claude Code 和社区工程已经把多任务、多 Agent、长时运行与 skills 推到什么程度；
2. 哪些能力由官方产品直接提供，哪些来自社区 workflow/runtime，哪些只在研究或高成本实验中出现；
3. 已知失败模式和未补上的坑是什么；
4. 一个 Codex-only 的社区开源 skills 项目，应该复现、组合、验证和公开哪些实践；
5. 哪些候选能力应成为 skill，哪些更适合做共享协议、agent profile、reference、script 或 evaluation。

目标决策是修订 Phase 1 研究路线与 skills 架构，而不是决定项目是否值得商业化。

## 2. 范围与方法

### 2.1 纳入范围

- 官方原生能力：Codex App/CLI 的任务、subagent、worktree、handoff、skills；Claude Code Agent Teams、subagent 和 worktree。
- 社区开源实践：oh-my-codex、gstack、Superpowers、Gas Town。
- 能力上限实验：长时自主开发、多 Agent 并行开发、结构化 handoff 与 evaluator 分离。
- 反面证据：多 Agent 协调失败、任务拓扑限制、skills 边际效用、版本漂移、维护和供应链风险。

### 2.2 排除范围

- 不把 star、营销文案或并发展示当作能力证据。
- 不把 Claude Code 适配纳入本项目实现范围；Claude 只作为 prior art。
- 不系统综述 AutoGen、LangGraph、MetaGPT 等通用 Agent 框架；它们不是本轮 Codex skills 架构决策的最近邻。
- 不根据单篇论文或单次高成本演示固定并发数、上下文阈值、模型档位或节省比例。
- 不把搜索中未找到官方说明解释为“产品一定没有该能力”。

### 2.3 来源与证据口径

来源优先级为：官方产品文档与当前工具 schema → 官方仓库/固定 revision → 原作者工程报告 → 论文与开放评测仓库 → issue/社区讨论。最后一类只用于发现待复现的失败线索。

本页使用以下关系：

- `direct`：来源直接陈述或仓库直接实现；
- `context`：可约束设计，但不是对本项目的直接证明；
- `contradicts`：反驳过强主张；
- `inference`：由多项证据推导，仍需本项目验证；
- `unverified`：当前只有线索或本地 schema 观察，尚未做行为实验。

## 3. 先给结论

### 3.1 外部已经走得很远

外部实践已经覆盖了本项目最初设想的大部分单点机制：

- Claude Agent Teams 已把 lead、独立 teammate 上下文、共享任务表、依赖、自领取锁、直接消息、hooks 和 cleanup 做成原生实验功能；
- Codex 官方已经提供并行任务、worktree、subagent、skills 和 App 内任务管理；当前本地工具 schema 还暴露了 create/fork/read/wait/message/handoff/archive 等组合原语；
- oh-my-codex 已形成围绕计划、team、持久 goal/ledger、checkpoint、review 和 QA 的大规模 Codex workflow 层；
- gstack 与 Superpowers 展示了如何把设计、计划、实现、审查、测试、交付、恢复和 skill 自身测试做成可触发的流程；
- Gas Town 把持久任务账本、角色、worktree、mail、handoff、watchdog、merge queue、scheduler 和 telemetry 做到了独立 orchestration runtime 的规模；
- Anthropic 的 C 编译器实验展示了 16 个 Agent、近 2,000 个 session、跨两周和约 100,000 行代码的压力上限。

因此，本项目不应声称这些基本组件是新发明。

### 3.2 外部也没有得到“多 Agent 越多越好”

证据一致指向一个条件结论：收益首先由任务拓扑、验证 oracle 和状态设计决定，而不是由 Agent 数量决定。

- Claude 官方明确建议只在可独立并行的工作上使用 Agent Teams，并把顺序任务、同文件编辑和高依赖工作列为较差场景。
- C 编译器实验在大量独立测试失败时容易并行；进入 Linux kernel 的单一串行瓶颈后，16 个 Agent 会撞到同一问题并互相覆盖。
- `Towards a Science of Scaling Agent Systems` 在固定预算、四类 benchmark 的条件下观察到：顺序推理中所有多 Agent 拓扑都退化，任务可并行性和协调开销决定最优拓扑。
- `Why Do Multi-Agent LLM Systems Fail?` 把失败归纳为 specification/system design、inter-agent misalignment、verification/termination 三大类，说明更详细的角色描述本身不足以消除问题。

### 3.3 skills 的价值必须逐项测，不能靠目录规模推断

`SWE-Skills-Bench` 对 49 个公开 skills 做成对、有确定性验收的评测；论文报告 39/49 没有 pass-rate 提升，平均提升仅 1.2%，但少数专用 skill 可提升最多 30%，版本不匹配的 skill 还会降低表现。这个结果不等于“skills 没价值”，而是说明：

- 专用、适配当前环境、能改变执行行为的 skill 更可能有效；
- 泛化过度、陈旧或只增加上下文的 skill 可能是负资产；
- 每个 skill 都需要 no-skill baseline、版本兼容信息、token/时间和失败模式。

### 3.4 本项目仍然有明确价值

价值不在于“别人没有”，而在于把分散实践转化为 Codex-only、可复现、可评测、可安装和可审计的社区方法：

1. 给出 Codex 当前原语的实测能力矩阵，而不是把产品文案当契约；
2. 给出任务拓扑 → task/subagent → workspace → handoff → Gate 的选择方法；
3. 给出结构化 artifact、证据复用、恢复和生命周期的可运行样例；
4. 对每个 skill 做有/无 skill 的边际效用评测；
5. 公开失败案例、版本漂移、Windows/App/CLI 差异和能力上限；
6. 在社区已有方案之上复现与组合，不以创新性作为收录门槛。

## 4. 系统与来源矩阵

| 对象 | 已直接展示的能力 | 仍未由该来源证明 | 对本项目的含义 |
|---|---|---|---|
| Codex App | 多任务并行、独立 thread、worktree、skills、automation；当前本地 schema 有 create/fork/read/wait/message/handoff/archive | 没找到一份官方文档把这些原语定义成与 Claude Teams 等价的共享 team runtime；本地 schema 也不是稳定行为保证 | 在真实 workflow 依赖未知语义时做最小 capability probe；不要伪造产品级 `team` 概念 |
| Codex subagents | 独立上下文、并行委派、自定义 agent/model/instructions；成本高于单 Agent | 与用户可见长期 task 的恢复、归档、workspace 和消息语义并不等同 | 用于父任务内部短工作；必须和长期 task 做对照 |
| Claude Agent Teams | lead、teammate、共享任务表、依赖、锁、直接消息、hooks、用户直达 teammate | 实验功能；无 in-process resume、无嵌套 team、lead 固定、状态可能滞后、cleanup/权限有局限；teammate 默认不做 worktree 隔离 | 作为 native team UX 和 lifecycle 的高水位 prior art，不进入兼容范围 |
| oh-my-codex | Codex workflow、team、持久 goal/ledger、checkpoint、model routing、review/QA | 仓库能力多且更新快；不能仅从文档推断所有组合都稳定或适合 Codex App/Windows | 作为 skills 规模与组合方式的直接参照，选择性复现并做自己的验收 |
| gstack | 端到端 sprint、专业化 skills、context save/restore、health、benchmark、browser/ship workflow | 其“10–15 parallel sprints”是作者实践描述，不是跨项目阈值 | 学习 workflow chaining、恢复和 skill benchmark，不照搬产品/角色语言 |
| Superpowers | 强制式方法论、worktree、TDD、逐任务 subagent、两阶段 review、skill triggering 和 transcript 测试 | 跨 harness 支持会引入适配复杂度；本项目不需要复制平台无关层 | 学习 skill 自身的触发测试、行为测试和 consent 边界 |
| Gas Town | git-backed ledger、角色、mail、handoff、watchdog、merge queue、scheduler、OTel、Windows minimal mode | 这是 runtime/CLI/daemon 级系统，不是纯 skills；完整 tmux workflow 在 Windows 仍建议 WSL | 研究它的 durable state、recovery 和 integration 机制，但不把本项目扩成 daemon 平台 |
| Anthropic 长时 harness | structured feature list/progress、context reset + handoff、planner/generator/evaluator、强 verifier | 特定模型、任务和高成本环境；不能推导日常工程 ROI | 把 handoff、fresh context、独立 evaluator 和 verifier 质量列为核心实验轴 |
| 多 Agent 研究 | 协调开销、拓扑依赖、错误放大、验证/终止失败的可测证据 | benchmark 不等于 Codex 软件工程；具体数值不能直接迁移 | 先测任务拓扑，再决定是否并行和用何种拓扑 |
| skills 研究 | 边际效用、版本冲突、复制式复用、维护与供应链风险 | 研究很新，生态和工具仍快速变化 | 建立 skill maturity、compatibility、A/B、provenance 和安全检查 |

## 5. 能力层级与真实上限

### L0：产品原语

任务、subagent、worktree、消息、等待、handoff、skills、Git 和测试工具已经存在。这里的上限是“能够被调用”，不是“组合后可靠”。

### L1：可复用 workflow

gstack、Superpowers 和 oh-my-codex 已证明，一个社区项目可以用几十个 skills、references、scripts 和状态文件覆盖从澄清到交付的完整流程。其主要难点转为：

- 正确触发与非触发；
- skill 之间的 handoff；
- 上下文预算与渐进式披露；
- 版本兼容；
- 对行为而非文案做回归测试。

本项目的主要交付面位于这一层。

### L2：持久 orchestration

Claude Teams 和 Gas Town 分别从产品内与独立 runtime 两条路线展示了共享 task state、mail、lifecycle、recovery、merge queue 和监控。纯 skills 可以复用其协议与操作法，但无法可靠替代所有后台 daemon、锁、scheduler 或 UI 状态。

本项目应研究并提供轻量脚本/schema/ledger，但不把自己改造成 Gas Town 式常驻平台。

### L3：长时压力实验

多周、多千 session 和高成本 Agent team 已经能产出大型工程 artifact，但其成功依赖高质量 test oracle、可并行 failure surface、持续集成、进度文件和大量计算。它证明“可能做到”，不证明“默认高效、质量等同专家或适合普通社区用户”。

本项目应复现机制级小实验，而不是复刻成本规模。

## 6. Claim-level evidence ledger

| Claim ID | 主张 | 关系 | Evidence | 条件与边界 |
|---|---|---|---|---|
| C01 | 多 Agent 收益由任务可分解性和依赖拓扑决定 | direct + context | E05, E07, E14 | 具体收益需在 Codex 软件工程任务重测 |
| C02 | 顺序、高耦合、同文件工作可能因协调开销而退化 | direct + contradicts | E05, E07, E14 | 不代表所有顺序任务必然退化 |
| C03 | worktree 隔离文件状态，但不消除语义、契约、数据库、端口或外部服务冲突 | inference | E03, E06, E13 | 需用共享资源故障注入验证 |
| C04 | 独立上下文减少主上下文污染，但增加 briefing、重定向和 token 成本 | direct + inference | E02, E05, E08 | 成本与模型、任务长度有关 |
| C05 | shared task/mailbox/ledger 可改善可见性，也会引入 stale state、resume、cleanup 和锁问题 | direct | E05, E13 | 两个实现路线不同，不能互换字段 |
| C06 | 高质量 verifier 是长时自主与多 Agent 工作的硬上限之一 | direct | E07, E08, E09 | 主观质量仍需独立 evaluator/人工判断 |
| C07 | proof/handoff 必须绑定 revision、环境和可复现命令，才能安全复用昂贵结果 | inference | E07, E08, E09 | 本项目 schema 与失效规则尚待实验 |
| C08 | skills 的平均收益不保证为正，专用性和版本匹配很关键 | direct + contradicts | E16 | 单一 benchmark/模型不能外推全部 Codex skills |
| C09 | skill 是需要维护、兼容和 provenance 的软件 artifact，不只是 prompt 文本 | direct + context | E12, E17 | 维护模式来自生态样本，不是强制规范 |
| C10 | 外部 skill 安装形成新的供应链与权限风险 | direct + context | E18, E19 | 两项研究很新；本项目需独立威胁模型 |
| C11 | 社区已经能把 plan、team、ledger、review、QA、recovery 组合成大规模 skills 工程 | direct | E10, E11, E12 | 文档存在不等于每条路径已被独立验证 |
| C12 | Codex 当前具备组成多任务工程流的原语，但组合语义与版本边界仍需实测 | direct + unverified | E01, E02, E03, E04 | E04 是 2026-08-10 本地工具 schema 观察 |
| C13 | 本项目的合理价值是 Codex-specific 复现、组合、评测和教学，而非创新声明 | inference | E01–E19 | 属于项目定位决策，不是外部事实 |
| C14 | 广泛收录与分阶段成熟度并不冲突 | inference | E10–E19 | 需要 maturity policy 避免把实验项冒充 stable |

## 7. Evidence catalog

| Evidence ID | 类型 | 来源 | 可支持内容 | 限制 |
|---|---|---|---|---|
| E01 | 官方产品 | [OpenAI — Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/) | 并行 threads、worktree、skills、automation | 产品介绍，不是完整协议 |
| E02 | 官方产品 | [OpenAI — Codex subagents](https://developers.openai.com/codex/subagents) | subagent 可用性、独立工作、额外 token | 版本会变化 |
| E03 | 官方产品 | [OpenAI — Codex worktrees](https://developers.openai.com/codex/environments/git-worktrees) | Local/Worktree/Handoff、detached HEAD、managed/permanent worktree | 不证明语义冲突被解决 |
| E04 | 本地观察 | 2026-08-10 当前 Codex App tool schema | create/fork/list/read/wait/message/handoff/archive 等工具存在 | 尚未执行行为矩阵；不是公开稳定契约 |
| E05 | 官方产品 | [Anthropic — Agent Teams](https://code.claude.com/docs/en/agent-teams) | shared tasks、mailbox、locking、hooks、成本与限制 | Claude only、experimental |
| E06 | 官方产品 | [Anthropic — Run agents in parallel](https://code.claude.com/docs/en/agents) | subagent/team/worktree 区分；team 默认无 worktree 隔离 | Claude only |
| E07 | 原作者实验 | [Anthropic — Building a C compiler with parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) | 大规模压力上限、并行/串行瓶颈、test harness | 高成本、单项目、研究原型 |
| E08 | 原作者实验 | [Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)；[Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) | progress artifact、context reset、handoff、独立 evaluator | 特定模型与应用类型 |
| E09 | 官方工程报告 | [OpenAI — Harness engineering](https://openai.com/index/harness-engineering/) | repo knowledge base、progressive disclosure、计划与机械验证 | 单一内部实践 |
| E10 | 固定仓库快照 | [oh-my-codex @ b30127a](https://github.com/Yeachan-Heo/oh-my-codex/tree/b30127a0979c96046c8cd6312a8cd922c3516cad) | Codex workflow、team、ledger、checkpoint、review/QA | 快速演进；需本地复现 |
| E11 | 固定仓库快照 | [gstack @ 94993f7](https://github.com/garrytan/gstack/tree/94993f74012782fd94416dd44b8314f6363a13a4) | workflow chaining、context save/restore、benchmark | 多 harness；作者经验不等于通用阈值 |
| E12 | 固定仓库快照 | [Superpowers @ 44c9b2d](https://github.com/obra/superpowers/tree/44c9b2d6e889982ac18c27d05a19fefe335194e1) | 强制 workflow、worktree、TDD、review、skill tests | 平台无关目标与本项目不同 |
| E13 | 固定仓库快照 | [Gas Town @ 649b832](https://github.com/gastownhall/gastown/tree/649b832b7672bc7a2dbef26f5983aba6198b819b) | ledger、mail、handoff、watchdog、merge queue、telemetry | runtime 级；完整 Windows 流程依赖 WSL/tmux |
| E14 | 论文 | [Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296) | 固定预算下的拓扑/任务属性/协调开销 | 不是 Codex SWE 专项 benchmark |
| E15 | 论文 | [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) | 14 类 failure modes 和三大类失败 | 研究框架与 Codex 产品不同 |
| E16 | 论文与仓库 | [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) | 49 skills 成对评测、边际效用与版本冲突 | 很新的预印本；公开仓库在本轮 `git ls-remote` 未能复核 |
| E17 | 论文 | [From Registry to Repository](https://arxiv.org/abs/2607.00911) | skills 的复用、定制和维护模式 | 观察性研究，不证明因果 |
| E18 | 论文 | [SkillGate](https://arxiv.org/abs/2607.25619) | 恶意 skill 检测与供应链风险 | 很新的预印本 |
| E19 | 论文 | [SkillGuard](https://arxiv.org/abs/2606.03024) | skill-centric 权限与运行时风险 | 很新的预印本 |
| E20 | 官方指南 | [OpenAI — A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) | 先最大化单 Agent、再增量引入多 Agent | 通用 Agent 指南，不是 Codex App 规范 |

## 8. 仍未补上的坑

### 8.1 拆分与调度

- 编排者常把“可以列成多项”误判成“可以独立并行”；
- task 粒度过小，协调成本超过实现；过大则长时间无反馈；
- dependency graph 写对不等于运行时状态会及时更新；
- 多 Agent 在同一串行瓶颈前只会形成排队或重复劳动。

### 8.2 状态与恢复

- message、task status、Git tree 和实际运行进程可能互相不一致；
- compaction、fresh context、fork、handoff 和 resume 的信息继承不同；
- 完成声明、session 终止、任务归档和 worktree cleanup 是四个不同事件；
- stale worker、orphan session、失联锁和重复领取需要确定性恢复。

### 8.3 workspace 与集成

- worktree 只隔离 checkout，不隔离端口、数据库、缓存、队列、云资源和凭据；
- 不重叠文件仍可能依赖同一契约或生成物；
- merge clean 不代表 behavior clean；
- 外部服务和不可重放 side effect 不能只靠 Git 回滚。

### 8.4 验证与证据

- verifier 不完整时，Agent 会优化错误目标；
- 自评易偏乐观，maker-checker 也可能共享同一盲点；
- evidence 会因 tree、依赖锁、环境、suite、seed 或外部服务变化而失效；
- 全量重跑浪费成本，但过度信任缓存会掩盖组合失败。

### 8.5 skills 本身

- skill 名称/description 可能抢占或误导路由；
- 过多候选 skill 会占用发现上下文，且用户难以判断何时用；
- 复制来的 skill 容易与本地版本、工具名和权限模型不匹配；
- skill 可携带脚本、工具调用和行为指令，必须看作供应链 artifact；
- “文档存在”与“触发可靠、执行有效、失败安全”是三项独立质量。

### 8.6 产品与环境漂移

- Codex App、CLI、IDE、Windows 与 macOS 的能力暴露可能不同；
- tool schema、模型名、thinking 档位、并发配额和 UI lifecycle 会变化；
- managed worktree、permanent worktree、same-directory 与 local handoff 需逐版本核验；
- telemetry 不完整时，不能把 wall time 或调用数伪装成 token 成本。

## 9. 对本项目研究路线的修订

2026-08-12 的第二轮源码调查进一步修订执行顺序：先设计并运行一个真实多 session 工程闭环，capability matrix 保留为按需安全检查。详见 [大型 Skill 套件的工程方法提炼](large-skill-suite-engineering-methods.md)。

### R1：Codex capability contract（按需基础）

每次真实 run 先固定日期、App/CLI 版本、OS、Git 状态与工具 schema。只有当前 workflow 依赖某条未确认语义时，才从下列矩阵选择最小 case：

- create、fork、direct message、wait、steer、interrupt；
- local、managed worktree、permanent worktree、same-directory；
- handoff、resume、archive、cleanup；
- subagent 的上下文、模型、写入、等待和回收；
- ignored/untracked 文件、detached HEAD、共享端口和失败恢复。

产物不是教程，而是可机读 capability matrix、reproduction transcript 和 known-issues list。未运行组合保持 unknown，不要求在首个纵向切片前补满。

### R2：最小协议与 validator

冻结最小 task、worker card、artifact、handoff、evidence 和 lifecycle schema。先支持一个纵向切片需要的字段，保留 extensions，不为全部未来范式预建字段。

### R3：基线纵向切片

同一真实工程任务至少对照：

1. 单一主任务；
2. 主任务 + subagent；
3. 多个独立 Codex task + worktree；
4. task + subagent 混合。

接受标准、repo revision 和 verifier 完全相同；先测可并行模块 + 单一集成点，不先追求大并发。

### R4：skill marginal utility

每个候选 skill 做 paired run：no-skill、skill、过期/不匹配 skill。记录 pass rate、缺陷、返工、token、wall time、用户介入、上下文注入量和错误停止。

不能证明边际效用的内容仍可作为 research reference，但不晋升为 stable skill。

### R5：故障注入与恢复

覆盖 stale status、错误 revision、假 exit code、flaky test、失联 worker、冲突 handoff、端口/数据库共享、被中断 tool call、归档未 cleanup 和 skill 版本漂移。

### R6：按证据扩展范式

先完成 contract-parallel + single integrator，再逐步加入 stage pipeline、maker-checker、competing prototypes、incident swarm 等。扩展条件是出现独立触发场景、明确行为差异和 acceptance Gate，而不是目录对称。

### R7：社区知识与能力上限

持续维护：

- 官方能力快照；
- prior-art mechanism map；
- 可复现 recipes；
- 失败案例与反例；
- Windows/App/CLI compatibility；
- benchmark 数据和原始 artifacts；
- “已证明 / 仅观察 / 未验证”的公开状态。

## 10. 对 skills 架构的修订

### 10.1 保留大范围，但引入成熟度

长远仍可建设与 oh-my-codex 同量级的丰富套件，但每项标注：

- `research`：只有来源、假设或原型；
- `incubating`：已有可运行实现和初步实验；
- `stable`：触发、行为、失败和回归评测达标；
- `deprecated`：被新产品行为、协议或实验证据替代。

规模由已验证能力累积形成，不用“先列满目录”制造完成感。

### 10.2 六类交付物

1. **Workflow entry skills**：用户明确触发的 plan/run/status/integrate/recover/close。
2. **Execution skills**：确实改变执行流程的 contract-parallel、maker-checker、evidence handoff 等。
3. **Research/evaluation skills**：capability audit、paired benchmark、failure injection、trace/evidence audit。
4. **Agent profiles**：orchestrator、explorer、implementer、reviewer、integrator 等角色配置；默认不是 skill。
5. **Shared protocol/runtime helpers**：schema、validator、capability probe、Git/worktree preflight、evidence collector。
6. **References/examples**：完整 pattern catalog、decision tables、runbooks、成功与失败 traces。

### 10.3 不是每个 pattern 或 role 都自动成为 skill

候选项满足下列条件才单独晋升为 skill：

- 有用户或 Agent 能独立识别的触发条件；
- 与其他项相比会改变步骤、工具、产物或停止条件；
- 单独加载能减少上下文或错误，而不是只增加路由；
- 有正向、非触发、错误输入和恢复测试；
- 能做 no-skill baseline 或有清楚的确定性价值。

否则先作为 reference、decision profile、agent definition 或模板存在。这不是缩小范围，而是避免把知识分类误当成可执行能力。

### 10.4 stable core 与 research packs

第一批 incubating 核心围绕真实开发闭环：

- `team-plan`
- `team-run`
- `team-status`
- `team-integrate`
- `team-finish`
- shared schema/validator/preflight/evidence scripts

Capability audit、recovery、review 和 benchmark 先作为上述入口的支撑流程或项目开发工具，证明独立触发价值后再晋升用户入口。`contract-parallel` 先作为 `team-plan/team-run` 按需加载的 execution reference；worker 角色先做 Codex agent profile + brief 模板。

后续 research packs 可以广泛覆盖 pattern catalog、lifecycle、context rotation、model routing、proof reuse、incident、release、skill authoring 与 benchmark，不受“首批核心较小”限制。

## 11. 查询日志

Web 检索工具没有暴露搜索结果总数，所以下表不伪造总数；“纳入”是进入证据目录的高相关原始来源数量。搜索日期均为 2026-08-10。

| Pass | 精确查询 | 过滤/来源 | 结果记录 | 新增机制 |
|---|---|---|---|---|
| Q01 | `site:code.claude.com/docs/en agent teams subagents worktrees shared task list limitations` | 官方域名 | 总数不可见；纳入 3 | shared task、mailbox、locking、resume/cleanup 限制 |
| Q02 | `site:learn.chatgpt.com/docs Codex subagents worktrees handoff skills multi-agent` | 官方域名 | 总数不可见；纳入 3 | Codex task/subagent/worktree/handoff |
| Q03 | `site:github.com/Yeachan-Heo/oh-my-codex team worktree handoff ledger skills` | 官方仓库 | 总数不可见；纳入 2 | Codex workflow、ledger、team |
| Q04 | `gstack GitHub coding agent skills workflow` | GitHub/仓库 | 总数不可见；纳入 3 | workflow chaining、context save/restore、benchmark |
| Q05 | `site:github.com/obra/superpowers README skills subagent worktree verification` | 官方仓库 | 总数不可见；纳入 4 | mandatory workflow、skill behavior tests、consent |
| Q06 | `GitHub steveyegge Gas Town coding agents beads worktrees README` | GitHub/作者站点 | 总数不可见；纳入 4 | durable ledger、watchdog、merge queue、telemetry |
| Q07 | `site:arxiv.org "Towards a Science of Scaling Agent Systems"` | arXiv | 总数不可见；纳入 1 | topology/overhead/capability saturation |
| Q08 | `site:arxiv.org "SWE-Skills-Bench"` | arXiv + repo | 总数不可见；纳入 2 | paired marginal-utility eval、version mismatch |
| Q09 | `site:arxiv.org multi-agent coding agents coordination failure software engineering benchmark` | arXiv | 总数不可见；纳入 2 | failure taxonomy、verification/termination |
| Q10 | `site:arxiv.org/abs/2607.00911 "From Registry to Repository"` | arXiv | 总数不可见；纳入 1 | skill maintenance/reuse |
| Q11 | `site:arxiv.org/abs/2607.25619 SkillGate agent skills` | arXiv | 总数不可见；纳入 2 | skill supply chain、permission surface |
| Q12 | `site:anthropic.com/engineering "building a C compiler" 16 agents tests harness` | 原作者工程报告 | 总数不可见；纳入 3 | long-run ceiling、oracle、context reset/evaluator |
| Q13 | `site:openai.com/research coding agents multi-agent long running verification harness` | OpenAI 官方 | 总数不可见；纳入 2 | repo knowledge base、mechanical enforcement |
| Q14 | `"Use subagents" Codex "explorer" "worker" OpenAI` | OpenAI 官方优先 | 总数不可见；纳入 2 | 当前 subagent 角色与成本 |
| Q15 | `"Git worktrees" Codex "Local" "Handoff" OpenAI` | OpenAI 官方优先 | 总数不可见；纳入 1；另记录 issues 线索但未作产品事实 | Local/Worktree/Handoff 术语 |

为保留空查询和检索谱系，下面列出同批次其余 exact queries。所有查询的搜索引擎总数仍不可见：

| Pass | 精确查询 | 结果记录 |
|---|---|---|
| Q16 | `site:github.com/garrytan/gstack README skills workflow pair-agent worktree` | 纳入 2 个官方仓库页面；无新机制类别 |
| Q17 | `site:github.com/steveyegge/gastown README multi-agent worktrees agents` | steveyegge namespace 下 0 个直接命中；后续沿作者/仓库 lineage 定位 gastownhall/gastown |
| Q18 | `site:arxiv.org multi-agent LLM systems failure taxonomy coordination agents` | 纳入 1 篇直接 failure taxonomy，另 1 篇 survey 只作 discovery |
| Q19 | `site:arxiv.org/abs/2512.08296 "Towards a Science of Scaling Agent Systems"` | 纳入 1 篇 |
| Q20 | `site:arxiv.org/abs/2603.15401 "SWE-Skills-Bench"` | 纳入 1 篇 |
| Q21 | `Claude Code agent teams official documentation limitations shared task list teammates`，domain=`code.claude.com` | 纳入 1 个官方页面 |
| Q22 | `OpenAI Codex app multi agent worktrees skills official`，domain=`openai.com` | 纳入 1 个官方页面 |
| Q23 | `Codex subagents official documentation worktree handoff`，domain=`learn.chatgpt.com` | 本次搜索 0 个直接结果；沿已知官方文档 URL 复核 |
| Q24 | `Codex skills official progressive disclosure 2% context`，domain=`learn.chatgpt.com` | 本次搜索 0 个直接结果；未把百分比写成项目常数 |
| Q25 | `site:arxiv.org/abs/2503.13657 "Why Do Multi-Agent LLM Systems Fail"` | 纳入 1 篇 |
| Q26 | `site:github.com/GeniusHTX/SWE-Skills-Bench README` | 搜索页面命中 1 个仓库页；随后 `git ls-remote` 失败，已降级证据等级 |
| Q27 | `site:github.com/Yeachan-Heo/oh-my-codex/blob/main/docs skills agents team` | 纳入 1 个官方仓库文档 |
| Q28 | `site:github.com/gastownhall/gastown README roles refinery witness mayor worktrees` | 纳入 3 个官方仓库页面 |
| Q29 | `site:gastown.dev/docs concepts roles refinery witness mayor hooks lifecycle` | 纳入 2 个官方文档页面 |
| Q30 | `site:cdn.openai.com Codex maxxing long-running work agents worktrees handoff skills` | 纳入 1 份官方白皮书作 context |
| Q31 | `site:anthropic.com/engineering multi-agent coding long running agents verification` | 纳入 3 篇原作者工程报告 |
| Q32 | `site:developers.openai.com/codex subagents Codex worktrees` | 0 个精确文档命中；搜索只返回官方入口页，未新增证据 |
| Q33 | `site:developers.openai.com/codex skills progressive disclosure` | 0 个精确文档命中；未新增证据 |
| Q34 | `site:help.openai.com Codex worktrees handoff tasks app` | 纳入 1 个官方 Help Center 页面作产品 context |
| Q35 | `site:learn.chatgpt.com Codex subagents explorer worker` | 0 个直接命中；未采用二手教程作为官方事实 |
| Q36 | `"Build skills" Codex "progressive disclosure" OpenAI` | 纳入 1 个官方 customization 索引线索 |
| Q37 | `site:developers.openai.com/codex "subagents"` | 纳入 1 个官方 subagents 页面 |
| Q38 | `site:developers.openai.com/codex/customization skills "progressive disclosure"` | 0 个精确命中；未新增证据 |
| Q39 | `site:developers.openai.com/codex "Build skills" "SKILL.md"` | 0 个精确命中；未新增证据 |
| Q40 | `site:developers.openai.com/codex/app/worktrees Handoff` | 0 个精确命中；未新增证据 |
| Q41 | `site:developers.openai.com/codex/environments/git-worktrees` | 0 个搜索命中；官方 URL 由已有文档 lineage 直接复核 |

### 仓库 snapshot 核验

通过 `git ls-remote <repo> HEAD` 只读核验：

| 仓库 | HEAD |
|---|---|
| Yeachan-Heo/oh-my-codex | `b30127a0979c96046c8cd6312a8cd922c3516cad` |
| garrytan/gstack | `94993f74012782fd94416dd44b8314f6363a13a4` |
| obra/superpowers | `44c9b2d6e889982ac18c27d05a19fefe335194e1` |
| gastownhall/gastown | `649b832b7672bc7a2dbef26f5983aba6198b819b` |
| GeniusHTX/SWE-Skills-Bench | 本轮远端返回 `Repository not found`；因此只引用 arXiv 与检索到的仓库页面，仓库可用性标记待复核 |

## 12. 饱和、盲点与下一轮

最后两轮检索新增的是 skills 安全与版本维护，没有再出现新的多任务机制类别；第一轮在“原生能力、workflow、durable runtime、long-run harness、失败研究、skills 评测/安全”六类上达到主题饱和。

仍有四个盲点：

1. 尚未执行当前 Codex create/fork/message/wait/handoff/archive 的行为矩阵；
2. 尚未在同一真实工程任务上做 no-skill/single/subagent/multi-task 配对实验；
3. 论文结果尚未在当前 Codex 模型、Windows App 和本项目 schema 上复现；
4. 未对 oh-my-codex、gstack、Superpowers、Gas Town 做安装后黑盒复现，本轮只做了源码/文档级机制核验。

所以本页可以决定研究顺序和信息架构，不能宣称项目已经实现或达到上述能力上限。
