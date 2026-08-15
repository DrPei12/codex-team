# 2026-08-15 OutputGuard Desktop 纵向切片实录

> 状态：`observed — one accepted recovery lineage`  
> 对应机器记录：[实验 evidence](../../evidence/experiments/2026-08-15-outputguard-vertical-slice.json)  
> 本地原始 artifact：`D:\Desktop\Codex多任务工程系统实验场\runs`

## 先说结论

这轮终于跑通了一个真实结果：同一个精确 Git tree 先通过公开测试、格式、类型和离线构建，再由新的 Reviewer 审查，最后只运行一次 sealed evaluator，`37/37` 通过。

但这不是“一次四任务从头顺滑跑到底”。最终结果来自一条保留所有失败现场的恢复链：Run02 到 Run09 先后暴露了实现缺陷、父任务编排错误和评测脚本缺口；Run10 复用 Run07 已验收的 CLI commit 和 Run09 被精确冻结的 Core candidate，再创建 Core recovery、Integrator、Reviewer 三条 Desktop 任务完成收口。这个区别很重要：我们证明了“这套手工治理方法能够诚实停止、携带证据恢复并最终交付”，还没有证明“未来每次都能四任务一次成功”。

## 评测对象和反作弊边界

固定任务是 `ndcorder/outputguard` 的 JSONL streaming 功能。上游 commit、公共 scaffold、公开 contract、解释器和 evaluator hash 都在实现前冻结。实现任务禁止联网、安装依赖、读取 evaluator vault、读取其他 dirty worktree 或从 GitHub 检索现成实现。sealed 内容只允许父编排任务在公开 Gate 和独立 Reviewer 都通过后执行一次。

原始实现与评测均在独立实验场完成，主项目仓库只保存研究结论和可移植的 evidence 摘要。完整固定输入见 [纵向切片计划](../19-outputguard-vertical-slice-plan.md)。

## 实际发生了什么

| Run | 结果 | 得到的新事实 | 为什么停 |
|---|---|---|---|
| 02 | `blocked` | 集成实现的实质公开命令全部通过 | 父任务 final-boundary helper 错把精确的一字节 `dist/.gitignore` 判成污染 |
| 03 | `changes_requested` | 修正 helper 后，同一 tree 的 public recovery 通过 | 新 Reviewer 找到 high R-001：自定义格式值可能不能 JSON 序列化 |
| 04 | `blocked_core_format_gate` | Core 逻辑测试 22 通过；CLI RED commit 可复用 | 把 formatter 的可修复输出当成 check-only 硬停止，Core 未提交 |
| 05 | `blocked_diff_hash_algorithm_ambiguity` | 各文件 hash 相符 | 聚合 diff hash 没冻结唯一字节生成算法，无法安全转移 dirty candidate |
| 06 | `changes_requested` | canonical recovery、集成和完整 public Gate 通过 | Reviewer 又找到三个 high：R-002 数值溢出 ID、R-003 surrogate/UTF-8、R-004 decoder `RecursionError` |
| 07 | `blocked_core_preflight_false_negative` | 独立真实 CLI RED contract commit `c8d874e` 被验收 | Core 自由文本 preflight 报 mismatch 且没有证据；父任务事后看到文件身份匹配，具体失效机制未知 |
| 08 | `blocked_parent_preregistration_hash_error` | canonical helper 51/51，通过且零写入；worker 正确 fail closed | 父任务手工抄错两个 preregistration hash |
| 09 | `blocked_green_basetemp_parent_absent` | outer manifest 66/66；RED 为 24 通过、7 个预期失败；三文件 candidate 被精确冻结 | 父任务要求 artifact root 初始不存在，却传入其下层 `--basetemp`；pytest fixture 出现 20 个 `FileNotFoundError` |
| 10 | `completed_passed_with_sealed_ignored_residue` | exact candidate、集成、review、sealed 全部通过 | 功能不再阻塞；sealed 子进程留下 29 个被 Git 忽略的 `.pyc`，所以不能声称评测目录完全无残留 |

失败 run 没有被改名成成功，也没有用后续结果覆盖。每次恢复只回答一个新问题，例如“修正 metadata 规则后原 tree 是否通过”“精确 dirty candidate 在预创建 artifact root 后是否通过”，而不是把整套昂贵 Gate 机械重跑一遍。

## 最终接受的精确结果

最终集成身份：

- CLI commit：`c8d874e43eeb4b680d7f3c3d7be4b6c41a72ef4a`
- Core commit：`cde55924f8c0fc92074d352fd54c8607a0485808`
- final commit：`b67c8e361ff72b1c75a2d0988acf126c81d71d93`
- final tree：`41de9670e0e9358fa7090e336ec2b561e139febb`
- 最终变更路径：`outputguard/cli.py`、`outputguard/jsonl.py`、`tests/test_jsonl.py`、`tests/test_jsonl_cli.py`

Run10 的实际 Gate：

1. Core recovery：同一 candidate 不再改源码，`59 passed`；Ruff format/check、mypy 和 `git diff --check` 通过，随后只提交一次。
2. Integrator：按实际顺序先合并 CLI、再合并 Core；affected tests `64 passed`。
3. 完整公开 suite：`2093 passed, 28 skipped`。
4. Ruff format：93 files；Ruff lint 通过；mypy 29 source files 通过。
5. 离线 build：一份 wheel 和一份 sdist，cache digest 保持冻结值。
6. Reviewer：R-002、R-003、R-004 全部关闭；critical/high/medium 为 0，保留 1 个 low finding。
7. Sealed evaluator：父任务只执行一次、无重试，`37 passed in 1.18s`，exit 0。

父任务没有重复 Integrator 已完成的 public Gate。接收动作只复核 commit/tree、父子关系、精确 blob、artifact bytes/hash、schema、dist、cache 和工作区边界。这里的“避免重复”不是相信 worker 自报，而是接收 proof 后只运行合并产生的新事实所需 Gate。

## 仍然存在的限制

第一，Run09 的 RED 摘要没有原始 pytest log artifact。它与精确 candidate 身份绑定，但证据等级仍低于原始日志；Run10 没有为了补齐形式而重跑 RED。

第二，Reviewer 保留 low L-001：安全检查和最终 record 序列化对同一个由调用方持有的 `ValidationResult` 做了两次投影。如果该对象的自定义值有状态或并发突变，两次结果可能不一致并导致 fail-closed 中止。它不允许 malformed record 泄漏，且不是本轮 repair 新引入，所以不阻塞当前 contract，但后续要决定是否冻结一次投影或明确对象稳定性要求。

第三，sealed evaluator 的子进程生成了 29 个 ignored `.pyc`：`outputguard/__pycache__` 13 个、`outputguard/strategies/__pycache__` 16 个。普通 `git status` 是 clean，commit/tree 未变，但 “ignored clean” 为假。现场留在隔离 worktree，没有静默删除。这是 evaluator harness 清洁性问题，不是本轮产品正确性失败。

第四，这只是一次恢复链成功。它没有给出可靠率、并发上限、token 节省、速度收益或多任务相对 single 的优势。模型 effective 配置也没有被 Desktop 完整暴露，仍记为 `unknown`。

## 这轮真正告诉我们的东西

最频繁的失败不是“worker 不会写代码”，而是控制面把同一个事实抄进多个文件、给出不完整的运行目录前置条件，或者把可变操作和验收检查混在一起。反过来，独立 Reviewer 的价值也很清楚：两次 public Gate 通过以后，它仍分别发现了 R-001 和 R-002/R-003/R-004；不能用“测试绿了”替代审查。

因此第一批 skills 的核心不该是更多角色名称，而应是一个可靠的证据骨架：

1. 一个 canonical run manifest 拥有 revision、hash、路径、命令和预算；brief、preregistration、freeze 文件只从它机器生成，不能手抄重复身份。
2. task 创建前先运行 parent preflight；task 开始后再运行 worker preflight，两边都输出机器可读结果。
3. `team-run` 在派发前创建并验证 artifact/cache/test 根目录，不能只在文字里假定它们存在或不存在。
4. formatter apply 这类预先授权的变更步骤与 formatter check 分开；check 仍在第一个非零时停止。
5. `team-status` 维护 append-only timeline 和明确的 blocked 原因，不把后继 recovery 写回旧 run。
6. `team-integrate` 验证 evidence identity 后只运行新事实需要的 affected/integration Gate；sealed 仍由父编排者单独授权。
7. `team-finish` 分别检查 ordinary、untracked、ignored、operation residue 和 run-local artifact，发现残留就记录，不默认清理。
8. `team-recover` 已经具备独立触发价值：它接收 blocked run、精确 candidate、尚未满足的单一事实和新的预算，禁止顺手重写历史或扩大修复范围。

## 研究路线怎么改

OutputGuard 现在适合作为开发 trace 和 failure corpus，用来实现 schema、validator、preflight、recovery 和 finish audit；它不再适合作为证明 skills 泛化效果的唯一任务，因为我们的流程已经针对它暴露过的坑做了学习。

下一阶段先把上述机制实现为最小 incubating workflow，再冻结实现。随后选择第二个未见过的公开仓库与可客观验收功能，使用新的 Git object store，确保 baseline 看不到 OutputGuard 或其他 lane 的 solution refs。第二 benchmark 才承担 no-skill/native single 与 skill-assisted workflow 的主要边际效用比较。

OutputGuard native single 仍可补做，但必须使用不含本轮 solution objects/refs 的新仓库、独立 Desktop project、冻结 prompt、零 follow-up 和相同 public/sealed Gate。因为执行顺序和主编排者知识已经受本轮影响，它只能作为带污染风险的补充对照，不能单独支撑“多任务更优”的结论。

## 下一步

先做 schema/validator v0.2 和共享 deterministic helper，不继续给 OutputGuard 随便加功能：canonical manifest、artifact-root preflight、proof-carrying recovery、Gate receipt、ordinary/ignored cleanliness audit。然后用这条完整 failure corpus 驱动 `team-plan`、`team-run`、`team-status`、`team-integrate`、`team-finish`，并把 `team-recover` 提升为首批入口候选。所有实现先标 `incubating`；在第二个 blind benchmark 与 no-skill baseline 完成前，不晋升 `stable`。
