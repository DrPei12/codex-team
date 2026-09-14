# Team Auto当前工作笔记

最后核对：2026-09-14。本笔记只保留当前导航；原始历史在SQLite追加事件、artifact及Git历史中，避免连续压缩摘要。

## 当前结论与停止边界

用户已提供[新版方向定义](../23-project-definition-v0.2.zh-CN.md)，并补充[四项方向修订](../24-direction-update-2026-09-14.md)：启发式选择澄清、跨领域委托及联网查证、自主性与约束平衡、Plugin交付。当前进入定义与设计更新，原模型实验保持停止。先依据D-070及新版要求重新映射实现和验收，不直接沿旧发布路线推进。

已完成的里程碑1–5作为保留基线：源码提交a911dbdc8643efc5bbb319dbbca8c574cff369bc，主项目与实验开发工作树在暂停前均无未提交修改。前轮账户用量观察为9%→14%，5个百分点预算已结束，不自动沿用。

仅Codex；Team核心不绑定第三方Skill/插件。当前实验Session及Subagent统一gpt-5.6-luna/max，主任务保持宿主模型。旧模型和失败记录不追溯改写。

## 可直接使用的成果

- 0.2 Auto控制程序、中文看板、SQLite状态/租约、协作请求、方向审查、暂停恢复、责任接替、工作笔记与原始历史检索。
- CheckCSV run-4a725206cf37：completed，commit 9ef3dc3acb638501d46d7644f8ad64060200266c。
- LabLedger run-9bf498c1547abacf211c942a：completed，commit 4663e17ef8536b489f0fdaf6b41b3e9d9c9e9d79；G1/G2/G3和真实浏览器通过，最终审查review-46e5615928a8.json为approved。接受者是delegated-operator，非用户亲自点击。
- 交付与回归结果见[里程碑5验收记录](../22-milestone5-acceptance.md)。协议和边界见D-067/D-068。

## 原始检索入口

实验根：D:/Desktop/Codex多任务工程系统实验场/runs/2026-09-05-team-auto-m5。
控制状态：small-state/team.sqlite3。使用team-auto.py的snapshot、notes、history读取，不手工编辑数据库。

- CheckCSV：snapshot run-4a725206cf37。
- LabLedger：snapshot run-9bf498c1547abacf211c942a；history run-9bf498c1547abacf211c942a 400。
- 原始证据：small-state/artifacts/<run-or-plan-id>/；capability-*.json；原生project/import/read回执。
- 本次Gate：gate-11614b652ac8.json、gate-670b983218b1.json、gate-3ec5f70cb31a.json。
- 最终审查原生thread 01a09573-5466-7ec3-941e-6fe1bda3c0a2，turn 01a09573-55db-7d51-bffd-f3ace7181f1e；completed事件#539，检查点#540。
- 浏览器：output/playwright/ui-verification-20260912.json及桌面/手机PNG，原始事件#470绑定候选commit和hash。
- 接受：m5-labledger-accepted.json；四个测试残留保存回执native-test-residue-preservation.json。残留仍保留在集成目录.team-temporary/preserved-test-residue-20260912，无用户数据删除。
- 上轮暂停：事件#475/#476及Git e7e2100中的本工作笔记，保留其未完成审查结论。

## 后续恢复时先核对

当前无继续耗用模型的实验。不要重做已完成产品或重复同一target有效验收。0.154.0-alpha.6.2及Python 3.12.14是本次验证环境；升级后重新资格化。原生历史tokens不完整，账户用量包含其他任务，不能当精确成本。Desktop侧栏、跨环境及长期可靠性尚无保证。
