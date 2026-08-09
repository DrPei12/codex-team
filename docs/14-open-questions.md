# 14. 开放问题

这些问题未被当前讨论完全解决。它们是后续研究和实验输入，不应被实现者静默猜测。

## P0：第一轮实现前必须回答

1. Codex 当前 `create/fork/handoff` 在 local checkout、managed worktree 和 permanent worktree 下的准确行为与失败模式是什么？
2. 第一批 skills 如何打包共享 schema/scripts，才能在安装后保持相对路径稳定又不复制大量资源？
3. Task、Artifact、Handoff 和 Evidence 采用哪个 A2A 版本及哪些字段；本地扩展如何命名与版本化？
4. 主编排者的项目状态存在哪里：单一 YAML/JSON ledger、Markdown 状态页，还是由 schema 生成两种视图？
5. 创建任务、发消息、等待、handoff、归档需要哪些最小权限和失败恢复？
6. Phase 1 用哪个真实仓库和任务作为纵向切片，什么结果算成功？

## P1：首个纵向切片中回答

1. 默认 active worker 数量的甜点区；何时需要分层编排者？
2. 主编排者和 worker 的模型/thinking 映射；当前实际可用模型名称是什么？
3. 何种结构化 brief 比长 prompt 更可靠，最小字段集是什么？
4. Evidence cache key 对不同语言、CI、数据库和外部服务需要多细？
5. affected tests 如何选择，证据错误时能否 fail closed？
6. Forked task 与 fresh/rehydrated task 在启动成本和错误继承上的差异？
7. 什么上下文健康指标能在明显性能下降前触发轮换？
8. 任务归档后 managed worktree 的安全清理如何确认？

## P2：扩展范式前回答

1. Hub-and-spoke 何时因主编排者瓶颈需要二级 coordinator？
2. Work queue 如何提供 lease、去重和 crash recovery？
3. Blackboard 如何避免并发写冲突和信息膨胀？
4. Competing prototypes 的统一 benchmark 如何防止选择偏差？
5. Maker-checker 是否需要不同模型、不同上下文或独立输入顺序来减少确认偏差？
6. 哪些项目可以安全自动 merge，哪些只能生成集成建议？
7. 如何量化 UI 冗繁、任务找回时间和用户认知负担？

## 暂不做的问题

- Claude Code 的对应体系和兼容策略；
- 跨平台 Agent adapter；
- 完整 A2A 网络互操作；
- 无边界自治发布；
- 在没有 telemetry 的情况下猜测 token 数据。

## 解决流程

每个开放问题关闭时应留下：来源或实验、原始证据、结论适用范围、被替代的假设、对应 decision ID，以及对 docs/schema/skills 的影响。
