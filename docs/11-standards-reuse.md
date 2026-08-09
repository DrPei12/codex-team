# 11. 成熟标准复用

## 原则

优先复用成熟标准的语义和格式，但只引入能解决当前问题的部分。标准越完整，实施和维护成本越高；“兼容某标准”必须写清兼容到哪一层。

## A2A

### 直接复用

- Agent/能力描述的思想；
- Task、`contextId` 和任务生命周期；
- Message、Part、Artifact 的分离；
- input-required、completed、failed 等状态语义；
- 异步长任务和 artifact 导向的交互方式。

### 本项目扩展

- Git revision、branch、worktree 与所有权；
- 工程验收、test evidence 和 cache key；
- 模型/thinking、上下文健康和 task lifecycle；
- 集成、接收、发布等项目控制平面状态。

### 第一版明确不做

- 不实现独立 A2A server/client；
- 不要求 Agent Card 服务发现；
- 不新增 HTTP、JSON-RPC 或 gRPC 传输；
- 不声称 Codex 原生消息满足 A2A 全部 wire-level conformance；
- 不把本地扩展字段说成 A2A 标准。

## Git

Git commit/tree hash 是代码状态锚点；branch/worktree 提供隔离；merge/rebase/cherry-pick 提供集成机制。Git 不能表达任务意图和测试有效性，因此还需要 task 和 evidence artifact。

## JSON Schema

用于验证 task、worker card、handoff 和 evidence 的结构、枚举和版本。YAML 模板应能转换为同一数据模型，避免 YAML 与 JSON 两套语义。

## OpenAPI

当 worker 通过 API 契约并行开发时，直接使用 OpenAPI 描述接口，而不是把 endpoint 约定重新写进任务消息。OpenAPI 只覆盖接口形状，业务不变量仍需 spec 和 contract tests。

## 原生测试报告

优先采集 JUnit XML、TRX、pytest JSON、coverage、Playwright report 等框架原生产物，在 evidence envelope 中引用。不要把所有日志解析成自创格式后丢掉原始证据。

## SARIF

静态分析和安全扫描可用 SARIF 表达 finding、位置、规则和严重性，便于跨工具汇总。并非所有测试都应转换为 SARIF。

## in-toto / SLSA（后续候选）

当项目需要更强供应链证明时，可以借鉴 in-toto 的 layout/link 和 SLSA provenance，把“谁在什么输入上运行什么命令产生什么输出”签名化。第一版不需要承担完整签名基础设施。

## OpenTelemetry（后续候选）

可以用 trace/span 关联主任务、worker、工具调用、测试等待和 handoff，以测量 wall time、并行度、返工和瓶颈。只有在 telemetry 能稳定获取且隐私边界明确时才接入。

## 采用标准的验收条件

每次引入一个标准都要回答：

1. 它替代了哪段自定义设计？
2. 采用的是语义、schema、传输还是完整 conformance？
3. 当前 Codex 工具能否原生携带？
4. 给 worker 增加多少上下文与实现负担？
5. 如何版本化和迁移？

若收益只是“听起来规范”，而没有提高互操作、可验证性或工具复用，就不应进入核心路径。
