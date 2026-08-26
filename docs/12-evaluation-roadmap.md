# 12. 评测路线

## 为什么必须做对照实验

多任务系统很容易在演示里显得强大：多个任务同时输出、消息互相到达、worktree 都有代码。但真实收益必须扣除 briefing、重复探索、等待、审查、合并、重测、失败恢复和任务管理成本。

评测单位应是“一个可验收的工程结果”，不是单个 worker 的输出数量。

Prior-art 调查进一步表明，skills 本身也必须作为 intervention 评测：目录更多、prompt 更长或流程更完整，不等于 pass rate 更高。每个可执行 skill 都应尽量有 no-skill baseline；每个多任务拓扑都应和能力相近的单任务/subagent baseline 比较。

截至 2026-08-25，Team v0.1 七个 skill 与离线主链已完成，可确定构建为可移动 skills-only plugin。原有 90 项与 8 项打包/隔离运行测试共 `98 passed, 0 failed`；临时生成包通过官方 plugin validator、7/7 packaged skill validator 和 37-file bundle self-check。当前证据支持“离线工作流可 fail closed，生成 plugin 可脱离源码仓库 cwd 运行”；仍没有真实 Codex marketplace/UI 安装、新会话触发、Desktop dispatch/live observation 或公平边际效用数字。OutputGuard 无 skill baseline 因读取历史 solution refs 和其他 planning guidance 被判为污染，只保留作 failure corpus。

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

## Prior-art 提供的研究约束

- Claude Agent Teams 官方说明、Anthropic C 编译器实验和多 Agent scaling 研究都把任务可分解性列为关键条件；本项目必须先描述任务拓扑，再评价并发。
- 长时 harness 实践显示 progress artifact、context reset/handoff 和高质量 verifier 是持续运行条件；不能只测“Agent 是否一直在线”。
- SWE-Skills-Bench 报告公开 skills 的平均边际收益很小且存在版本冲突退化；本项目不能跳过 paired evaluation。
- Gas Town 等 runtime 展示了 ledger、watchdog、merge queue 和 recovery 的高水位；Agent Orchestrator 展示了持久事实、派生状态与 Prompt/反馈路由；CCPM 展示了 PRD/Epic/Task 分解；Parallel Code/Conductor 展示了一任务一 worktree 的可视化。本项目只复现可由 Codex 原生 task + skill/schema/helper 驱动的机制，不复制其 daemon、adapter 或第二套 workspace runtime。
- gstack 源码显示其长处是阶段化 sprint，跨 session 并行主要交给 Conductor；Superpowers 把写入任务默认串行并逐任务审查，只并行真正独立的 domain；oh-my-codex 的耐久 Team 依赖 tmux/runtime。三者共同说明：第一实验应验证真实任务拆分和集成，不应继续把已知原语 smoke test 当主成果。
- 详细来源、适用条件和反面证据见 [prior-art 与能力上限调查](research/prior-art-and-capability-limits.md)。
- 针对大型工程方法的源码级提炼见 [大型 Skill 套件的工程方法提炼](research/large-skill-suite-engineering-methods.md)。

## 首个主评测问题

首个评测对象不是“功能入口是否存在”，而是一个完整结果：主任务能否把中等偏大的功能拆成可执行 task graph，冻结共享契约，把两个到三个实现 lane 放进独立 worktree，持续管理依赖和阻塞，再由单一 integrator 接收 commit/evidence、完成 review 和合并后 Gate。

第一轮有意限制为 3–5 条 worker session，方便定位失败；这不是长期并发上限。至少包含：

1. 一个必须先串行冻结的共享 contract；
2. 两到三个文件/模块所有权不重叠的实现 lane；
3. 一个独立 review/verification lane；
4. 一个集成点和只有合并后才有意义的 integration test；
5. 一次真实故障或受控注入，例如接口误解、证据缺项、worker 阻塞或所有权冲突。

## 已冻结的首个 benchmark、无效试跑与 Desktop lineage

首个纵向切片已选定 `ndcorder/outputguard` 的 JSONL streaming 功能，固定 upstream `cfcdf871ae613f4a958f1880283f31aa87d5875d`、公共 scaffold `d235f59dcb7eb853043117402d3a1c8ef267b9af`、公开 task/contract 和 sealed evaluator hash。目标项目代码没有 GitHub remote，worker 不接触 evaluator 路径或失败详情，以降低检索原实现和针对隐藏断言作答的风险。

2026-08-12 的第一次启动不能作为 benchmark 结果。它通过 CLI 启动了 core 与 CLI 两个 worker 回合；两者只得到 partial 输出，共消耗 3,099,681 input tokens（其中 2,923,008 cached）、38,788 output tokens 和 15,344 reasoning tokens。真实 worker sandbox 中的 Python launcher 无效、pytest/mypy 未运行、Git metadata 不可写，且 recorder 没有完成 retry manifest。single、integrator、reviewer 和 sealed evaluator 都未运行。随着 D-023 确立 Desktop 为权威执行面，该 run 被定性为 `stopped_invalid_for_comparison`，只进入 failure corpus，不能回答单任务与多任务谁更好。

冻结记录位于 `D:\Desktop\Codex多任务工程系统实验场\runs\2026-08-12-outputguard-jsonl-01\abort-result.json`。

随后，用户把实验场内 clean 的 `outputguard-single` checkout 注册为 Desktop saved project。Desktop 通过 `local` 环境创建任务 `019ff93b-d3a1-7cf3-8ee5-14a6e0561b65`，一个只读回合核验了正确 cwd、branch、`d235f59`、开始/结束 clean、`.git`/common-dir 归属和 Python 3.12.1 无 bytecode 导入；主任务又独立复核 saved-project 映射、任务 cwd、HEAD 和 porcelain。该 preflight 在只读范围内 PASS，但没有测试 Git metadata 写入、commit、pytest、mypy、Ruff 或 sealed evaluator，不能直接升级为实现环境已就绪。完整结果位于 `D:\Desktop\Codex多任务工程系统实验场\runs\2026-08-12-desktop-native-preflight-01\result.json`。

### Desktop write/test qualification 结果

2026-08-13 又进行了四轮有停止条件的 Desktop qualification。第一轮因 worker 在父任务停止规则后自行改命令继续而整体无效；后续没有把它“补救”为 PASS。第二轮用独立简单 Git 命令观察到 index refresh、临时 ref 创建/核验/删除和父任务 clean 验收，但系统 Python 缺 pytest，所以整体为 BLOCKED。第三轮在固定 lab venv 中得到 `2048 passed, 28 skipped`，随后因 Ruff 参数位置错误停止。第四轮的 Ruff format/check、mypy 类型结果和 Git diff 命令全部 exit 0，但 mypy 在仓库生成 `.mypy_cache`，因此仍为 BLOCKED；缓存被完整移动进 run artifact，而非删除现场。第五轮只改变缓存位置，固定 mypy 命令 exit 0，19 个缓存文件全部落在 run 目录，父任务确认仓库内 cache 为 0、Git 身份与 clean 不变，结果 PASS。

这些 run 合并后只支持“一个有界 Desktop local 实现条件已完成 Git/public test/Ruff/mypy 资格检查”。后续 Qualification 08 又在固定 Python、`uv --offline --no-python-downloads` 和 run-local seed cache 下生成 wheel/sdist；Qualification 09 由真实 Desktop local task 在 assigned permanent worktree 创建并提交唯一 marker 文件，同时保持 saved project 不变。它们仍没有验证功能实现、真实 handoff/integration/review、sealed Gate、长期可靠性或多任务收益。详细边界与下一步见 [首个纵向切片计划](19-outputguard-vertical-slice-plan.md)。

### 2026-08-15 Desktop 纵向切片结果

资格检查之后的功能执行形成 Run02–Run10 的恢复链。最终 Run10 在 exact tree `41de9670e0e9358fa7090e336ec2b561e139febb` 上完成：Core recovery `59 passed`；Integrator affected tests `64 passed`；完整 public suite `2093 passed, 28 skipped`；Ruff、mypy、离线 wheel/sdist 和最终身份边界通过；fresh Reviewer 关闭 R-002/R-003/R-004，仅保留一个 low；父任务只执行一次 sealed evaluator，`37 passed in 1.18s`。

该结果的严格表述是“一条 Desktop recovery lineage 在精确 tree 上完成公开、审查和 sealed 验收”。它不是一个无中断四任务 run：Run10 复用了 Run07 的 CLI commit 和 Run09 的 Core candidate，新建 Core recovery、Integrator、Reviewer 三条任务。Run02–Run09 的 blocked/changes-requested 状态全部保留。完整过程、hash 和限制见 [实录](research/outputguard-vertical-slice-2026-08-15.md)及[机器 evidence](../evidence/experiments/2026-08-15-outputguard-vertical-slice.json)。

这一轮直接观察到两类独立价值。其一，fresh Reviewer 在 public Gate 已绿时仍先后发现 R-001 和 R-002/R-003/R-004。其二，proof-carrying recovery 可以复用 exact candidate 和已验收 lane，只运行新增事实需要的 Gate，同时不把旧失败改写成成功。它也暴露了控制面缺陷：手抄 hash、未冻结 diff 算法、缺少 `--basetemp` 父目录和 ignored bytecode 残留。

因此 OutputGuard 现在主要作为 workflow 开发 trace 与 failure corpus。它不能单独证明 skills 的边际效用；后续 skills 冻结后必须在第二个未见 benchmark 上做主要 no-skill 对照。

## 评测矩阵

### E1：模型与 thinking 分配

当前 M1 不做跨模型对照。同一 Desktop benchmark 对照内部使用相同、明确记录的模型/thinking；用户没有明确指定时不覆盖 Desktop 默认配置，effective 值不可见时标为 `unknown`。这样先测编排方法，同时诚实保留无法严格控制模型这一限制。

以下矩阵推迟到首个工程闭环稳定后：

对照：

- 全员高能力/高 thinking；
- 高能力主编排者 + 常规模型 worker；
- 常规模型主编排者 + 强 reviewer；
- 自动升级策略。

指标：首次通过率、缺陷、返工、总 wall time、token（可取得时）、用户介入和升级正确率。

### E2：Briefing 形式

对照短结构化 brief、长叙述 prompt、结构化 brief + 按需 references。控制任务、模型和 workspace 一致。

### E3：单任务有效上下文（后续优化）

同一个 worker 连续领取 1/3/5/8 个同类和异类任务，并与每次 fresh task、forked task、rehydrated task 对比。不能只统计轮数；记录累计输入、压缩事件和 task switching。

观察：需求引用准确率、重复探索、旧决策污染、执行错误、handoff 完整度和单位有效产出。

### E4：Workspace 隔离

对照同一 checkout、managed worktree、permanent worktree；设置文件无重叠、同文件重叠、共享生成物和共享外部服务四类场景。

Normal/minimal profile 对照暂缓。第一轮只记录 memory/skills/plugins/MCP 注入，不尝试继续裁剪；不能把 worktree clean 当作上下文 clean。

### E5：编排范式

在同一中型功能上对照：单任务、hub-and-spoke、stage pipeline、contract-parallel。分别设置 embarrassingly parallel、contract-coupled、sequential bottleneck 三种任务图，且使用相同 acceptance Gate。不能用天然更容易的任务替并行方案加分。

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

### E10：Codex capability contract

在固定日期、App/CLI 版本、Windows 环境和 repo snapshot 下，逐项记录：

- create/fork 的历史继承与 workspace；
- direct message、wait、steer、interrupt 的送达与唤醒；
- local、managed worktree、permanent worktree、same-directory 的 Git 状态；
- handoff/resume/archive/cleanup 的状态转换；
- subagent 的上下文、模型、写入、等待和回收；
- ignored/untracked 文件、detached HEAD、branch 占用和失败后的恢复。

每项保存 tool input/output、Git before/after 和 cleanup evidence。产品文档或当前 schema 只能生成测试用例，不能替代行为核验。

2026-08-12 CLI 历史结果：两个 `codex exec -C` 会话在指定手工 worktree 中通过；idle message/wait 与 idle same-directory fork 通过。已消费 cursor 隐藏旧 final body，但 completed/notLoaded CLI task 仍以 `inactiveStatus` 唤醒。目录隔离没有阻止全局 memory/skills/plugins 加载，并发启动出现一次 system-skills access-denied。它们只约束当时的 CLI 条件，不能外推为 Desktop-native capability。详见 [pilot 报告](research/capability-pilot-2026-08-12.md)。

随后用两个串行新会话做 normal/minimal profile 配对。Normal 通过 verifier；粗粒度 minimal bundle 因 execution policy 阻止 verifier 而失败，input tokens 为 normal 的约 5.19 倍。结论只否定该组合，不外推到所有精简 profile。详见 [profile 对照](research/profile-comparison-2026-08-12.md)。

### E11：Skill marginal utility

对每个候选 skill 至少比较：

- no skill；
- 当前 skill；
- skill + 按需 reference；
- 过期或版本不匹配 skill 的受控负例。

指标包括 acceptance pass、缺陷、token、wall time、上下文注入量、返工、用户介入、错误停止和未触发/误触发。没有可测正收益的内容可以继续作为 reference 或 research artifact，但不能仅凭主观完整度晋升 stable。

### E12：Shared state 与 lifecycle 故障

注入 task status 滞后、消息重复/延迟、worker 完成但未更新状态、orphan session、失联锁、提前 archive、handoff 缺字段和 cleanup 失败。验收系统是否能发现不一致、恢复或 fail closed。

### E13：Git 之外的共享资源

设置端口、数据库、cache、queue、生成物目录、云资源和不可重放 side effect。验证 worktree 是否只隔离文件，以及 workspace policy 能否识别和分配这些资源。

### E14：Skill 兼容、维护与安全

- 固定 skill 来源、license、revision、Codex/OS/tool 兼容范围；
- 检查相对路径、脚本依赖、权限和网络/文件副作用；
- 注入陈旧工具名、过时 API 和恶意/越权指令；
- 测试升级、降级、deprecated 路由和 provenance 是否可追溯。

### E15：Desktop/历史 CLI/OS 能力矩阵

Active 基线以当前 Windows Codex Desktop 为准。既有 CLI 结果保留在独立历史矩阵，只用于发现可能的风险和差异，不作为任务执行 fallback。macOS、Linux 或远程 host 只有实际复现后才填写；缺失数据标为 unknown，不用社区描述补成已确认事实。

### E16：用户监督与认知负担

记录用户需要检查的任务数、关键决策数、误投/找回任务时间、approval 次数和失败恢复操作。多 Agent 节省模型时间但增加用户注意力时，应把两者同时报告。

## Baseline 层次

1. **Native single**：一个 Codex 任务，不加载本项目 skill。
2. **Native subagent**：一个主任务按当前原生能力使用 subagent。
3. **Native multi-task**：多个用户可见 Codex 任务，在 same-directory 或 worktree 中工作，不加载本项目治理 skill。
4. **Project workflow**：加载当前被评测的 skill、schema 与 helper。
5. **External mechanism reproduction**：只复现 Claude Teams、oh-my-codex、gstack、Superpowers、Gas Town、Agent Orchestrator、CCPM 或 Parallel Code/Conductor 的一个具体机制，不把整个外部系统当成可直接比较的参赛者。

Codex 官方文档提供测试用例 baseline，A2A 提供 task/message/artifact 语义 baseline，长上下文和多 Agent 研究提供风险假设。实际阈值必须用当前 Codex 模型和真实代码库重测，不能直接照搬论文、作者经验或产品推荐数字。

## 最低实验质量

- 固定代码库 snapshot、task spec 和 acceptance Gate；
- 固定 Codex 客户端、tool schema、模型、thinking、OS、依赖和权限；
- 至少重复多次并记录随机性；
- 保存所有 prompt/task artifact、revision、环境和证据；
- 区分执行时间、等待时间、模型时间和人工时间；
- 保存 no-skill baseline 和未触发、误触发、退化 run；
- 记录失败与撤销，不只展示成功 run；
- baseline checkout 必须使用不含其他 lane solution refs/objects 的独立 Git object store，并审计可见分支、artifact 和 evaluator 泄漏；
- ordinary、untracked、ignored 与运行 artifact cleanliness 分别记录，不能只保存一个 clean 布尔值；
- 不用同一 Agent 既设计评分又在不知道标准的情况下随意判分；
- verifier 有缺口时标为评测限制，不把“测试通过”外推成完整质量；
- 结论标注适用范围，不把单仓库结果外推到所有工程。

## Phase 1 推荐实验

按以下顺序推进，而不是继续穷举已知功能或直接实现全部 pattern：

1. 保持已冻结的 OutputGuard repo、task、contract、common scaffold 和 sealed verifier 不变；无效 CLI 试跑不回填答案或放宽 Gate。
2. 已完成：注册实验场内 checkout，并通过一个 Desktop local、只读、单回合 preflight，证明 task/project/cwd/HEAD/clean 和 Python 导入条件。
3. 已完成：在相同 Desktop local 权限模型中验证简单 Git index/ref 写入与 cleanup、无缓存 public baseline、Ruff 和 mypy 外置缓存；失败 run 保持原结论，不接触 sealed evaluator。
4. 已完成：冻结 `team-plan` 的四任务 DAG、所有权、依赖、task/workspace、Gate、集成顺序和停止条件；Core 与 CLI 可并行，Integrator 与 Reviewer 串行依赖。
5. 已完成：冻结该闭环需要的 session plan、roster、task brief、worker report、integration queue schema v0.1、正向样例、缺 proof 负对照和 validator；五个主线入口当时尚未实现。
6. 已完成：离线 package build qualification 和 assigned permanent worktree task preflight；两者均保留失败尝试、固定输入和父任务独立验收，且不接触 sealed evaluator。
7. 已完成：Desktop 原生 task 形成 Run02–Run10 recovery lineage，最终 exact tree 通过 public Gate、fresh review 和单次 sealed Gate；失败 run 不翻案，CLI 不作 fallback。该事实不等于无中断四任务 run 或多任务优于 single。
8. 已完成：`team-plan` v0.1 的 canonical manifest、机器派生 projection、artifact/worktree real-path 边界和 19 项回归。
9. 已完成：`team-run` 非 live 准备层与 `team-status` 只读 facts/derived renderer；真实 task 创建/消息/等待仍未运行。
10. 已完成：`team-integrate`、`team-finish`、`team-recover` 和统一 `team` 只读路由的 repo-local v0.1；Gate receipt、append-only recovery link 和 ordinary/ignored/operation-residue receipt 已落地。
11. 已完成：八组共 90 项回归通过，一条临时 Git/worktree 主链从 run preparation 走到 milestone completion，16 份产物通过 schema。该结果只是离线 workflow 证据。
12. 已完成：按官方 skills-only plugin 结构构建可移动 `codex-team`，bundled runtime/schema 不依赖源码仓库 cwd；两次构建 bytes 一致，全入口在临时目录隔离运行。
13. 下一步只在用户单独授权后验证 marketplace/UI 安装、新会话 discovery、显式/隐式/非触发对照、更新与卸载；同时可继续实现独立 Codex-native observation adapter，只读 list/read/wait、Git 和 artifact，写新 immutable facts。
14. OutputGuard native single 只能在不含 solution objects/refs 的新 Git object store、独立 Desktop project、冻结 prompt、零 follow-up 和同一 Gate 下补做；由于执行顺序与主编排者知识已受多任务 run 影响，它是带污染风险的补充对照。
15. Team v0.1 实际安装/live 边界冻结后选择第二个未见公开仓库与客观验收功能，主要比较 no-skill/native single、native multi-task 和 skill-assisted workflow；注入至少一个 E12/E13 故障，记录 Gate、返工、等待、冲突、wall time、可取得 token 和用户介入。
16. 第二 benchmark 后再决定哪些入口晋升 stable，并研究上下文裁剪、模型分层、更大并发和长期 owner 轮换。

这项顺序替代“先完成全部 capability contract 再开始纵向切片”的旧安排。已有 capability evidence 保留为安全输入，但不再是 M1 的主交付。
