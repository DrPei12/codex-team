# Security Policy

## Supported versions

当前仅维护最新公开版本。历史 releases用于复现与审计，不承诺安全更新。

| Version | Supported |
| --- | --- |
| 0.1.4 | Yes |
| 0.1.0–0.1.3 | No |

## Reporting a vulnerability

请使用 GitHub 仓库的 **Private vulnerability reporting / Security advisory** 提交安全问题，不要在公开 issue、discussion、PR、日志或截图中粘贴密钥、Authorization header、credential、真实业务数据或可利用细节。

报告应包含：受影响版本/commit、最小复现、影响边界、是否需要网络或用户授权、已观察与推测的区分。收到报告不代表漏洞已确认；维护者会先验证 candidate finding，再决定修复与披露。

## Scope

优先关注：

- manifest/receipt/hash 身份绕过；
- ownership、forbidden path 或 symlink/junction逃逸；
- secret进入artifact、prompt、日志或发布资产；
- 未授权 task/Git/cleanup 外部副作用；
- reviewer/Gate target混淆；
- plugin bundle完整性检查绕过。

模型输出质量、未承诺的长期scheduler能力和第三方Codex平台本身的问题不自动属于本仓库漏洞，但可作为边界报告。
