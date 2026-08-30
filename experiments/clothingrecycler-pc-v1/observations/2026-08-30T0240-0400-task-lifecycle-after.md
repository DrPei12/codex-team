# 用户可见任务生命周期治理 after snapshot

## 执行结果

- 12 条已完成历史任务全部成功改为中文职责标题并归档。
- 1 条此前已归档的 Open Design 任务因归档状态下无法直接改名，按预注册的可恢复步骤执行：临时取消归档 → 中文重命名 → 重新归档，三步均成功。
- 产品主编排任务未归档，并以后台标题操作改为 `ClothingRecycler｜主编排与发布`；运行 turn 未被打断。
- 本实验任务继续保留。
- 未删除或移动任何 task history、branch、worktree、artifact、cache 或 Open Design 项目。

## 归档任务

| Thread ID | 最终标题 |
|---|---|
| `01a04e0c-867f-7d02-928e-df842224f1f7` | `ClothingRecycler｜最终修复复核（历史）` |
| `01a04db8-ced1-7163-8b82-9d4b7657ce6d` | `ClothingRecycler｜独立审查（历史）` |
| `01a04dd0-5703-7382-b72e-e680fd9db614` | `ClothingRecycler｜业务安全修复（历史）` |
| `01a04dd0-0a95-78b0-a442-5a9de168276f` | `ClothingRecycler｜查询与供应商修复（历史）` |
| `01a04da9-6e80-73c3-8254-750dbca75f3f` | `ClothingRecycler｜Live Gate 包装器修复（历史）` |
| `01a04d96-0730-7fa1-a05c-5b58412f534e` | `ClothingRecycler｜集成 Gate 修复（历史）` |
| `01a0475f-ad97-7c30-8636-b37fe46676cd` | `ClothingRecycler｜集成验证（历史）` |
| `01a04732-d60d-7ba1-bc23-1b0503ad3069` | `ClothingRecycler｜旧版 UI 接入（历史）` |
| `01a04725-28f1-71d3-a930-2c53c18b81b0` | `ClothingRecycler｜旧版设计系统（历史）` |
| `01a046b2-58b9-73a3-8207-2241768b6e6f` | `ClothingRecycler｜业务适配器（历史）` |
| `01a04695-bad8-7000-9ac6-59bcee6635ae` | `ClothingRecycler｜供应商与密钥安全（历史）` |
| `01a04695-6bc9-7263-a5f6-7eea41a3774b` | `ClothingRecycler｜应用核心（历史）` |
| `01a04696-0fc1-7160-9491-e6b718ab9ca8` | `ClothingRecycler｜Open Design 设计尝试（历史）` |

## 验证

- 普通 `list_threads` 中不再出现上述 13 条历史任务。
- `list_archived_threads` 返回这些任务及其中文标题。
- 产品主编排 `01a0467a-1f94-73c2-a4fe-cd560a146baf` 仍为 active。

## 新 Team contract 候选

本次行为触发 Team 0.1.2 候选改进：

- root manifest 记录 `user_locale`；
- lane 记录 `execution_surface`、独立 `task_title` 和 `lifecycle`；
- visible-task 必须有最多 80 字符、单行、非 prompt 的用户语言标题；
- internal-subagent 不创建侧栏任务、title 为 null 且仅允许 one-shot；
- finish 输出逐 lane `task_dispositions`：archive / retain / not-applicable；
- 所有 disposition仍 `authorized=false`，需要用户授权、before snapshot和rollback映射；
- task archive 与 worktree/evidence cleanup继续分离。

## Source/package 验证

- Candidate plugin version：`0.1.2`；
- 九组 Team tests：`133/133`；
- team-plan/team-run/team-finish quick validation：通过；
- 临时 package：`C:\Users\lenovo\AppData\Local\Temp\codex-team-forward-2d62408b2ae24173888f684ff303db50\codex-team`；
- bundle self-check：37 files / 7 runtime entrypoints；
- bundle manifest SHA-256：`c935261251d61787491922a551ce470d50e7ef49842abf203cf0a3cdf9f1e1b5`；
- 当前 installed plugin仍为0.1.0，本轮没有marketplace/install/cache mutation。
