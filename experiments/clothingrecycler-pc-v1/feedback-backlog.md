# Team skill 改进 backlog

本 backlog 只记录本次真实 run 支持的问题与建议。优先级表示对 Team v0.1 可靠性的影响，不表示产品缺陷优先级。任何核心协议、默认范式或生命周期语义修改前，必须新增/替代决策并同步项目状态。

## P1：阻断 canonical 主链

### T-001 统一 ownership glob 语义

**状态：Source fixed / not deployed。** D-040 已接受；源码和定向/全量回归通过，修正版尚未安装或 live forward-test。

**证据：** manifest 使用裸 `docs/design/pc-ai-native-v1` 表达目录 owner，通过 plan/run；`team-recover` 和 `team-integrate` 用 `fnmatchcase` 将其解释为精确文件，所有真实子文件被拒绝。现有测试的目录示例使用 `owned/**`，但 manifest reference 未明确这一规则。

**影响：** canonical recover 和 integrate 都无法生成 candidate；本 run 被迫手工 successor 和手工 ff-only integration。

**建议：**

1. 已冻结裸路径语义为“路径本身及其后代”，与 planner 原有 ancestor/descendant overlap 规则一致；
2. plan/integrate/recover 已复用同一 segment-aware matcher；
3. 显式 glob 保留：`*`/`?` 不跨 segment，`**` 可跨 segment；
4. 已增加同一语义在 plan/integrate/recover 三阶段的一致性测试。

**变更等级：** 核心协议语义；需决策日志、状态页、schema/reference/runtime/tests 同步。

### T-002 Reviewer preflight 必须绑定 post-integration target

**状态：Source fixed / not deployed。** D-041 已接受；源码和定向/全量回归通过，尚未运行修正版 Desktop reviewer forward test。

**证据：** reviewer 与 integrator 共享 workspace，但 `team-run.worker_preflight` 固定要求 `observed.head == lane.workspace.base_revision`。Integration 完成后 shared workspace 已位于 post-integration HEAD，canonical reviewer preflight 必然失败。本 run 因此采用手工只读 reviewer。

**影响：** 文档宣称的 `team-integrate -> reviewer -> team-finish` 无法用当前 canonical worker preflight 在真实 integrated target 上闭环。

**实现：** dispatch 为 reviewer 预注册 canonical `--gate-receipt RUN_DIR/gate-receipt.json`。Reviewer preflight 只接受同 run、同 manifest、status passed、Gate 定义与 manifest 一致、file refs/hash 完整的 receipt，并把当前 workspace 绑定到其中 exact HEAD/tree；implementer/integrator 仍 base-bound。

**回归：** integrated HEAD 非 base 时 reviewer PASS；wrong HEAD/tree、dirty、不同 common-dir、非 passed Gate target 时 fail closed。

**变更等级：** 生命周期/身份协议；需决策和 schema/runtime/tests 同步。

### T-003 支持 capability failure / empty-code recovery

**证据：** Open Design lane 因 runtime reasoning 不可观测而在零产品改动时 blocked；`team-recover` 要求 non-empty changed files，无法冻结“没有代码 candidate、只有能力 blocker”的合法 predecessor。主编排者为满足 candidate 被迫先创建 recovery-context commit，随后仍受 T-001 阻断。

**影响：** 能力/工具失败不能自然进入 canonical recover，容易诱发为了满足 schema 而制造无关 commit。

**建议：** 增加 evidence-only/capability-failure recovery candidate，绑定 predecessor、workspace identity、零 diff、失败 tool receipt 和唯一新事实；禁止把它伪装成实现 candidate。

**变更等级：** recovery 协议扩展；需决策、schema 和负例。

### T-004 Canonical 表达 manual fallback 和 replacement Gate

**证据：** Open Design generation 失败后采用人工设计 fallback；Team candidate 又失败后采用手工 integration。产品能够继续，但 canonical status 无法精确表达“原能力仍失败、替代产物已被接受”。

**影响：** 容易把人工 fallback 重标为原 Gate success，或让 router 停留在旧失败而无法继续。

**建议：** facts 中分开记录 `original_capability_state`、`fallback_artifact`、`acceptance_scope`、`supersedes_for_delivery` 和 `does_not_prove`；router/finish 只消费明确批准的 replacement policy。

**变更等级：** 状态和生命周期语义；需决策。

## P2：增加失败轮次和人工介入

### T-005 Gate command qualification 与 MSB4126

**证据：** repair lane 的 frozen full Release Gate 使用 `.slnx -p:Platform=x64 -c Release`，在测试执行前因 `MSB4126` 失败；后续 bounded successor 才改用可执行的 test-project/build 命令。

**影响：** 功能候选被环境/命令合同错误阻塞，增加 successor，而不是提供产品质量信息。

**建议：** manifest 冻结前加入 command qualification receipt，分别验证项目/solution configuration、工作目录、无网络参数和输出根；qualification 只证明命令可执行，不预先宣称测试通过。

### T-006 Gate wrapper 不能只信外层 exit

**证据：** application-core 曾出现内层测试未启动但外层 exit 0；DeepSeek blocked wrapper 又因 repo-root 相对路径少一层而失败，随后用第二个 successor 修复。

**影响：** 仅记录 outer exit 可能产生 false PASS；相对路径错误会消耗完整 Gate attempt。

**建议：** receipt 同时绑定 inner argv/exit、expected marker、result count/log existence/hash；wrapper 必须从已绑定 repo root 定位，不从脚本层级猜测。增加“inner 未执行、outer 0”和“相对 root 错一层”负例。

### T-007 外部 live blocker 与 delivery classification

**证据：** 没有新 DeepSeek Key 时，live script 正确返回 inner exit 3/BLOCKED；其余 Gates 和 review 可以完成。最终合理分类是 `review-ready-but-live-blocked`，不是 failed，也不是 completed。

**影响：** 当前 finish 主链偏向 passed Gate，难以表达可交付候选但外部 live 条件未满足。

**建议：** 设计明确的 conditional milestone：列出 required-for-code、required-for-live、waived/blocked-by-external-state，不允许把 blocked 转 PASS；是否进入 finish 属核心生命周期决策。

### T-008 Model/reasoning 的 requested/effective/observability 三分

**证据：** Open Design 能选 `gpt-5.6-luna`，但无法设置/回读 reasoning；Codex task reader也未暴露 effective。后续 repair/review 都只能确认 requested policy。

**影响：** 本 run 只能证明模型路由请求，不证明实际模型分层效果。

**建议：** 所有 task/receipt 统一记录 `requested`、`effective`、`observability`、`fallback`；policy 决定 `effective=unknown` 时允许、阻塞还是升级，禁止从 prompt 推断。

### T-009 中断恢复需要 durable resume receipt

**证据：** 主编排与 integration 在中间停止后被外部观察任务恢复。`wait_threads` 只能确认 active/inProgress，不能证明从哪个 durable artifact/command 继续，也不能自动防止昂贵 Gate 重跑。

**建议：** status facts 增加 interrupted-at、last accepted artifact、consumed Gate evidence、next exact action、do-not-repeat commands；恢复时生成 non-mutating resume receipt。

## P3：质量与可维护性

### T-010 Review skill 依赖缺失不应污染 Team 验收语义

**证据：** 最终 reviewer 加载的通用 `review` skill 缺少其强制 `checklist.md`，只能退回人工只读审查。

**影响：** 这是相邻 skill packaging 问题，不是 Team v0.1 runtime 本身；但 Team 若把“调用 review skill”当独立 review 证据，会错误升级成熟度。

**建议：** Team reviewer brief 只要求独立、只读、exact-target 的审查合同，不依赖某个外部 review skill 名称；外部 skill load 成功单独记录。

### T-011 Finish 前纳入非阻断生命周期 findings

**证据：** 最终 review 唯一 P3 是 restore preview evidence 无过期/回收策略。

**影响：** 不阻断本轮批准，但长期会积累完整数据库副本。

**建议：** finish artifact 支持 `accepted_followups`，绑定 owner、风险和不阻断理由；不要自动创建 issue、删除 evidence 或把 P3 隐藏为“无风险”。

### T-012 Visual Gate 必须证明 material design delta

**证据：** UI lane 曾以 token、静态 WinUI Gate、Light/Dark/preview截图和 74/74 tests 被接收；用户随后明确否决，认为页面、背景、动画和 Apple-inspired UI/UX“根本没有大的改变”。此前 Gate 证明实现没有明显结构错误，但没有证明设计目标达成。

**影响：** 自动 Gate 与 worker screenshot 可在“视觉变化不足”时产生 false acceptance；用户主观目标没有被转成可审查 artifact。

**建议：** UI brief 必须冻结逐屏 before/after、视觉层级、material/background、motion、breakpoint 和 copy matrix；验收同时包含机器 Gate、运行截图和独立高级模型视觉 review。Reviewer 必须回答“变化是否足够明显且仍原生”，不能只核对 token/控件存在。

### T-013 用户可见 copy 需要结构化类别与 deny policy

**证据：** 用户在已 review-approved candidate 后要求“前端展示给用户的语言中解释性话语全部禁止出现”，说明原 contract 没有区分必要功能标签与解释性/营销/架构文案。

**影响：** 功能正确的 UI 仍可能因冗长副标题、教程、系统自述或 AI explanation 不可接受；纯 regex 很难独立判断语义。

**建议：** 维护 user-visible copy inventory；只允许 Nav/Field/Action/State/Error/ConfirmFact/Data 类别，拒绝 Description/Subtitle/Help/Tip/Explain/Marketing。机器 validator 负责 inventory/类别/重复与禁用前缀，高级 reviewer 逐屏检查语义；危险操作保留结构化影响事实，不能因“禁止解释”删除安全确认。

### T-014 Secret input 只保存 capability reference，不进入 artifact bytes

**证据：** 用户提供 `D:\Desktop\121.txt` 作为新 DeepSeek Key 来源。产品 live Gate需要读取真实 secret，但 Team artifact、command evidence和对话都不能保存 Key、请求头或可还原片段。

**影响：** 若 brief/receipt 把 secret 值或包含值的 argv/env dump纳入 proof，会造成凭据泄漏；若完全不记录，又无法证明 live Gate使用的是用户重新配置的新凭据。

**建议：** manifest/brief仅记录 secret source kind/path和授权，不记录 bytes/hash/长度/片段；受控 helper无输出导入 Windows credential store或进程内使用。Receipt只记录 `source_present`、`secure_import_succeeded`、`live_result`、`secret_output_detected=false`，并对日志做 fail-closed secret scan。Secret file删除/改写永不隐含授权。

### T-015 用户否决已验收里程碑时创建 successor，不改写旧 review

**证据：** 最终代码 review曾为 approved/live-blocked，但用户后来否决视觉结果并扩大UI验收。旧 review对当时 contract仍是事实，却不能继续支持正式发布。

**建议：** status facts支持 `superseded-by-user-rejection` 或等价 append-only successor关系，绑定新 acceptance delta；旧Gate/review保留，不重标为失败，新release candidate必须消费新successor结果。

## 推荐实施顺序

1. T-001/T-002 已完成源码修复；下一步先做同类 manifest 和 Desktop reviewer 的 live forward test，不直接重装覆盖旧 plugin。
2. 设计 T-003/T-004/T-007 的统一 successor/fallback/conditional milestone 状态机，避免三个局部补丁互相冲突。
3. 实施 T-005/T-006 的 Gate qualification 与 nested-exit receipt。
4. 补 T-008/T-009/T-010/T-011 的可观测性和治理材料。
5. 将 T-012/T-013/T-014/T-015 纳入下一版 UI/secret/status contract，避免本次用户否决再次发生。

在 T-001/T-002 完成 live forward test 前，不应声称 Team v0.1 的 live `integrate -> review -> finish` 已验证。
