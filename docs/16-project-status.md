# 16. 项目状态

## Snapshot

- 日期：2026-09-01
- 阶段：`M1.8 — Public GitHub release`
- 状态：`DrPei12/codex-team` public main、v0.1.0–v0.1.7 annotated tags/releases与assets已发布，private vulnerability reporting已启用。0.1.7 CI已通过finish/integrate并证明path修复有效，随后因runner cp1252 stdout打印Unicode path失败；D-055已接受，0.1.8显式UTF-8 CI正在追加发布。7个skill继续`incubating`，没有live fact collector或Desktop backbrief/checkpoint forward test
- 当前源码基线：branch `codex/team-v012-lifecycle`，本轮0.1.3实现基于实验审计commit `3563dbe`继续；0.1.1核心修复commit `85baabe`，0.1.2 lifecycle commit `d43aa9c`；`main`仍为`db3b810`
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
- [x] 核对 OpenAI 官方 plugin/skill 打包规则：一个 skills-only plugin 可包含一组 related skills，无需为本地 workflow 强行引入 MCP server
- [x] 接受 D-038 并实现确定性 `codex-team` plugin builder：staging + no-overwrite、bundled runtime/schema、`<TEAM_SKILL_DIR>` 可移动定位和 SHA-256 bundle manifest/self-check
- [x] Plugin packaging 回归 `8 passed, 0 failed`：两次构建 bytes 一致、篡改检测、错名/覆盖拒绝、源码仓库外全 runtime 正向运行
- [x] 临时生成包通过官方 `plugin-creator` validator、7/7 packaged skill `quick_validate.py` 和 37-file/7-entrypoint bundle self-check；全套九组 `98 passed, 0 failed`
- [x] 接受 D-039 并新增 repo marketplace contract：`.agents/plugins/marketplace.json` 指向 ignored `./plugins/codex-team`，plugin tests 增至 9/9，与 Team 回归合计 99 项
- [x] 完成两个真实安装周期：marketplace add、`0.1.0 installed/enabled`、38-file 源/缓存 hash 一致、plugin remove、marketplace remove 和最终缓存回滚
- [x] 安装后新任务 7-skill discovery、总入口显式调用、7-skill 显式加载矩阵、单次隐式路由和行为负触发完成；两条卸载后新 projectless task 均返回 `ABSENT`
- [x] 完成 ClothingRecycler PC v1 live Team 观察：5 个初始实现/设计 lane、integration、2 个 Gate successor、2 个 bounded repair、2 轮 independent review；最终产品 candidate 的发布边界与 Team 反馈位于 `experiments/clothingrecycler-pc-v1/`
- [x] 接受 D-040：ownership 裸路径统一拥有自身与子树，forbidden deny 覆盖 write allow，plan/integrate/recover 复用同一 matcher；三组 55 项定向回归通过
- [x] 接受 D-041：reviewer preflight 必须绑定 canonical dispatch/plan/apply/passed Gate 和真实 Git merge topology 的 post-integration exact target；`team-run` 26 项、`team-status` 20 项回归通过
- [x] D-040/D-041 后九组 Team 回归共 130 项全绿，包含离线端到端 artifact schema validation、relocatable plugin build/self-check 和 packaged `integrate → Gate → reviewer-preflight → finish`
- [x] 接受 D-042：协议修订构建版本升为 `0.1.1`，不以 same-version overwrite 假定 cache/task 刷新；真实安装升级仍需独立 snapshot/rollback 验证
- [x] 接受 D-043：manifest/brief/dispatch记录user locale、visible-task/internal-subagent、独立用户语言title和one-shot/milestone/long-lived-owner生命周期
- [x] 接受 D-044：finish输出逐lane task disposition；本轮按before snapshot/rollback纪律中文重命名并归档13条历史任务，主编排保持active
- [x] 接受 D-045：required标题/生命周期协议构建版本升为`0.1.2`；不覆盖当前installed 0.1.0
- [x] D-043/D-044/D-045后九组Team回归共133项全绿；team-plan/run/finish quick validation和临时0.1.2 bundle self-check通过
- [x] 接受D-046：manifest required requirement coverage lattice阻断ownership orphan、contract invariant缺失、unknown Gate和objective/forbidden path冲突
- [x] 接受D-047：prepare生成hash-bound worker backbrief template/argv；passed/needs-input/failed receipt阻止多级handoff静默丢失requirement
- [x] 接受D-048：stage checkpoint与lane material-progress facts进入status；依赖accepted但checkpoint pending时仍不得dispatch，heartbeat/turn limit使用manifest配置并checkpoint-stop
- [x] 接受D-049：新required协议构建版本升为0.1.3；不覆盖当前installed 0.1.0
- [x] D-046至D-049后九组Team回归共144项全绿；最终临时0.1.3 package为37-file/7-entrypoint自检通过，7/7 packaged skills quick validation通过
- [x] 接受D-050：冻结public仓库名、完整可达历史、0.1.0–0.1.3 tag commit、release asset与无许可证边界
- [x] 创建并验证GitHub public remote、main、v0.1.0–v0.1.3 tags/Releases/assets与private vulnerability reporting
- [x] D-051本地受影响回归通过：team-status 24/24、plugin 9/9、离线端到端/schema 1/1；总测试数145
- [x] 发布0.1.4并保留第二次CI失败证据；不移动0.1.3/0.1.4 tags
- [x] D-052本地九组回归146项全绿，离线主链16份artifact通过schema
- [x] 发布0.1.5并保留第三次CI失败证据；不移动0.1.3–0.1.5 tags
- [x] D-053本地九组回归148项全绿，离线主链16份artifact通过schema
- [x] 发布0.1.6并保留第四次CI失败证据；不移动0.1.3–0.1.6 tags
- [x] D-054本地九组回归149项全绿，离线主链16份artifact通过schema
- [x] 发布0.1.7并保留第五次CI失败证据；path phases已通过，失败为cp1252输出编码
- [ ] 发布0.1.8 UTF-8 CI fix并取得public main/tag CI green

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
- [x] 实现可移动 plugin/repo marketplace，并完成真实安装、7-skill 新任务加载、单次隐式路由与卸载后不发现验收
- [ ] 将当前手工 Desktop 观察固化为独立 adapter，强制 client surface、task/project、Git identity、证据路径和可观察的 requested/effective model/thinking 取证
- [x] 完成第一次 Desktop-native 多任务恢复链的 exact-tree public/review/sealed 验收
- [ ] 在隔离 solution objects/refs 的新 Git object store 中补充 OutputGuard Desktop single；将其明确标为有顺序污染风险的补充对照
- [ ] skills 冻结后选择第二个 blind benchmark，完成主要 no-skill/native single/native multi-task/skill-assisted 对照
- [ ] 对首批 skill 完成 no-skill、版本不匹配和故障注入对照
- [ ] 按 workflow 需要补核验 create/handoff/archive/subagent 与 dirty/failure 行为
- [ ] 证明自动集成在各风险等级的边界
- [ ] 在首个闭环后再研究 profile 裁剪、模型分级、context rot、更大并发和长期 owner 轮换

## 下一里程碑建议

`M1.8 — 0.1.3 controlled live successor and fact collector`

产物：

1. 保留 ClothingRecycler 原manifest、stale facts、手工fallback、九小时turn、UI/AI Native缺口和Android blocker，不改写成canonical成功；
2. 先为ClothingRecycler successor生成0.1.3 plan-only manifest，用requirement coverage证明AI workflow owner、代表性UI owner、Android verification-only owner和Gate/reviewer闭合；未通过不得dispatch；
3. 在独立临时fixture或新任务中forward-test一次真实worker preflight→backbrief，验证Desktop prompt/路径/receipt，而不先改产品；
4. 实现只读Codex-native fact collector：读取list/read/wait、Git与artifact，写新immutable progress/checkpoint facts，不发送消息或改变task；
5. 为产品 successor设置AI Native vertical slice与Dashboard/AI/operation-dialog视觉checkpoint；高级模型和用户先验收代表性证据，再允许扩展页面与昂贵系统Gate；
6. 单独解决Android baseline来源/审计/rebaseline授权，不能由Team skill静默改写；
7. 在受控snapshot/rollback下验证0.1.3安装、新任务discovery与explicit load；源码/package测试不等于installed runtime已升级；
8. 只有0.1.3 live checkpoint/backbrief、canonical integrate/reviewer/finish和新的blind benchmark都成立后，才讨论skill晋升。

已有 capability evidence 是安全输入，不再要求先补齐全部产品行为。纵向切片依赖某个 unknown 时才做对应 probe，并把未覆盖组合继续标为 unknown。

## 当前风险

- 产品工具行为可能随版本变化，文档中的快照必须复核；
- 当前本地 tool schema 只证明工具入口存在，不证明所有组合行为稳定；
- `multi_agent=stable,true` 是 CLI feature 声明，不能替代 subagent 生命周期实验；
- A2A 语义与本地扩展若边界不清，会产生“伪兼容”；
- 当前环境已观察 Codex 实际安装后保留 bundled 布局且新任务发现 7 个 skill；该结果只限 Windows / CLI `0.146.0` 当次条件，不是长期保证；
- CLI 历史回合能读取 token usage，但 Desktop task/follow-up/fork 未保证暴露同等 usage；telemetry 仍不完整，不能混合统计；
- 外部论文和社区仓库更新很快，数字和 HEAD 只能作为 2026-08-10 snapshot；
- skill 可能无正向边际效用、与项目版本冲突或形成供应链/权限风险；
- `codex-team` builder 的 bundle manifest 可检出普通文件篡改，但它不是签名/公证机制；攻击者同时改写产物与 manifest 不在当前威胁模型内；
- 已验证 repo marketplace、同版重安和卸载；未验证 plugin cachebuster、异版升级、禁用和新旧会话版本选择；
- D-040/D-041 目前只在源码 fixture、离线端到端和临时 plugin package 中验证；当前安装 cache 与既有 live task 仍可能运行旧 v0.1 bytes，未做升级/cachebuster；
- D-043/D-044新增required manifest字段，旧0.1.0/0.1.1 artifact/runtime不应被假定兼容；当前活动ClothingRecycler task没有热加载0.1.2证据；
- D-046至D-048新增required requirements/checkpoints/progress/backbrief字段；0.1.3只在源码、临时Git fixture和no-overwrite package验证，当前installed 0.1.0与历史ClothingRecycler artifacts均不会自动升级；
- stage checkpoint当前由manifest/status/router正常路径约束；纯skill不是权限系统，调用者绕过canonical workflow直接调用phase helper时不会得到后台强制拦截；
- 仍没有Codex-native live fact collector，Desktop task不会自动写material-progress或checkpoint facts；heartbeat/turn budget长期准确率与notification行为未知；
- ClothingRecycler当前idle且无进程残留，但正式发布仍受Android baseline mismatch、系统辅助accessibility Gate、AI Native product-surface覆盖和用户视觉验收阻塞；
- 负触发任务没有直接 skill-invocation telemetry，只能根据最终行为与无 bundle output 判定“相符”；隐式路由也只有一条高匹配样本；
- 一条卸载后 worktree task 只返回 client ID 而未得 thread ID，不计入验收；6 条可读测试任务保留 idle，本轮无 archive 授权；
- 本轮 managed worktree 已移出 Git registry，但 4 个产品管理容器目录仍存在且为空；plugin marketplace cache 父目录也存在但为空，本轮不手工删除这些容器；
- `team-plan` 的 symlink 边界已实测，Windows junction 未现场实测；
- `team-run` 已实测 Brief symlink、dirty/ignored、错误 cwd、receipt 不覆盖和 reviewer exact Gate target；仍未用 Desktop task forward-test reviewer 新路径，也未覆盖 Windows junction、submodule/LFS、detached HEAD 或 Git operation residue；
- `team-status` 已实测 identity/hash、依赖解锁、dirty handoff、跨-run evidence 和矛盾 facts，但没有 live Codex observer、消息/cursor 时序或长期准确率；
- `team-integrate` 的原 canonical candidate 在 ClothingRecycler live run 因 ownership mismatch fail closed；手工 ff-only/Gate 不能替代 skill apply 证据。D-040 修复仅在临时 fixture 验证，仍没有修正版 live apply、submodule/LFS、长队列、push 或 sealed 证据；
- `team-finish`仍只生成未授权task disposition和workspace建议；本轮另行验证native rename/archive/unarchive/rearchive及active主任务保留，但没有自动adapter、批次失败恢复、handoff或实际worktree/cache清理证据；
- `team-recover` 在 live capability blocker 上正确被 router 选中，但 candidate 因 ownership/非空 candidate 限制失败；后续 successor 为手工 fallback。D-040 只修 ownership，不解决 evidence-only recovery；
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

Phase 0 已在根提交 `35bec95` 完成。当前已进入 M1.7；仍然没有`stable` skill，但已有七个`incubating` Team skill、离线主链、可移动plugin、repo marketplace、真实0.1.0安装/发现证据和一轮有失败边界的Desktop live多任务观察。D-040至D-049源码修订后九组144项回归全绿，最终临时0.1.3 package自检与7/7 skill validation通过；0.1.3尚未安装或Desktop live forward-test。`team-plan`已在`main`，其余套件位于候选分支，`main`未合并。不能把手工fallback写成canonical全链已验证，也不能声称live heartbeat、自动checkpoint、长期标题语言、归档或worktree cleanup稳定。
