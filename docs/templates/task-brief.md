# Task Brief — `<task-id>`

## Outcome

用一句可观察、可验收的话说明完成后什么为真。

## Why

说明用户价值和这项工作在项目依赖图中的位置。

## Scope

### In

- 必须完成的工作。

### Out

- 明确不做的工作。

## Workspace and ownership

- Workspace mode/path：
- Base revision：
- Branch：
- Owned modules/files：
- Forbidden/other-owner areas：
- Shared external resources and isolation：

## Inputs

| Artifact / spec | Version or hash | Read order / purpose |
|---|---|---|
|  |  |  |

## Contract

- Public interface/schema version：
- Invariants：
- Compatibility requirements：
- Forbidden changes：

## Required outputs

- Git revision or diff artifact；
- Handoff artifact；
- Verification evidence；
- Contract/documentation update（如适用）。

## Acceptance Gates

| Gate | Owner | Exact command/check | Evidence required |
|---|---|---|---|
| Targeted | Worker |  |  |
| Affected integration | Integrator |  |  |
| Full/release | Release owner or CI |  |  |

## Stop and escalate when

- 输入缺失会实质改变结果；
- 需要改变公开 contract；
- 会越过文件/模块所有权；
- 遇到破坏性或外部写操作；
- 测试失败无法用局部原因解释；
- 证据无法绑定准确 revision 或环境。

## Handoff target

- Receiver：
- Requested action：
- Archive/retain policy after acceptance：
