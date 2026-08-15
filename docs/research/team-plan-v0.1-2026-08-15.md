# `team-plan` v0.1 实录

## 结论

本轮首次交付了可执行的 workflow skill，而不是继续补调查文档。`team-plan` v0.1 能把一个多任务工程计划写成 canonical manifest，机器检查 DAG、并行所有权、workspace、Reviewer 目标、Gate 和停止条件，再从同一 SHA-256 派生每条 lane 的 task brief。它成功后必须停止，不创建任务或实现代码。

当前成熟度是 `incubating`。一次 fresh forward test 生成了 1 份 canonical manifest 和 4 份 digest-bound brief，最终 validator PASS；但这仍是已见 OutputGuard failure corpus 上的显式 repo-local skill 测试，不是第二个 blind benchmark，也不证明 skill 比 no-skill 更快或更可靠。

## 产物

- `skills/team-plan/SKILL.md` 与 `agents/openai.yaml`
- `schemas/team-plan-manifest.schema.json`
- `scripts/team-plan.py`：`validate` 与 `project`
- `tests/test_team_plan.py`：19 项标准库回归
- 最终实现 commit `9254d1de74e19a62b3f3e71661f968812f3368aa` / tree `bd4eb2b32e66531f118ae504aeaa2a37a03f15b4`
- forward artifact：`D:\Desktop\Codex多任务工程系统实验场\runs\2026-08-15-team-plan-forward-02`

## RED：普通计划的真实失败

Baseline task `01a0057f-10ff-7c40-8340-b2e0810f3b47` 没有加载 `team-plan`。它给出了有价值的 Core/CLI/兼容性/Integrator 拆分，但出现三类问题：

1. 主动读取了 7 条历史 solution branch 和旧集成摘要，污染了 no-skill baseline；
2. 计划停留在长篇自然语言，没有 canonical identity、task/project/workspace 绑定或机器可验的 brief；
3. 单个只读计划回合运行约 506 秒，且需要父任务追加“立即停止勘察”的 follow-up。

因此这次 baseline 只进入 failure corpus，不能用于 skill 边际效用 A/B。公平对照必须使用独立 Git object store、审计可见 refs，并限制其他 skill/memory 泄漏。

代码侧先写 9 项失败测试；在实现不存在时得到 `0 passed, 9 failed`。系统 Python 和 Codex bundled Python 都没有 pytest，所以测试改为标准库自带 runner，而不是安装新依赖或把环境失败冒充 RED。

## GREEN：最小实现与第一次 forward failure

Implementation task `01a00587-df07-7483-9503-4e1df7bd8637` 只拥有 skill、schema 和 helper。首个 commit `02496da` 使 9/9 通过；主任务复核后启动 fresh forward task `01a0059d-15a3-7f91-8cef-1b6ec491d613`。

该 forward task 漏写 manifest 的 `objective`。Validator 返回：

```text
ERROR: manifest: missing required field(s): objective
```

它正确停止，没有生成 brief 或派发任务。这证明 fail-closed，但也暴露 skill 缺少“只修 manifest 后重跑 validator”的反馈环。

## REFACTOR：Reviewer 逼出的边界

独立 reviewer task `01a0059d-034a-7143-9128-a2440d72ee89` 没有因为测试通过而批准。四轮审查依次发现并验证：

- mutable workspace 可指向 saved task project；
- Reviewer 不必依赖 Integrator，也不能表达同一 exact workspace；
- Windows 大小写、`./` 和重复分隔符可绕过 ownership overlap；
- `project --out` 可写到 artifact root 外；
- task project、artifact root 和 lane workspace 的祖先/子孙或 symlink alias 可重叠；
- worktree root 可经 symlink 逃出 experiment root；
- 两条 lane 可用不同字符串指向同一物理 workspace。

每个 confirmed finding 都先进入新失败测试，再做最小修复。测试从 9 增长到 16、18、19；最终 commit `9254d1d` 只改变 `scripts/team-plan.py`，终审结果为 `approve`。

## 成功演示

Fresh task `01a005b5-5aa9-7581-918f-fd307003321a` 使用更新后的 skill，独立得出：Core 与 CLI 并行，Integrator 等二者完成，Reviewer 再只读审查 Integrator 的 resolved workspace。它首次 validate 即 PASS，然后生成 4 份 brief。

主任务用最终代码重验：

```text
PASS: run-manifest team-plan-forward-02
PASS: digest=sha256:da72149fd716f7c2284064dda3cc6ff7dd2232a77bbc1fddb06542283a5b4261; briefs=4; canonical_bytes=13511
```

目标 OutputGuard checkout 仍停在 `d235f59dcb7eb853043117402d3a1c8ef267b9af` 且 clean。没有创建实现 lane、没有访问 sealed evaluator、没有实现功能。

## 使用方法

```text
python scripts/team-plan.py validate MANIFEST
python scripts/team-plan.py project MANIFEST --out ARTIFACT_ROOT/briefs
```

`project` 先重新 validate；输出目录必须为空且位于 manifest 声明的 artifact root。每份 brief 携带 canonical manifest digest，后续 `team-run` 只能消费这些机器派生结果。

## 尚未证明

- Windows symlink 已实测，junction 未现场实测；
- 没有验证安装后 shared schema/helper 的相对路径；
- 没有验证 implicit trigger、版本不匹配或其他模型；
- requested model/thinking 是 `gpt-5.6-luna` + `max`，effective 值未暴露；
- 没有实际 dispatch、handoff、integration 或 finish；
- no-skill baseline 已污染，不能计算提升比例；
- OutputGuard 已见，主要效用结论必须等待第二个 blind benchmark。
