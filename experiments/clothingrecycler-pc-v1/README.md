# ClothingRecycler PC v1 Team skill 实验

## 实验目的

在不参与 ClothingRecycler 产品实现和集成决策的前提下，观察一次真实 Codex Desktop 产品任务如何使用 Team v0.1，并把可复现证据转化为 Team skill 的能力边界、失败样本和小范围改进候选。

本目录是实验观察记录，不是 ClothingRecycler 的产品事实源，也不是 Team canonical run directory。

## 范围与禁止事项

- 只观察产品主任务 `01a0467a-1f94-73c2-a4fe-cd560a146baf` 及其后续可见开发任务。
- 只保存对 Team skill 有用的章程、脱敏拓扑、artifact 引用、时间线、Gate 结果、阻塞、人工介入点、能力边界、backlog 和复盘。
- 产品代码、设计稿、业务契约和产品文档只留在 `D:\Desktop\ClothingRecycler`；本目录最多记录路径、Git revision、摘要和哈希。
- 不保存 API Key、Authorization header、完整敏感请求、原始对话全文或可还原的业务隐私。
- 不修改 `D:\Desktop\ClothingRecycler`，不替产品任务创建、派发、集成、归档或清理任务，不创建额外产品任务。
- 禁止使用 Superpowers。
- 在产品任务给出可复现证据前，不预改 Team skill。核心协议、默认范式或生命周期语义若确需改变，必须同步 `docs/13-decisions.md` 和 `docs/16-project-status.md` 并运行相关测试。

## 证据分级

- **已确认事实**：由当前 Git、文件 bytes/hash、Codex 原生任务读取或 CLI 只读查询直接支持。
- **实验观察**：本轮在明确时间、版本和任务条件下发生的行为；不外推为长期保证。
- **合理推测**：基于现有证据的解释，必须保留替代解释。
- **待验证假设**：需要后续 artifact、任务状态或 Gate 才能判断。

## 模型政策

以下均为用户指定或任务请求值；`read_thread` 当前没有暴露 effective model/reasoning 字段，因此不得把 requested 写成已确认 effective。`2026-08-29` 的最新政策替代启动时的产品 `xhigh` 约定：

- 规划、分析、集成判断和验收：`gpt-5.6-sol` / `high`。
- 产品开发执行（含开发任务内部 subagent）：`gpt-5.6-luna` / `max`。
- 本实验观察任务：`gpt-5.6-sol` / `high`。

此前已经完成的开发 lane 是在旧的 requested `gpt-5.6-sol` / `xhigh` 政策下运行，不能追溯性改写为 `luna/max` 证据。只有新建或恢复后的开发执行才能计入新模型分层实验。

## 记录结构

- `observations/`：按时间追加的只读观察与启动/阶段快照。
- `feedback-backlog.md`：由本次真实 run 支持的 Team skill 改进项；不把建议写成已实现能力。
- `final-retrospective.md`：本轮对 Team v0.1 的能力结论、人工介入和未验证边界。
- 只有在出现真实证据时，才新增脱敏拓扑、artifact 引用、失败、Gate、backlog 或复盘内容；不预建空的“完成证据”。
