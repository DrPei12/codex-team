# 模板目录

这些文件是 Phase 0 的 **v0.1 设计模板**，用于让文档中的对象具体化。它们不是已冻结 JSON Schema，也不代表完整 A2A conformance。

| 模板 | 用途 |
|---|---|
| `worker-card.yaml` | 描述执行者的角色、历史、workspace、权限、模型和生命周期 |
| `task.yaml` | 描述一项工程任务及其 contract、依赖和 Gate |
| `artifact.yaml` | 描述可持久化输出和内容 hash |
| `verification-evidence.yaml` | 绑定 revision、测试命令、环境与结果 |
| `handoff.yaml` | 从 worker 向 reviewer/integrator 交接产物与风险 |
| `message-envelope.yaml` | 在 Codex 原生任务消息中携带短摘要和 artifact 引用 |
| `task-brief.md` | 主编排者给 worker 的可读任务说明 |

## 使用原则

- 复制模板后必须生成唯一 ID，不能保留示例占位值；
- 路径以仓库或 workspace 为锚点，避免依赖发送者当前目录；
- `revision`、hash 和测试结果不允许凭 Agent 推测；
- 空字段与“未验证”不同，必须显式记录 unknown/not-run；
- 大日志、patch 和报告放文件，模板中只存引用与 hash；
- schema 冻结后，所有模板都必须通过 validator。
