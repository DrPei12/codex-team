# 用户可见任务生命周期治理 before snapshot

## 授权与边界

- 用户明确要求按分析结果改进旧任务堆积和命名问题。
- 产品主编排任务仍在执行，本轮不发消息、不重命名、不归档该任务。
- 本轮只处理最新有效 turn 已完成、且 commit/finding 已被后继消费或替代的 12 条历史可见任务。
- 归档仅改变侧栏生命周期；不删除历史、Git branch、worktree、artifact 或 cache。
- Open Design 外链未出现在 Codex `list_threads` 中，不属于本轮 task archive target。

## Before snapshot 与计划

| Thread ID | 原标题 | 最新有效状态 | 推荐中文标题 | 计划 |
|---|---|---|---|---|
| `01a04e0c-867f-7d02-928e-df842224f1f7` | `ClothingRecycler · final-repair-review` | completed / approved，后续视觉 successor 已重开 | `ClothingRecycler｜最终修复复核（历史）` | rename then archive |
| `01a04db8-ced1-7163-8b82-9d4b7657ce6d` | `ClothingRecycler · independent-review` | completed / findings 已进入后继修复 | `ClothingRecycler｜独立审查（历史）` | rename then archive |
| `01a04dd0-5703-7382-b72e-e680fd9db614` | `ClothingRecycler · repair-business-safety` | completed / commit 已进入后继集成 | `ClothingRecycler｜业务安全修复（历史）` | rename then archive |
| `01a04dd0-0a95-78b0-a442-5a9de168276f` | `ClothingRecycler · repair-ai-query-provider` | completed / commit 已进入后继集成 | `ClothingRecycler｜查询与供应商修复（历史）` | rename then archive |
| `01a04da9-6e80-73c3-8254-750dbca75f3f` | `ClothingRecycler · blocked-wrapper-repair` | completed / successor evidence preserved | `ClothingRecycler｜Live Gate 包装器修复（历史）` | rename then archive |
| `01a04d96-0730-7fa1-a05c-5b58412f534e` | `ClothingRecycler · integration-gate-repair` | completed / failed Gate 与 successor preserved | `ClothingRecycler｜集成 Gate 修复（历史）` | rename then archive |
| `01a0475f-ad97-7c30-8636-b37fe46676cd` | `ClothingRecycler · integration` | completed after earlier interrupted turn / superseded | `ClothingRecycler｜集成验证（历史）` | rename then archive |
| `01a04732-d60d-7ba1-bc23-1b0503ad3069` | `ClothingRecycler · ui-adoption` | completed / 用户已否决视觉结果并创建新 successor | `ClothingRecycler｜旧版 UI 接入（历史）` | rename then archive |
| `01a04725-28f1-71d3-a930-2c53c18b81b0` | `ClothingRecycler · design-system-fallback` | completed / 人工设计 fallback 被新视觉 successor 替代 | `ClothingRecycler｜旧版设计系统（历史）` | rename then archive |
| `01a046b2-58b9-73a3-8207-2241768b6e6f` | raw delegation prompt / no concise title | completed / business-adapters commit accepted | `ClothingRecycler｜业务适配器（历史）` | rename then archive |
| `01a04695-bad8-7000-9ac6-59bcee6635ae` | `ClothingRecycler · provider-security` | completed / commit accepted | `ClothingRecycler｜供应商与密钥安全（历史）` | rename then archive |
| `01a04695-6bc9-7263-a5f6-7eea41a3774b` | `ClothingRecycler · application-core` | completed / commit accepted | `ClothingRecycler｜应用核心（历史）` | rename then archive |

## Retain

- `01a0467a-1f94-73c2-a4fe-cd560a146baf`：产品主编排，当前 active，保留。
- 本实验观察任务：当前 active，保留。
- 主编排内部 release/UI subagents：不是侧栏可见任务，由父任务生命周期管理，本轮不操作。

## 预注册 rollback

任一操作失败时停止后续批次并保留已完成清单。Rollback 按每条 thread ID 执行：

1. `set_thread_archived(archived=false)`；
2. `set_thread_title` 恢复本表“原标题”；
3. 重新 `list_threads` / `list_archived_threads` 验证。

Raw delegation title 的完整原文保存在任务自身历史和 before snapshot tool evidence中；rollback 时若 UI title为自动生成长 prompt，可恢复为工具返回的原始 title，而不是从本文件重建 prompt。
