# 06. 任务、消息与 Artifact 模型

## 设计立场

本项目不重新发明一套完整 Agent 通信协议，而是复用 A2A 的核心语义：Agent 能力描述、Task 生命周期、Message、Part、Artifact 和上下文关联。

但 Codex 任务之间当前使用的是产品原生消息和仓库文件，不需要为了“标准化”先部署 A2A HTTP/JSON-RPC/gRPC 服务。第一版是 **A2A-aligned local profile**：语义对齐，传输沿用 Codex，持久事实进入 Git/artifact。

## 为什么 Agent 汇报不能照搬面向用户的回复

用户回复要帮助人快速理解结论、风险和选择；Agent 交接要让接收者能继续执行并机器校验。后者更强调：

- 稳定 ID 和明确状态；
- revision、路径、hash、命令和环境；
- 输入输出 contract；
- 覆盖范围与未覆盖范围；
- 可执行的下一步；
- 大内容的 artifact 引用，而非一大段叙述。

Agent 消息也不应成为不可读的纯 JSON 垃圾。推荐“短人类摘要 + 结构化引用”，关键字段可被 skill 解析。

## A2A 语义映射

| A2A 概念 | 本项目中的用途 |
|---|---|
| Agent Card | `worker-card`：能力、角色、workspace、权限、模型策略和生命周期 |
| Task | 一项有唯一 ID、状态、目标和 owner 的工程工作 |
| `contextId` | 同一功能、里程碑或故障的相关任务组 |
| Message | 指令、提问、阻塞、状态或接收确认 |
| Part | 文本、结构化数据或文件/artifact 引用 |
| Artifact | 代码 revision、设计、测试报告、日志、patch、schema 或交接包 |
| Task status | submitted / working / input-required / completed / failed / canceled 等状态 |

具体字段以采用版本的 A2A 规范为准。本项目模板添加的 Git、测试和 workspace 字段属于本地 profile，不冒充 A2A 标准字段。

## 核心对象

### Worker Card

描述“谁能做什么、在哪做、能做多久”：

- `worker_id`、显示名称和角色；
- 能力与非能力；
- `history_origin`；
- `workspace_mode`、路径、branch 和所有权；
- 默认模型/thinking 与升级条件；
- 可执行和禁止的操作；
- 生命周期和当前状态。

### Task

描述“要完成什么”：

- `task_id` 和 `context_id`；
- 目标、业务背景、范围、非范围；
- base revision 和依赖；
- owner、reviewer、integrator；
- 输入 artifact 和输出 contract；
- acceptance Gate；
- 当前状态和时间戳；
- 风险等级、权限边界和升级条件。

### Artifact

描述“工作产生了什么”：

- 稳定 ID、类型和 schema 版本；
- 创建者、task 和 revision；
- 路径或 URI；
- 内容 hash、大小和生成时间；
- 消费者和兼容版本；
- 可复现方法与保留策略。

### Verification evidence

一种特殊 artifact，把测试声明绑定到事实：

- 被验证的 commit/tree hash；
- exact command 和工作目录；
- suite/version、选择器和测试数量；
- 环境指纹、依赖锁和关键服务版本；
- 开始/结束时间、duration、exit code；
- stdout/stderr 摘要与完整日志路径/hash；
- 通过、失败、跳过和未覆盖范围；
- 是否可缓存、失效条件和执行者。

### Handoff

把 task、artifact 和证据串起来：

- 从谁交给谁；
- 源 workspace、branch、revision 和 clean/dirty 状态；
- 变更摘要及设计理由；
- 已完成与未完成；
- 验证证据引用；
- 已知风险、阻塞和建议下一步；
- 接收方需要执行的最低确认。

## 消息的五种用途

第一版只规范以下意图，不创造新的网络 method：

1. **ASSIGN**：分配或修改 task，引用完整 task artifact。
2. **QUESTION / INPUT_REQUIRED**：缺失信息会实质改变结果，请求输入。
3. **STATUS / BLOCKED**：轻量进展、阻塞、预计下一事件。
4. **HANDOFF_READY**：产物已准备，引用 handoff 和 evidence。
5. **ACCEPT / REJECT / CANCEL**：接收、退回或停止，并写明判定依据。

消息正文建议不超过“足以决定下一动作”的长度。实现 diff、长日志、完整设计和测试报告一律放 artifact。

## 示例

```text
[HANDOFF_READY] task=PAY-142 context=checkout-v2
Outcome: card-token refresh implemented; targeted suite passed.
Revision: 8b2f...  Workspace: wt/payments-refresh
Artifacts:
  handoff: docs/artifacts/PAY-142-handoff.yaml#sha256=...
  evidence: artifacts/PAY-142-test.json#sha256=...
Risk: integration suite not run; requires API contract v3 consumer check.
Requested action: integrator validate evidence key, merge, then run affected-contract Gate.
```

这段文字对 Agent 可读，也让人能快速判断；真正的机器字段在引用文件中。

## 状态纪律

- `completed` 表示 worker 已完成输出 contract，不等于项目已接收。
- 项目层可另设 `accepted` / `integrated` / `released`，不要伪装成 A2A 标准 Task 状态。
- `input-required` 必须写明缺什么、为什么无法合理假设、谁有权回答。
- `failed` 要区分产品缺陷、环境失败、权限失败和任务定义失败。
- 状态消息到达不等于磁盘状态或 revision 已被验收。

## 可靠性原则

原生消息是控制信号，Git 与 hash artifact 是事实锚点。即使消息重复、延迟或任务被归档，接收方仍能用 task ID、revision 和 artifact hash 幂等恢复。
