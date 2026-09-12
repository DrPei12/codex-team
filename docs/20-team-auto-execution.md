# Team Auto：里程碑 1–5 执行记录

状态：里程碑1–5已完成本地验收（2026-09-12），到此停止。源基线 d3e3589；开发分支 codex/team-auto-m5。实验创建的 Session/Subagent 请求 gpt-5.6-luna / max。请求配置、服务返回配置、模型重路由和不可观测项分别记录。

用户追加约束：Team不绑定第三方Skill或插件（包括Open Design）。核心执行、协作、状态、看板和验收只使用Codex原生能力、Team自身代码和标准库。项目可选业务工具的缺失只能影响对应项目能力，不成为Team核心依赖。开发时查询资料或使用本机开发工具不等于为产品增加运行依赖。

## 本轮范围和停止点

完成能力实测、可观察运行骨架、Auto→方案→Run→检查点、协作/纠偏/恢复、真实工程验收。到里程碑5停止。发布、对照收益证明和正式安装升级属于里程碑6；本轮准备可移动产物但不对外发布。已有用户工作区与历史失败不被覆盖。

## 实施决策

新增独立的0.2 Auto运行协议，保留0.1.x legacy流程和回归。新协议将需求、版本化方案、运行、工作包、执行尝试和会话身份分开。轻量控制程序使用Python标准库；单机SQLite保存事务状态与追加事件，Markdown保存规范和决策，独立artifact保存证据；本地HTTP看板消费同一状态。Codex执行只使用已安装官方App Server的stdio协议，通过现有Codex认证；不创建API key，不写Codex内部数据库。

App Server属于有版本边界的实验接口。通过当前binary生成schema并实测后才登记observed。新协议允许App Server执行，替代D-023对本轮0.2范围的Desktop-only限制；不把App Server会话等同于Desktop侧栏任务。D-022/D-032的纯skills范围在0.2扩展为Codex专用薄控制层；旧实验解释不变。

授权绑定方案digest、目标检查点、允许根目录、动作和资源。默认实验策略由本轮明确选择，并非产品通用阈值。控制层不代替环境强制审批。普通调试与预期RED有有限attempt预算；身份/权限/证据冲突立即停止。可逆局部假设可以披露后推进；目标/验收/风险取舍需用户决定。零代码失败可以进入恢复。

## 里程碑追踪

|里程碑|状态|证据|
|---|---|---|
|1 基线与能力|关键能力已观察，版本受限|protocol-selected/及capability-*.json；实际0.153.0，9月8日恢复为0.153.4|
|2 运行骨架与看板|已完成本地验收|team_runtime/，真实SQLite、故障回归与浏览器检查|
|3 Auto到检查点|首条真实闭环已完成|CheckCSV run-4a725206cf37与exact commit 9ef3dc3|
|4 协作纠偏恢复|关键链路已实测|LabLedger跨会话请求、纠偏、WP2责任接替及两次跨日reconcile；9月12日补恢复状态回归|
|5 真实工程验收|已完成|LabLedger 4663e17e，原生G1/G2/G3、真实浏览器、独立Luna/max审查通过；受托操作者接受，最终本地交付见验收记录|

当前工作导航见[工作笔记](work-notes/team-auto-m5.md)，最终证据与限制见[里程碑5验收记录](22-milestone5-acceptance.md)。核心决策D-058至D-068已纳入决策日志。此前预算暂停和未完成审查仍作为历史保留。

实验根目录：D:/Desktop/Codex多任务工程系统实验场/runs/2026-09-05-team-auto-m5。

## 开发所有权

主任务：team_runtime/codex.py、engine.py、cli.py、__main__.py、协议/项目文档、集成与真实验收。
状态worker：team_runtime/store.py及tests/test_auto_store.py。
界面worker：team_runtime/board.py、team_runtime/static/及tests/test_auto_board.py。
其他文件只有重新明确分配后才能由worker修改；共享接口以docs/21-team-auto-contract.md为准。

## 验收原则

运行必须真实调用Codex；测试替身仅用于故障和边界单测。真实案例要覆盖单会话选择、多会话独立实现、协作请求、纠偏、暂停/接替、集成与独立审查，并说明哪些是注入故障。用户链路和产物行为独立验收，不用进程active或worker自报替代。控制程序重启必须恢复事实、不重复派发；暂停显示请求与确认，后台命令是否停止独立记录。长期可靠性、睡眠期间继续执行和多任务优势不预宣称。
