# 16. 项目状态

## Snapshot

- 日期：2026-08-25
- 阶段：`M1.4 — Team v0.1 offline workflow implemented; install/live validation next`
- 状态：Team v0.1 repo-local 离线工作流已闭环：`team-plan -> team-run -> team-status -> team-integrate -> team-finish`，失败转 `team-recover`，统一 `team` 只读路由。八组共 90 项回归和 16 份端到端 schema artifact 通过；7 个 skill 仍为 `incubating`。没有调用真实 Codex task 生命周期，没有合并 `main`，安装/live observation/公平 no-skill 对照仍未完成
- 本次同步所依据的功能基线：branch `codex/team-v01`，commit `e497188d27b5531aeb553d852d0a80a546e3bbdd` / tree `9930abfce6d637167f8dc907df1cd9d58ace94f0`；module commits `93a6d4d` / `95b8567` / `32927d0`；`main` 仍为 `db3b810`
- 项目目录：`D:\Desktop\Codex多任务工程系统`
- 范围：Codex only
- 研究起点 Git 基线：`35bec95`

## 已完成

- [x] 项目目标、非目标和成功标准
- [x] 编排范式、worker 角色、历史来源、workspace、生命周期的正交模型
- [x] 默认混合运行架构
- [x] Codex 任务/fork/worktree/handoff 的概念边界与待核验项
- [x] A2A-aligned task/message/artifact 设计
- [x] Proof-carrying handoff 和分层验收提案
- [x] 模型、thinking、上下文和升级策略
- [x] 任务保留、轮换、归档和 worktree 清理边界
- [x] 大型多-skill 架构与渐进式披露方案
- [x] 评测矩阵、决策日志、开放问题和讨论记录
- [x] 结构化模板草案
- [x] Codex/Claude 原生能力、oh-my-codex/gstack/Superpowers/Gas Town 和代表性研究的第一轮 prior-art 调查；补充核验 Agent Orchestrator、CCPM、Parallel Code/Conductor 并接受 Codex 原生组合边界
- [x] Claim-level evidence ledger、能力层级、未补坑点、查询日志与代码 snapshot
- [x] 社区开源研究定位、skills 成熟度和“pattern/role 不自动等于 skill”的架构修订
- [x] 当前 Windows、Codex AppX `26.803.10989.0`、CLI `0.146.0`、相关 feature flag、Git 与 repo 静态 snapshot
- [x] Desktop task/subagent tool schema 的 claim-level evidence ledger；九项 capability 中八项为 `declared_unverified`
- [x] Capability contract `0.1-draft` JSON Schema、只读 PowerShell probe 和 Python 标准库 validator
- [x] 带 baseline、负对照、混杂审计、预算和 stop rule 的行为实验计划
- [x] 只读 task list/read pilot：本项目 active task 可定位/读取，不存在 ID 显式失败；`codex.task.inspect` 有条件地标记为 `observed`
- [x] 项目外实验场、零依赖 fixture、两个手工 worktree 和可重复 baseline verifier
- [x] 两个持久 CLI 会话在指定 worktree 中完成只读核验，主任务独立验收后仍为 clean
- [x] 一个 idle direct message/wait 回合和一个 idle same-directory fork 历史继承回合
- [x] 最新 13 条 capability：5 条 `observed`、2 条 `contradicted`、6 条 `declared_unverified`
- [x] 发现 cwd/worktree 不隔离全局 memory/skills/plugins；接受三层隔离决策 D-018
- [x] 本地运行记录及 SHA-256；pilot 按 3 会话/2 worktree 预算停止
- [x] Normal/minimal worker profile 串行配对：normal 通过，粗粒度 minimal bundle verifier 失败且 input 约为 5.19 倍
- [x] 接受 D-019：上下文裁剪必须保留执行规则，按单一变量与固定 verifier 继续
- [x] 固定 gstack `94993f7`、Superpowers `44c9b2d`、oh-my-codex `b30127a` 源码快照并提炼大型工程方法
- [x] 确认 gstack 强在阶段化 sprint、Superpowers 强在 task/review 纪律、oh-my-codex Team 已进入专用 runtime 范围
- [x] 接受 D-020：M1 主线改为真实多 session 工程闭环，剩余 capability probe 按需运行
- [x] D-021 曾为 CLI 实验固定 `gpt-5.6-luna + high`；已由 D-023 对未来 Desktop task 的模型规则取代
- [x] 接受 D-022：复用三套 prior art 的方法，但不复制 tmux/daemon/mailbox runtime
- [x] 实验场新增机器可读模型政策与 `prior-art/` 只读源码目录；三份快照均 clean
- [x] 选择并冻结首个真实 benchmark：OutputGuard JSONL streaming；固定 upstream `cfcdf871`、common scaffold `d235f59`、公开 task/contract 和 sealed evaluator hash
- [x] 预注册 managed-first 与 single 对照、反作弊边界、成本字段和 stop rule
- [x] 冻结第一次 CLI 混合试跑为 `stopped_invalid_for_comparison`：只保留两个 partial worker 的失败证据，未运行 integrator/reviewer/single/evaluator，不产生比较结论
- [x] 接受 D-023：Codex Desktop 是后续 task 执行与协调的权威界面，CLI 不再启动 benchmark worker
- [x] 预注册一个不改代码的 Desktop-native 单 task preflight，明确任务创建授权、路径选择、PASS 和 stop rule
- [x] 将实验场内 `outputguard-single` 注册为 Desktop saved Git project，并通过 Desktop `local` 创建只读任务 `019ff93b-d3a1-7cf3-8ee5-14a6e0561b65`
- [x] 只读 preflight PASS：任务与主编排者分别确认 cwd、branch、`d235f59` 和 clean；Python 3.12.1 无 bytecode 导入成功；Git 写入与测试明确保持未验证
- [x] 接受 D-024：既定计划内可恢复的 Desktop 项目/任务/消息/等待等操作由主编排者自主完成，不再要求用户代发机械指令
- [x] Desktop qualification 保留四类失败证据并完成有效事实闭环：简单 Git index/ref 写入与 cleanup、`2048 passed / 28 skipped` public baseline、Ruff，以及 mypy 外置缓存
- [x] 冻结首个 [四任务纵向切片计划](19-outputguard-vertical-slice-plan.md)：Core、CLI、Integrator、Reviewer，包含 DAG、所有权、workspace、Gate、预算和停止条件
- [x] 冻结 session plan、roster、task brief、worker report、integration queue 的最小 schema v0.1、正向样例、缺 proof 负对照和标准库 validator
- [x] Qualification 08 资格化固定 Python 3.12.1、`uv 0.11.28 --offline --no-python-downloads`、run-local cache/dist 的 package build；一份 wheel 与一份 sdist生成，checkout 无残留
- [x] Qualification 09 由真实 Desktop local task 在 assigned permanent worktree 创建唯一 marker commit `fd81338`；父任务确认 parent/path/hash/clean，saved project 未变化
- [x] OutputGuard Run02 的集成实现通过实质 public 命令，但 parent final-boundary helper 对一字节 `dist/.gitignore` 产生 false negative；run 保持 blocked
- [x] Run03 修正同一 tree 的 public boundary 后由 fresh Reviewer 发现 high R-001；sealed 按规则未运行
- [x] Run04–Run05 分别保留 formatter Gate 设计错误和 aggregate diff hash 算法歧义，未用后继结果翻案
- [x] Run06 完成 canonical recovery、完整 public Gate 和 fresh review；Reviewer 新发现 high R-002/R-003/R-004，sealed 继续禁止
- [x] Run07 接受独立真实 CLI RED contract commit `c8d874e`；Core 因无证据 preflight false negative 停止
- [x] Run08 验证 canonical helper 51/51、零写入和 worker fail-closed；同时记录 parent 手抄 preregistration hash 错误
- [x] Run09 outer manifest 66/66，完成一次 RED 和精确三文件 candidate；因 parent 未预创建 pytest basetemp 父目录产生 20 个 fixture error，run 保持 blocked
- [x] Run10 复用 exact candidate：Core `59 passed` 并提交 `cde5592`；Integrator 得到 final commit `b67c8e` / tree `41de967`，affected `64 passed`、full `2093 passed / 28 skipped`、Ruff/mypy/offline build 全过
- [x] Run10 fresh Reviewer 关闭 R-002/R-003/R-004，critical/high/medium 为 0，保留 low L-001；父任务随后唯一一次 sealed run 为 `37 passed`
- [x] sealed 后 ordinary Git status clean、commit/tree 不变；29 个 ignored `.pyc` 被完整记录并保留，没有静默清理
- [x] 接受 D-027/D-028/D-029：canonical manifest、append-only proof-carrying recovery、artifact-root 与多层 cleanliness Gate
- [x] 完成 [OutputGuard 全流程实录](research/outputguard-vertical-slice-2026-08-15.md)和[机器 evidence](../evidence/experiments/2026-08-15-outputguard-vertical-slice.json)
- [x] 实现首个 `incubating` `team-plan`：canonical manifest schema、标准库 validate/project helper、精炼 skill/reference 和 19 项回归
- [x] 完成 `team-plan` RED/GREEN/REFACTOR：污染基线保留为失败语料，两次 forward test 一次 fail-closed、一次生成 4 份 digest-bound brief，四轮 fresh review 最终 approve
- [x] 接受 D-031：`team-run` v0.1 采用非 live 准备层，不把继续推进解释为创建用户可见 task/worktree/message 的授权
- [x] 实现 `team-run` schema/helper/skill：preregistration、runtime roots、parent/worker preflight、Prompt/dispatch bundle 和 11 项真实临时 Git/worktree 回归
- [x] 接受 D-032：组合 CCPM、Agent Orchestrator、Gas Town、Parallel Code/Conductor 的突出机制，但所有执行仍使用 Codex 原生控制面
- [x] 接受 D-033：`team-status` 保存 durable facts，显示状态只做可重建派生；依赖只认 accepted fact
- [x] 实现 `team-status` schema/helper/skill：facts 初始化、identity/hash validation、dependency/status derivation 和 18 项回归
- [x] 接受 D-034 并实现 `team-integrate` v0.1：exact candidate、manifest-order plan、显式授权 Git apply、exact-target Gate receipt 和 first-nonzero stop，12 项回归
- [x] 接受 D-035 并实现 `team-finish` v0.1：Gate/review binding、ordinary/ignored/operation-residue audit、run inventory 和非破坏性 milestone result，11 项回归
- [x] 接受 D-036 并实现 `team-recover` v0.1：clean commit 与 dirty patch/ZIP candidate、immutable predecessor、proof/new-fact/budget binding 和非 live recovery brief，10 项回归
- [x] 接受 D-037 并实现统一 `team` 只读路由：只读 canonical run artifact，选择下一 phase，不授权 task/Git/command/cleanup，8 项回归
- [x] 完成 Team v0.1 离线端到端主链：临时 Git/worktree 中从 prepare 走到 milestone completion，16 份产物通过 Draft 2020-12 schema
- [x] Team v0.1 全量验收：8 组 90 项回归、7/7 skill validator、9/9 schema meta-validation、3 份 capability contract 和 5 类旧 workflow artifact 通过

## 纵向切片清单（已完成与未完成）

- [x] 在实现前完成 Desktop Git/public test/Ruff/mypy qualification；不接触 sealed evaluator
- [x] 写出首个 task plan：共享 contract、DAG、4 条 worker lane、所有权、workspace 和集成顺序
- [x] 冻结 session plan、roster、task brief、worker report、integration queue 的最小 schema
- [x] 资格化离线 package build 命令，并把 dist/cache 全部限制在 run artifact 目录
- [x] 用真实 Desktop task 验证 saved project 控制入口与 assigned permanent worktree 写入边界
- [x] 启动真实 Desktop lane，并通过多次 fail-closed successor run 形成可验收 recovery lineage；未得到“一次无中断四任务 run”证据
- [x] 把 canonical manifest、机器派生 projection 和 artifact/worktree 安全边界固化为 `team-plan` v0.1 schema/validator
- [x] 实现并验证 `team-plan` v0.1；成熟度为 `incubating`
- [x] 实现 `team-run` v0.1 非 live 准备层；真实 Desktop create/message/wait 与 thread/project binding 未验证
- [x] 实现 read-only `team-status` v0.1 renderer；live Codex observation adapter 未实现
- [x] 实现 `team-integrate`、`team-finish`、`team-recover` 与统一 `team` 路由，并完成离线端到端验收；仍属 `incubating`
- [ ] 建立 Desktop-native 实验记录器，强制 client surface、task/project、Git identity、证据路径和可观察的 requested/effective model/thinking 取证
- [x] 完成第一次 Desktop-native 多任务恢复链的 exact-tree public/review/sealed 验收
- [ ] 在隔离 solution objects/refs 的新 Git object store 中补充 OutputGuard Desktop single；将其明确标为有顺序污染风险的补充对照
- [ ] skills 冻结后选择第二个 blind benchmark，完成主要 no-skill/native single/native multi-task/skill-assisted 对照
- [ ] 对首批 skill 完成 no-skill、版本不匹配和故障注入对照
- [ ] 按 workflow 需要补核验 create/handoff/archive/subagent 与 dirty/failure 行为
- [ ] 证明自动集成在各风险等级的边界
- [ ] 在首个闭环后再研究 profile 裁剪、模型分级、context rot、更大并发和长期 owner 轮换

## 下一里程碑建议

`M1.4 — Validate installation and observe native Codex task facts without mutating them`

产物：

1. 冻结 Run02–Run10 failure corpus 和 Run10 exact-tree acceptance evidence，不重跑 sealed、不清理隔离现场；
2. 审查 `codex/team-v01` 的 Team v0.1 完整 stacked history；未获单独授权时不合并 `main`；
3. 验证七个 skill 安装后的触发/非触发、helper/schema 路径、共享资源和 Windows 执行入口；
4. 实现独立 Codex-native observation adapter：只读 list/read/wait、Git 与 artifact，写新 immutable facts，不发送消息；
5. 对 duplicate/delayed message、cursor、task 不存在、task/project 错配和中途归档做 fail-closed 测试；
6. 只在用户单独授权后运行最小 Desktop live pilot，记录 create 返回的 thread/project/workspace binding 和真实 worker preflight；
7. 将 OutputGuard 保留为失败回归语料，选择第二个未见 benchmark，建立反 solution-ref 泄漏边界，完成主要 no-skill/native single/native multi-task/skill-assisted 对照；
8. 依据安装、live pilot 和第二 benchmark 证据，逐 skill 决定保持 `incubating`、晋升或降级。

已有 capability evidence 是安全输入，不再要求先补齐全部产品行为。纵向切片依赖某个 unknown 时才做对应 probe，并把未覆盖组合继续标为 unknown。

## 当前风险

- 产品工具行为可能随版本变化，文档中的快照必须复核；
- 当前本地 tool schema 只证明工具入口存在，不证明所有组合行为稳定；
- `multi_agent=stable,true` 是 CLI feature 声明，不能替代 subagent 生命周期实验；
- A2A 语义与本地扩展若边界不清，会产生“伪兼容”；
- 共享资源在多-skill 安装后的路径规则尚未验证；
- CLI 历史回合能读取 token usage，但 Desktop task/follow-up/fork 未保证暴露同等 usage；telemetry 仍不完整，不能混合统计；
- 外部论文和社区仓库更新很快，数字和 HEAD 只能作为 2026-08-10 snapshot；
- skill 可能无正向边际效用、与项目版本冲突或形成供应链/权限风险；
- Team v0.1 七个 skill 当前通过 repo-local 路径显式加载；作为可安装 skill 后能否稳定定位共享 schema/helper 和正确隐式触发尚未验证；
- `team-plan` 的 symlink 边界已实测，Windows junction 未现场实测；
- `team-run` 已实测 Brief symlink、dirty/ignored、错误 cwd 和 receipt 不覆盖，但未覆盖 Windows junction、submodule/LFS、detached HEAD 或 Git operation residue；
- `team-status` 已实测 identity/hash、依赖解锁、dirty handoff、跨-run evidence 和矛盾 facts，但没有 live Codex observer、消息/cursor 时序或长期准确率；
- `team-integrate` 的 Git apply/Gate 只在临时 fixture 中实测；没有真实 task handoff、submodule/LFS、长队列、push 或 sealed 执行证据；
- `team-finish` 只生成 archive/cleanup 建议；没有验证 Codex archive/handoff 或实际 worktree/cache 清理；
- `team-recover` 没有创建真实 successor task；“一个新事实”的实质性仍需人工审查，dirty snapshot 对 symlink/submodule/LFS/大文件的政策尚未完整；
- 统一 `team` 路由依赖 canonical 文件名；当历史产物不在 canonical 名称时，仍需明确接收/提升步骤，不能由路由器猜测“最新”；
- 当前仓库没有 LICENSE；本轮只独立实现 prior-art 思想，没有复制外部源码。任何后续源码复用必须先决定 LICENSE/NOTICE；
- 独立 cwd/worktree 仍会加载用户级 memory、skills、plugins、MCP 与 Git 配置；文件隔离不能当作上下文隔离；
- 两个历史 CLI 会话并发启动时出现一次共享 system-skills 目录 access-denied；它是 Desktop preflight 的风险提示，不是 Desktop 已复现缺陷；
- 第一组 minimal flags 已证明不安全且更贵，不能因名称是“minimal”就在后续 worker 中默认使用；
- 用户未明确指定时，Desktop 新建 task 必须使用其默认模型设置；effective model/thinking 若产品未暴露只能标 `unknown`，不能假装严格控制；
- `outputguard-single` 已注册为 Desktop saved project，解决了首个 local task 的实验根目录问题；它仍是手工准备的既有 worktree，不能证明 Desktop-managed worktree 的路径、创建或 cleanup 行为；
- 只读 task 能导入 Python 依赖，不等于能写 Git index/ref 或运行完整 Gate；前次 CLI 失败表明这两项必须在功能实现前单独 qualification；
- OutputGuard CLI 试跑留下两个 dirty worktree 和三个 runtime 目录；它们为失败证据保留，不提交、不集成、不隐藏评测，也不在未授权时清理；
- 固定 candidate venv 仍没有 `build`、`hatchling` 或 `pip`；当前 package Gate 只在固定 `uv 0.11.28`、显式 Python 3.12.1、原始 seed 的 run-local cache 和 `--offline --no-python-downloads` 条件下通过，未安装产物也未抓取网络包；
- assigned worktree 预检由固定 helper 完成，并非自由命令路由对照；Desktop task reader 未暴露底层 tool-call 明细。真实 lane 仍须逐条 preflight，且结果不能表述为 Desktop-managed worktree 已验证；
- oh-my-codex 表明耐久 lease、heartbeat、mailbox 和自动重分配很快需要专用 runtime；纯 skills 必须明确其恢复上限，不能伪装已有后台调度器；
- 过早把全部范式和角色包装成 stable skills 会造成大面积未验证规范，应先做纵向闭环；这不限制长期扩展范围。
- Run10 的成功来自 recovery lineage：接受 Run07 CLI commit、Run09 Core candidate 和三个新任务；不能改写成最初四任务 DAG 一次成功或估算可靠率；
- OutputGuard 已成为已见 failure corpus。继续只在它上面迭代会产生 benchmark overfitting；skills 边际效用必须转到第二个 blind benchmark；
- `outputguard-single` 与 lane worktree 若共享 Git object database，baseline 可能通过 refs/objects 看到 solution。补 single 前必须使用独立 object store 并审计所有可见 ref/artifact；
- Reviewer low L-001 尚未修复；当前只确认 malformed record 不会因此泄漏，不能把它写成完整线程安全保证；
- sealed pytest 的子进程留下 29 个 ignored `.pyc`。功能 Gate 通过与 evaluator harness residue-free 是两个结论，后续 helper 必须分别取证。

## 完成 Phase 0 的判定

Phase 0 已在根提交 `35bec95` 完成。当前已进入 M1.4；仍然没有 `stable` skill，但已有七个 `incubating` Team v0.1 skill 和离线主链验收。`team-plan` 已在 `main`，其余套件基线位于 `codex/team-v01`，尚未合并 `main`；不能表述为安装后或真实 Desktop dispatch/live observation/handoff/archive 已完成。
