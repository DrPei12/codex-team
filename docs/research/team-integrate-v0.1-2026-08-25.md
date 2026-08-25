# `team-integrate` v0.1 有序集成实录

## 结论

`team-integrate` v0.1 已实现“精确候选 → 有序计划 → 显式授权合并 →
显式授权 Gate”。它把 worker report、evidence、preflight receipt、commit/tree
和变更文件绑成 integration candidate，再按 manifest `integration_order`
生成计划。

当前成熟度为 `incubating`。实现在临时真实 Git worktree 中验证了合并
与 Gate 回执，但没有从真实 Codex task 收集 handoff，也没有自动 push、
sealed evaluation 或远程集成。

## 流程与边界

1. `candidate` 校验当前 run 的 manifest、preflight、report/evidence hash、
   lane workspace、base/HEAD/tree、ordinary cleanliness 和 write ownership。
2. `prepare` 只接受 `handoff-ready` 或 `accepted` lane，拒绝同一文件的
   跨 lane 重叠，按 manifest 顺序生成不可覆盖的 plan。
3. `apply` 必须显式给出 `--allow-git-mutation`，并在合并前重验
   plan/candidate bytes、commit/tree、integrator base 和 clean state。
4. `run-gates` 必须显式给出 `--allow-command-execution`，把每条命令、
   exit code 和 log hash 绑到 exact target，第一个非零立即停止。

该 skill 不创建任务、不安排 sealed evaluator、不 push，也不把
worker 的“完成”声明当作主编排者验收。

## 回归证据

实现 commit `93a6d4d5d99d626779e6a7f4fd6146d8e042e8c8` / tree
`d83dca9a7b152cfeee69afe60b31a13eb37ed74f`。`tests/test_team_integrate.py`
结果为 `12 passed, 0 failed`，覆盖候选身份、越权变更、dirty workspace、
状态条件、顺序、plan 篡改、授权旗标、真实临时 worktree 合并、
exact target Gate 和 first-nonzero stop。五份生成产物通过 Draft
2020-12 schema 校验。

## 尚未证明

- 没有真实 Codex handoff/message 时序与跨任务长期可靠性；
- 没有验证复杂 rename、submodule、LFS、超大二进制文件或长合并队列；
- 没有证明自动合并比人工串行接收更快或更稳定。
