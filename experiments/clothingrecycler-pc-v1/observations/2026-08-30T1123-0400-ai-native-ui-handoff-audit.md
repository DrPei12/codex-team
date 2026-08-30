# AI Native、UI 与任务传递审计

## 结论

当前候选不应归类为“AI Native v1 已全部验收、可以正式发布”。更准确的结论是：**共享业务操作内核已经形成，安全/事务基础较强；实际 AI 产品入口仍主要是入/出库草稿 handoff，未覆盖 frozen catalog 的通用 query/command 工具面；UI 运行证据仍未达到用户冻结的视觉与 copy 目标；最新九小时工作也没有进入 canonical Team facts/brief/receipt 主链。**

本审计只读检查 exact integration workspace、既有运行截图、canonical Team artifacts 和 Codex 原生任务状态；没有启动应用、运行新产品 Gate、修改产品代码或打断任务。

## 主任务终态

- 主任务 `01a0467a-1f94-73c2-a4fe-cd560a146baf` 的 turn `01a05132-766c-7b03-b797-84b1d880e827` 已于 `2026-08-30T11:01:58-04:00` 完成。
- 精确耗时 `33,461,463 ms`，即 9 小时 17 分 41 秒。
- `wait_threads` 返回 task `idle`、turn `completed`，但 `latestAssistantMessage=null`、`latestToolMarker=null`；完成后用户仍没有可读 final/status marker。
- canonical `artifacts/run-001/status-facts.json` 最后观察时间为 `2026-08-29T11:24:28-04:00`，status snapshot 最后生成于 `11:25:31-04:00`。它们早于本次 8 月 30 日 UI/发布工作，因此不能表示最新候选状态。
- 最新产品状态仍为 `release-candidate-system-assisted-gates-pending`，而不是正式发布完成。

## 后端已确认能力

- frozen catalog 有 24 个 operation：8 个 query、16 个 command；其中 AI 允许全部 8 个 query，并可为 8 个普通 command 生成需人工确认的 preview，另 8 个危险 command 对 AI denied。
- `IOperationDispatcher`、catalog、validator、policy、preview binding、人工 confirmation、idempotency、transaction-coupled audit 和 structured error 已存在。
- `OperationUiService` 的人工和 `preparedByAi` session 都进入同一 dispatcher；AI prepared command 保留 AI actor/channel，execute 使用人工 confirmer。
- `OperationQueryService` 将 catalog query 路由到同一 dispatcher；AI business context 对 categories/customers 使用 AI actor query。
- 现有 release evidence 报告 115/115 tests、真实 DeepSeek HTTP 200、UIA 10/10、backup success/failure 和 package/clean-install receipts。它们支持底层能力，不自动支持完整 AI 产品入口。

## AI Native 缺口

- frozen product requirement 明确指出旧差距是 `AiWorkflowToolService` 主要做草稿 handoff/navigation，而不是通用 Application/Command/Query 层；当前实现仍保留这一结构。
- `AiWorkflowToolService` 定义的是 6 个 workflow-specific tool，核心副作用是 `AiDraftHandoffService.Store(...)` 与 `ShellNavigationService.Navigate(...)`，它本身不依赖 `IOperationDispatcher`、`IOperationCatalog` 或 `OperationQueryService`。
- 实际 AI UI 只暴露入库/出库草稿。完整草稿被送到页面后，页面才以 `preparedByAi=true` 建立 `inbound.create` / `outbound.create` preview。这证明两条 AI prepared command path 共用内核，但不证明 AI 可以调用 catalog 中的全部 8 个 query 与 8 个可预览 command。
- AI business context 只读取 categories/customers；没有用户从 AI command center 发起 dashboard、inventory、orders、analytics、consistency query 的端到端证据。
- 因此 AC-04 的“人工 UI 和 AI 都通过同一等价入口调用 catalog query/command”只在内核和两条业务 slice 上成立，产品级覆盖不完整。

## UI 运行证据缺口

- S01/S02/S08/S09 仍是大面积单色 canvas + 基础边框卡片，背景、玻璃层级、空间层次和视觉重点有限；与 frozen spec 的 material redesign、Apple-inspired hierarchy/whitespace/motion rhythm 仍有明显距离。
- AI command center 的可见模型仍是 Provider + 入/出库草稿表单，不是 catalog-driven AI operation surface；这与后端入口缺口相互印证。
- S20-dark 窄窗口中 Provider 文本和“语音设置”控件明显截断，主操作不在首屏可见区域；现有截图不足以支持 narrow composition 已完成。
- S21 operation dialog 直接显示 `maintenance.backup`、英文描述、raw JSON、完整本机 backup path 和长 state version；这违反用户禁止解释性/技术性话语的最新要求，也不符合 business-first confirmation UI。
- 当前 motion 实现可定位到 page `EntranceThemeTransition` 与 fade storyboard；没有运行证据证明 preview → confirmation → result 的连续动画、控件微交互或 reduced-motion 行为达到冻结目标。
- system-assisted 200%/Contrast/Narrator/keyboard/reduced-motion 和最终独立 review 仍未完成。

## 任务拆分与信息损失

### 已确认 ownership orphan

- run manifest 的全局 invariant 明确要求 WinUI 与 AI 共用 dispatcher/catalog。
- `ui-adoption` objective 明确要求 move manual pages and AI tools onto dispatcher。
- 但 `ui-adoption`、`application-core`、`business-adapters` 都 forbidden `PC/Services/Ai`；`provider-security` 只拥有 DeepSeek provider、settings 和 secret files，不拥有 `AiWorkflowToolService.cs`。
- 因此负责实际 AI workflow/tool routing 的文件没有任何 implementation lane owner。worker 只能在页面/ViewModel 层做 AI draft handoff，无法完成 objective 的完整语义。

### Gate coverage hole

- application/business tests证明 dispatcher、24 handlers、AI denied policy 和底层 AI actor可用。
- WinUI static Gate检查 composition root、`OperationQueryService`、AI categories/customers context 和 direct database bypass。
- 没有 Gate 从真实 AI command center 输入一个 catalog query/command，验证 operation selection、payload、AI policy、preview、人确认、execute、audit 的完整链路。
- 因此“测试全绿”证明组件成立，不证明 AI Native 用户流程成立。

### 最新工作脱离 Team 主链

- canonical Team facts/snapshot 在 8 月 29 日停止更新；8 月 30 日九小时 turn 的 25 个集成提交、UI runtime matrix、package/install receipt 没有生成新的 canonical immutable facts。
- 最新 turn 完成后仍无 assistant/tool marker；当前 API 也没有暴露内部 subagent prompt/receipt，因此无法审核最近开发执行是否遵守 `luna/max`，也无法核对指令在内部 handoff 中损失了哪些细节。
- 这不证明没有使用内部 subagent；它证明这段执行没有提供 Team 可审计的 topology、brief、receipt 和 heartbeat。

## 推荐检查点

1. **Plan coverage Gate**：每个 requirement/AC/invariant 必须绑定 implementation owner、owned path、Gate owner、evidence 和 reviewer；任何 unowned 或 objective/ownership 矛盾都禁止 dispatch。
2. **Worker backbrief Gate**：worker 在改代码前提交 machine-readable backbrief，列出已理解 requirement ids、输入 revision、owned/forbidden paths、输出、does-not-cover、疑问和 first test；主编排只审核 delta，不靠复制长 prompt。
3. **AI Native vertical-slice Gate**：先从真实 AI UI 完成一个 query 与一个 command preview → human confirm → execute → audit，再扩展到 catalog coverage；组件单测不能替代 slice。
4. **Visual direction Gate**：先交 Dashboard、AI command center、operation dialog 三张 exact-target 运行截图和 motion sample，经用户/高级 reviewer确认方向，再批量改其余页面。
5. **Mid-run checkpoint**：每个 phase 绑定 last material delta、当前 blocker、下一 bounded action、剩余 Gate 和 process/session receipt；超出 silent/wall-clock budget先 checkpoint，不自动无限继续。
6. **Pre-expensive-Gate review**：在200%/Contrast/Narrator/clean install之前先做 semantic/visual review；核心产品目标 changes-requested时禁止继续耗时系统矩阵。
7. **Final dual acceptance**：独立高级模型做 contract/architecture/visual review，用户做视觉和产品行为验收；两者均绑定同一 exact package source。

## 当前建议分类

- Operation kernel：已形成，有较强测试与 live evidence。
- Human structured operation path：大部分已迁移。
- AI Native product surface：部分实现，核心 catalog tool coverage 未完成。
- Visual redesign：changes-requested。
- Formal release：blocked/pending，不应宣称完成。
- Team experiment value：高；它提供了 ownership orphan、Gate coverage hole、stale facts 和超长无 marker turn 四个可复现样本。
