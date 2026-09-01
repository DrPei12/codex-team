# ClothingRecycler PC v1 Team 实验复盘

## 总结

这次实验既不是 Team v0.1 的端到端成功，也不是 Team 方法失败。

它证明了 Team 的若干治理机制在真实中型工程中有直接价值：先冻结契约和 owner、为 lane 建独立 workspace、worker preflight、exact commit/evidence handoff、first-nonzero stop、独立 review 和 bounded repair。尤其是第一次独立 review 在测试/build 已绿后仍报告四个 unresolved P1，随后修复链形成五项最终 closure criteria，说明“worker 完成 + 自动 Gate”不能代替高级模型验收。

它也证明了当前 v0.1 的 canonical live 主链尚未闭合：recover/integrate 因 ownership 语义失败，reviewer preflight 不能绑定 post-integration HEAD，Open Design/手工 fallback/外部 live blocker 只能靠人工状态转换，最终 finish 没有以纯 canonical artifact 链完成。

## 实际规模

- 1 个产品主编排任务。
- 至少 12 个可见产品侧执行/集成/修复/审查任务：5 个初始实现/设计 lane、integration、2 个 Gate successor、2 个 bounded product repair、2 个 independent review。
- 1 次用户中断后恢复；观察任务显式恢复主编排和 integration。
- 多次 fail-closed successor，而不是原地把失败结果改成通过。

任务数量不等于并行收益。本次没有 no-Team 或 single-task 对照，也没有可靠 token/cost/effective-model telemetry，因此不能声称 Team 更快、更省或模型分层带来质量提升。

## Phase 结论

| Phase | 本次观察 | 能力结论 |
|---|---|---|
| `team-plan` | 生成 manifest、brief、DAG、owner 和 Gate，支撑多 lane 开发 | 有实际价值；但 ownership 裸路径语义未在计划阶段 fail closed |
| `team-run` | implementer/integration preflight 和 receipts 被使用 | 初始 lane 可用；reviewer preflight 被 base revision 绑定，不能用于 post-integration target |
| `team-status` | 主编排维护过 status facts/snapshot，router 用于恢复 | artifact-to-status 有用；live observation、manual fallback 和 successor 状态仍依赖人工 |
| `team-integrate` | candidate 阶段因 ownership mismatch 停止；未生成 canonical candidates | fail-closed 有效，但本次没有验证 canonical live integration；实际采用手工 ff-only |
| `team-recover` | router 正确选择 recover；candidate 因 ownership/empty candidate 失败 | 路由边界有效，真实 capability-failure recovery 未闭环 |
| reviewer | 两轮独立 read-only review，第一次 changes-requested，第二次 approved | 高价值；但未通过 canonical reviewer preflight，属于手工 reviewer 流程 |
| `team-finish` | 最终形成 review-approved/live-blocked candidate | 未证明 canonical finish；archive/cleanup/default-branch merge/release 未验证 |

## 什么真正起作用

1. **契约先行。** 24 个 operation、AI safety、owner 和 stop conditions 给 repair/review 提供了可判定目标。
2. **Worktree + owner。** 初始 lanes 和后续 repair 能隔离修改；worker 都报告 exact commit 和 clean 状态。
3. **Fail closed。** MSB4126、wrapper 路径错误、live no-key 和 integration candidate mismatch 没有被原地改写为 PASS。
4. **独立 review。** 初审推翻“只剩 live blocker”的过早结论；初审发现与后续 hardening 最终形成 dispatcher、数据最小化、endpoint、restore 和 filesystem idempotency 五项 closure criteria。
5. **Bounded repair。** 修复被拆为 AI/query/provider 和 business recovery 两个 owner 清晰的 lane，最终在 exact integrated target 上复核关闭。
6. **证据分级。** 最终 reviewer区分当前 Git/代码确认、committed Gate evidence 推断和 live/运行未验证边界。

## 什么没有起作用

1. Ownership 语义在 plan 与 integrate/recover 之间不一致，直接击穿 canonical candidate 流程。
2. Reviewer preflight 的 base-bound 设计与“审查集成后共享 workspace”冲突。
3. Capability failure 没有 zero-code/evidence-only recovery candidate。
4. 人工 fallback 缺少原能力失败与替代产物接受的 canonical 双轨表达。
5. Gate 命令在冻结前没有资格化，产生 MSB4126 successor。
6. Wrapper 外层退出和内层语义未被统一绑定，出现 false-green 风险和相对路径失败。
7. Finish 无法自然表达“代码可交付、live 外部状态 blocked、运行无障碍仍未验证”。

## 模型分层结论

- 启动阶段的初始开发 tasks 在旧 requested `gpt-5.6-sol/xhigh` 政策下完成，不能计为 luna 开发证据。
- 后续两条 bounded repair 请求 `gpt-5.6-luna/max`，两条 review/主编排请求 `gpt-5.6-sol/high`，角色路由符合最新政策。
- 所有相关任务的 effective model/reasoning 均不可独立观测。因此本次只验证“请求如何路由”，不验证实际 effective 配置，也不能做高低模型质量/成本比较。
- 若未来要评估模型分层，需要 task-level effective telemetry、同 brief 对照、质量/人工返工/耗时/token 指标。

## 产品交付边界

最终 exact candidate `8f1e8b…` 得到只读 reviewer `approved`，无 P0–P2；这支持把它交给用户做 live Key 配置和真实运行验收。

仍不能声称：

- DeepSeek live success；
- Open Design generation；
- 真实 200%/High Contrast/screen reader；
- 默认分支合并、安装包、发布、archive 或 cleanup；
- 长期稳定性或无残余风险。

## Team v0.1 成熟度结论

维持 `incubating`。本次新增了真实 live task dispatch、worker preflight、任务恢复、手工 integration、独立 review 和 bounded repair 的行为证据，但没有证明 canonical `team-plan -> team-run -> team-status -> team-integrate -> reviewer -> team-finish` 端到端闭环。

下一次 forward test 应以 T-001 和 T-002 修复后的同类 manifest 为前提，目标不是再做一个更大产品，而是验证：

1. 目录 ownership 在 plan/candidate/recover 一致；
2. reviewer 能从 passed integration target 自动获得 exact preflight；
3. capability failure/manual fallback/conditional live blocker 能进入 canonical facts/router/finish；
4. 全链不需要手工伪造 candidate 或绕开 canonical phase。

## 2026-09-01 追加结论

上述“产品交付边界”是早期candidate时点，已被后续事实替代但不删除。最新integration HEAD为`0edecbc90fe94f2b0901227b0e53066b4f6f646c`；DeepSeek live、115/115 tests、UIA、package/clean-install已有证据，但正式发布仍受Android baseline mismatch、系统辅助accessibility、AI Native product-surface覆盖和用户视觉验收阻塞。

九小时主turn与最终代码审计新增了三个比T-001/T-002更上游的问题：全局requirement可在lane拆分后成为ownership orphan；worker/组件Gate可以全绿而真实AI用户链路未覆盖；canonical facts可以停止更新而主任务继续大量实现和GUI Gate。D-046至D-049因此新增0.1.3 requirement coverage、worker backbrief、stage checkpoint和material-progress协议，并通过九组144项源码回归与临时package验证。

成熟度仍为`incubating`。0.1.3没有安装、没有live fact collector，也没有Desktop worker backbrief/checkpoint forward test；不能把源码协议改进写成现有产品任务已自动获得heartbeat或Team端到端能力。
