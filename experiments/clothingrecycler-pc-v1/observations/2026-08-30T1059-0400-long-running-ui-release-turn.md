# 长时间 UI 发布轮次观察

## 结论

这不是“完全卡死”的证据，也不是“仍在高效推进”的充分证据。当前可确认的是：产品主编排把 UI 实现、修复、运行态 UIA/截图、真实业务 Gate、打包、干净安装与恢复集中在同一个可见 turn 中，持续超过 9 小时且没有向原生任务读取面暴露任何助手消息或工具进度标记。Git 与验收 artifact 证明期间存在大量实质进展，但发布仍有系统辅助无障碍 Gate 和独立终审未完成。

本记录不修改 ClothingRecycler，不中断主任务，不关闭任何应用或进程。

## 已确认事实

- 产品主任务：`01a0467a-1f94-73c2-a4fe-cd560a146baf`，标题 `ClothingRecycler｜主编排与发布`。
- 当前 turn：`01a05132-766c-7b03-b797-84b1d880e827`，从 `2026-08-30T01:44:16-04:00` 开始；截至 `2026-08-30T10:59:27-04:00` 仍为 `inProgress`，已持续至少 9 小时 15 分。
- 两次 Codex 原生 `wait_threads` 快照均返回 `active/inProgress`，且 `latestAssistantMessage=null`、`latestToolMarker=null`；第二次使用 cursor 后 `changed=false`。这证明观察面没有可见进度，不证明内部没有执行。
- `codex/pc-v1-integration` 在本 turn 开始后到 `10:50:15-04:00` 之间产生 25 个提交；最新 HEAD 为 `cd8c6ff53650a1054555594460c3ab9f986d5642`，工作区普通 clean。
- 当前 release 状态文件将候选分类为 `release-candidate-system-assisted-gates-pending`。
- 已记录的结果包括：115/115 Release tests、0-error Release build、真实 DeepSeek HTTP 200、10/10 UIA navigation、真实 backup success/failure、32 张 hash-bound PNG、ZIP/installer hash、可逆 clean install/launch 及旧安装 tree-digest 恢复。
- `runtime-gates.md` 和 release status 仍列出待完成项：200% Light/Dark、High Contrast、Narrator、keyboard focus restoration、reduced motion，以及完成这些证据后的独立终审。
- `2026-08-30T10:57:47-04:00` 与 `10:59:27-04:00` 的只读进程快照均未发现 ClothingRecycler、dotnet、MSBuild、testhost、vstest 或命令行包含 ClothingRecycler 的存活进程。当前没有证据表明应用实例持续堆积或残留。
- 截图写入集中在 `06:11–06:16` 和 `10:01–10:26` 两个窗口；clean-install receipt 记录过一次已响应 launch、UIA 10/10、测试安装移除和旧安装恢复。

## 实验观察

- 用户观察到应用被频繁打开；现有 Codex task API 和产品 artifact 没有记录逐次 launch/restart 数量，因此无法核实准确次数，也不能把 32 张截图等同于 32 次启动。
- 这轮同时产生 25 个 commit 和多类 Gate 证据，说明长期 active 不能直接判定为死循环。
- 但超过 9 小时没有可见 heartbeat，而一轮同时跨越实现、集成、运行测试、打包、系统状态恢复和发布判断，已使用户无法区分“必要回归”与“无收益反复启动”。这是 Team 的编排和可观测性缺口，不只是 UI 测试耗时。

## 合理推测

- 频繁打开应用的一部分可能来自 UIA 导航、主题/布局截图、backup success/failure 和 clean-install launch；这些是当前 release Gate 的真实需要。
- 后半段多次 UIA root/lookup 修复提交表明至少有一部分重复运行是“发现 Gate harness 缺陷 → 修复 → 重跑”，而不是单纯重复同一测试。
- 剩余 Gate 涉及系统缩放、Contrast、Narrator 和 reduced motion。若继续由主编排在同一 turn 临时操作，耗时和用户干扰仍可能继续扩大。

## 暂时无法验证

- 当前 active turn 内部正在执行的 exact command、实际模型/reasoning、已经启动过多少次应用、每次启动对应哪个 case，以及是否存在重复无变化重跑。
- 200%/High Contrast/Narrator/keyboard/reduced-motion 是否正在执行或只是排队。
- 当前候选能否通过最后独立 review 并正式发布。

## Team skill 价值

这段有直接实验价值，但支持的是两个新的治理问题，不支持“live worker dispatch 或长期触发稳定性已验证”：

1. **活动不等于可见进展。** Team 需要长 turn heartbeat/checkpoint，绑定最近 material delta、当前 phase、下一界限和无进展原因；超时应先产出可恢复 checkpoint，而不是自动中断或继续静默运行。
2. **GUI Gate 需要运行会话 receipt。** 每次或每批 launch 应绑定 target identity、case/purpose、PID/window、restart count、截图/结果、系统副作用及恢复、最终 process residue。没有这些数据，观察者无法判断必要矩阵测试和 launch thrash。
3. **主编排应保持项目级编排边界。** 可分离的系统辅助 UI matrix、安装恢复和独立 review 应形成有边界的 milestone/lane；主任务消费 receipt 和做 release 决策，不把所有交互塞进一个不可见的超长 turn。

## 下一观察点

- 等待主任务出现首次可见 assistant/tool marker、完成或 needs-attention；不做高频无变化轮询。
- 观察剩余五类 system-assisted Gate 是否各自生成 exact-target receipt，以及最终 reviewer 是否消费同一 commit/tree/package identity。
- 观察完成后是否留下应用进程、测试安装、系统 accessibility 设置、临时备份或未归档 successor；清理建议与自动清理授权继续分离。
