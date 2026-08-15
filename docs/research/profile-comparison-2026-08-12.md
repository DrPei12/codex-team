# 2026-08-12 Worker Profile 对照

> 历史证据说明：本报告比较的是 CLI profile。D-023 之后它不定义 Desktop task 的启动方式；这里只保留“不要粗暴删除执行规则”和“配置必须在真实 task 内验证”两项风险提示。

## 结论

测试的 minimal 启动方式不能采用。它没有让 worker 更轻，反而移除了必要的执行规则，导致 verifier 无法运行；同时 skills 仍被发现和注入。

在同一 fixture、相同 prompt、相同只读 sandbox 和相同默认模型下：

| 条件 | 是否完成任务 | Input tokens | 非缓存 input | 回合耗时 |
|---|---:|---:|---:|---:|
| 正常配置 | 是 | 42,231 | 12,023 | 43.3 秒 |
| `--ignore-user-config` + 禁用 memories/plugins/skill_search | 否 | 219,179 | 32,555 | 91.5 秒 |

minimal bundle 的总输入约为正常配置的 5.19 倍，非缓存输入约 2.71 倍，耗时约 2.11 倍；而且固定 verifier 被 execution policy 拒绝。低 token 预期被直接否定。

## 为什么失败

- `--ignore-user-config` 不只移除上下文偏好，也移除了当前环境中允许正常只读命令执行的规则；
- Agent 遇到拒绝后不断拆分和改写命令，造成更多调用和上下文；
- 禁用 `memories`、`plugins` 和 `skill_search` 仍没有阻止 skills loader 扫描已安装 skills；
- 因此“关掉更多功能”等于“更少上下文”的前提不成立。

## 能说什么，不能说什么

可以说：这个四项组合在当前 Windows/CLI `0.146.0`、固定 fixture 和单次配对实验中不安全且更贵。

不能说：所有 minimal profile 都无效，或单独某一个 flag 必然造成失败。本轮同时改变了四项设置，且只有一对样本，不能拆出因果贡献。

## 架构影响

- worker bootstrap 必须保留已验证的 execution policy；
- 上下文裁剪不能从 `--ignore-user-config` 开始粗暴清空；
- 下一次只改变一个来源，优先调查“是否能限制 skill/plugin discovery，同时保留 auth、rules 和 sandbox”；
- 每个 profile 变体都必须通过相同 verifier，token 更少但任务失败一律不算优化。

本地计划与结果保存在 `D:\Desktop\Codex多任务工程系统实验场\runs\2026-08-12-profile-compare-01`。结果 SHA-256：`c9f7be7015908cacaca5272e0bcb944d7a21433e2167765f0327b70855e009db`。
