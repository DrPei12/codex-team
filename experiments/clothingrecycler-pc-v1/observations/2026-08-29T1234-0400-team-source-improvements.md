# Team T-001/T-002 源码修复快照

## 范围

用户授权在产品正式发布线并行改进 Team。本轮只处理 ClothingRecycler 已复现的两个 P1 控制面缺口：

- T-001：ownership 在 plan/integrate/recover 之间语义不一致；
- T-002：reviewer preflight 固定绑定 manifest base，无法审查 post-integration exact target。

没有修改当前安装 cache、marketplace、全局 skills 或产品仓库；没有宣称 live 修复已经部署。

## 模型与文件所有权

- 两条开发 lane 均请求 `gpt-5.6-luna/max`；effective 不可观测。
- T-001 owner：team-plan/integrate/recover runtime、manifest reference 和三组 tests。
- T-002 owner：team-run runtime/schema/skill/reference/test。
- 主任务使用高级模型做 source-contract review、语义校准、决策/状态同步和最终回归。

两个 worker 在代码和测试已落盘后长时间没有返回 final report；主任务确认相关测试进程结束后中断生成回合，保留共享 filesystem 改动，再独立审查和重跑。这个行为只证明 parent 能接管 durable filesystem state，不证明 subagent completion/report 可靠率。

## D-040：统一 ownership matcher

### 最终语义

- 裸仓库相对路径拥有该路径本身及所有后代；它可以表示现有文件，也可以提前声明尚未创建的 subtree root。
- 显式 glob 支持 segment-aware 匹配：`*`/`?` 不跨 `/`，`**` 可跨 segment。
- `forbidden_paths` 使用相同语义，并始终覆盖 `write_paths` allow。
- Windows `\` 规范化为 `/`，匹配大小写不敏感。
- `team-plan` overlap、`team-integrate` candidate、`team-recover` candidate 复用同一 matcher。

### 为什么没有采用“目录必须 `/**`”

`team-plan._path_patterns_overlap` 在 v0.1 已把裸 parent/child 当作 overlap；ClothingRecycler manifest 也用裸路径表达 subtree。若只让 integrate/recover 把裸路径视为 exact file，或只在 task project 中目录已经存在时拒绝，会继续漏掉“计划时目录尚未创建、worker 后来创建子文件”的真实 RED。

### 验证

- `test_team_plan.py`：23/23；
- `test_team_integrate.py`：17/17；
- `test_team_recover.py`：15/15。

覆盖裸 subtree、不同深度 bare/glob overlap、显式 `/**`、exact file、forbidden deny、越权和 Windows alias/case。

## D-041：Reviewer exact Gate target

### 最终语义

- Implementer/integrator preflight 继续绑定 manifest base。
- Reviewer dispatch argv 追加 canonical `--gate-receipt RUN_DIR/gate-receipt.json`。
- Reviewer preflight 验证 canonical dispatch argv、same run、manifest ref、schema/profile/kind、integrator manifest base、candidate ref/content/order/diff/ownership、真实 Git merge parents、apply before/after、passed Gate 定义/log/hash和 exact target。
- 当前 shared workspace 必须 clean，HEAD/tree 精确等于 Gate target；receipt 记录 `dispatch_ref`、`gate_receipt_ref` 与 `target`，`team-status` 再次复验 lineage。
- Missing/noncanonical/wrong-manifest/failed/different-Gate/fake plan-apply/single-parent fake merge/unplanned pre-merge base/missing-or-boolean order/wrong-head/tree/dirty/non-reviewer/tampered status 全部 fail closed。

### 验证

- `test_team_run.py`：26/26；
- `test_team_status.py`：20/20。

## 全量与 package 验证

- 九组 Team tests：130/130；
- 离线端到端：16 个 artifact schema validation 通过；
- `team-plan` / `team-run` skill quick validation：通过；
- 临时 relocatable plugin build：通过；
- bundle self-check：37 bundle files / 7 runtime entrypoints；
- D-042 后 authoritative 临时 build 版本：`0.1.1`；
- authoritative 临时 bundle manifest SHA-256：`384f230c70e74cb32f6466cbabe1d5a8a4443cacede68a1478b154d8c841e58b`。

Authoritative 临时包保留在：`C:\Users\lenovo\AppData\Local\Temp\codex-team-forward-b517777f19cd4febb9adc48d35286a17\codex-team`。它包含 strict boolean-order check、manifest-base binding 和 Git topology validation；三个 packaged marker 均为 true。较早包只保留为历史证据。第一次“构建后递归删除”命令被策略在执行前拒绝；后续只构建/验证、不删除，成功。没有 marketplace 或安装状态变更。

## 剩余边界

- 当前修订仍未提交。
- 当前 installed `codex-team 0.1.0` 没有被替换；旧 task/cache 是否热刷新仍未知。
- T-001 尚未用修正版对 ClothingRecycler 同类 manifest 做 live candidate forward test。
- T-002 尚未创建修正版 Desktop reviewer task。
- Capability-failure/evidence-only recovery、manual fallback、conditional live blocker/finish、Gate qualification 和 nested wrapper receipt 仍在 backlog。

## 独立复审

高级模型对当前 diff 做了五轮只读 adversarial review，先后发现并推动关闭：glob/bare overlap false negative、伪 plan/apply/Gate、自洽单 parent fake merge、未计划 pre-merge base、candidate order 缺失/boolean 绕过、forbidden deny、status 跨解释器误拒和 package 落后。最终裁定 `APPROVE`，未发现剩余 P0/P1/P2；只指出一个已修正的 D-040 限制文案 P3。
