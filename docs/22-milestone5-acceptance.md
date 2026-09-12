# 里程碑5验收记录

2026-09-12：里程碑1–5已完成本地验收，0.2.0仍为incubating。依据用户“完成里程碑5”委托记录delegated-operator接受；没有声称用户本人亲自查看页面。到此停止，里程碑6未启动。

## 真实工程证据

|实验|最终源码|验收结果|
|---|---|---|
|CheckCSV 单会话|9ef3dc3acb638501d46d7644f8ad64060200266c|completed，真实CLI、12项测试、原生沙箱Gate及独立Luna/max审查通过|
|LabLedger 双会话|4663e17ef8536b489f0fdaf6b41b3e9d9c9e9d79|completed，G1/G2/G3分别6/5/11项通过，独立审查11条要求全部满足|

LabLedger实际完成跨会话接口提问与答复、纠偏、暂停恢复、WP2责任接替、集成、最终审查和受托接受。冻结CONTRACT.md未改。最终审查为review-46e5615928a8.json，原生模型gpt-5.6-luna/max，回合completed事件#539。

Edge实际验证中文资产新增、运行记录、筛选、历史、JSON下载及刷新持久化，桌面1440和手机390视口检查通过；没有脚本注入或page error。看板笔记和原始历史检索已操作，长请求ID窄屏溢出已修复。原始证据为实验根output/playwright/ui-verification-20260912.json及PNG，绑定同一候选提交。

## 控制程序与交付

本轮engine+codex回归99项通过；修复后engine整组76项通过，最终补丁相关28项通过（JUnit原始回执final-fix-regression.xml）。集合有重叠，不相加。测试使用真实SQLite/Git/子进程，原生模型在单测中明确使用测试替身；上述两个真实工程实验补足实际Codex调用证据。

独立源码审查提出三个P2，已修复并加入回归：恢复后用量低估、ignored文件漏过范围检查、blocked工作包无法恢复。Git目录读取警告现会阻塞验收。已验证为本实验生成的四个SQLite测试目录通过原有原生沙箱保存在.team-temporary/preserved-test-residue-20260912，没有删除或放宽权限。

本地交付：实验根delivery-m5/codex-team-0.2.0-m5.zip及SHA256SUMS，构建和bundle-self-check均通过。核心只有Codex原生能力、Team自身代码和Python标准库，不绑定第三方Skill/插件。源协议、决策D-067/D-068、当前状态与工作笔记已同步。

[机器可检索证据索引](../evidence/experiments/2026-09-12-team-auto-m5.json)列出实验、精确提交、artifact路径与SHA-256。实验根为D:/Desktop/Codex多任务工程系统实验场/runs/2026-09-05-team-auto-m5。工作笔记提供最新导航，SQLite追加事件及原始artifact保存历史，不对摘要反复压缩。

## 预算与验证边界

本轮账户本周已用从9%到停止观察的14%，达到5个百分点预算边界，停止追加模型工作。读数为共享账户且有粒度，不能当作本任务精确费用。原生历史tokens存在缺口，保留legacy标识，不事后推算。

验证环境为Windows、Codex 0.154.0-alpha.6.2与资格化Python3.12.14。Desktop侧栏项目展示、跨环境兼容、长期无人值守稳定、多会话普遍收益仍未得到证明。正式公开发布、全局安装升级及收益对照属于后续里程碑6。
