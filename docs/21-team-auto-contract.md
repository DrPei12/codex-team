# Team Auto 0.2：模块集成契约

适用版本说明（2026-09-14）：本页继续描述已有0.2实现；固定proposal、工程Gate及原协作行为不代表新版目标。新设计见[自适应执行](25-adaptive-execution-design.md)及[验证与迁移](26-execution-validation-and-migration.md)，实现迁移前不得据新设计改变旧记录语义。

这是本轮实现共享接口，修改由主任务拥有。全部代码Python 3.12标准库，包team_runtime。无跨平台agent抽象。

## Store

`Store(path: str|Path)`创建/打开SQLite数据库，独立连接按操作使用，支持HTTP线程并发。方法：

- `put(kind, entity_id, data: dict, *, expected_revision: int|None=None) -> dict`：创建时expected_revision=None只允许不存在；更新必须给当前revision。返回 `{id, kind, revision, data, updated_at}`。冲突抛`ConflictError`，不得覆盖。
- `get(kind, entity_id) -> dict|None`；`list(kind) -> list[dict]`按更新时间返回。
- `append_event(run_id, event_type, payload:dict, *, dedupe_key:str|None=None) -> dict`；相同run+dedupe_key返回原事件，不重复写入。结果`{seq,run_id,type,payload,created_at}`。
- `events(run_id, after:int=0, limit:int=500) -> list[dict]`。
- `tail_events(run_id, limit:int=500) -> list[dict]`：返回最近事件，按seq正序；看板不会永久停留在前500条。
- `claim(resource, owner, *, ttl_seconds:float=60) -> bool`：原子排他租约，可由同owner续租；`release(resource,owner)->bool`只释放本owner；用于controller进程领导权和工作包claim。
- `close()`不删除任何数据。

所有JSON为UTF-8，data完整保留，不秘密缓存凭据。表及索引内部实现由状态worker决定。必须验证重开持久、并发CAS、幂等事件、租约过期与错误owner释放。时间字段ISO UTC字符串，租约内部可用epoch。

## Engine（主任务实现）

`Engine(state_dir: str|Path)`包含`store`。界面只调用以下公开方法：
- `snapshot(run_id:str|None=None)->dict`：`{plans:[envelope],runs:[envelope],events:[...],capabilities:dict}`。指定run时只返回相关运行/事件。plan.data至少含brief,repository,status,questions,proposal,digest；run.data至少含plan_id,status,packages,checkpoint,limits,created_at。额外字段允许。
- `propose(repository:str, brief:str, *, answers:dict|None=None, policy:dict|None=None)->dict`：真实模型澄清/生成plan，返回Store plan envelope。可能需数分钟。
- `approve(plan_id:str, expected_digest:str)->dict`：冻结授权并创建run，返回run envelope，尚不执行。digest不匹配抛ValueError。
- `start(run_id:str)->dict`：启动后台运行，返回run envelope；幂等，同一run不重复派发。
- `pause(run_id:str)->dict`、`resume(run_id:str)->dict`、`cancel(run_id:str)->dict`。
- `reconcile(run_id:str)->dict`：无有效运行owner时，保存原状态、核对原生idle及空背景终端和源码快照；原Run及未完成running/blocked工作包转paused。保留会话、回合及回执，不推断离线完成；范围冲突未解决时仍拒绝恢复。
- `requalify(run_id:str)->dict`：停止态重新资格化已更新解释器，保留旧绑定与验收证据。
- `supervise(run_id:str)->dict`：停止态独立方向检查，结果是on-track/correctable/needs-user，不能代替最终验收。
- `replace_session(run_id:str, package_id:str, reason:str)->dict`：校验旧原生中断回执、笔记和当前源码后准备交接；新Session首轮派发验证快照，后续合法修改后的resume不再与最初交接快照比较。
- `get_note(run_id:str, package_id:str)->dict|None`、`search_history(run_id:str, query:str, *, package_id:str|None=None, limit:int=20)->dict`：当前工作笔记和有界原始历史检索。
- `steer(run_id:str, package_id:str, message:str)->dict`：当前执行owner可直接纠偏，跨进程或停止态则持久排队，由执行owner投递。
- `amend_limits(run_id:str, policy:dict, expected_digest:str)->dict`：停止态版本化修订资源，保留先前方案及证据。
- `request_collaboration(run_id:str, from_package:str, to_package:str, question:str, *, request_id:str|None=None)->dict`：返回request envelope。
- `resolve_request(run_id:str, request_id:str, answer:str)->dict`。
- `accept_checkpoint(run_id:str, expected_digest:str, *, actor:str='user')->dict`：按当前证据digest接受，不进入下一阶段。actor只允许user或delegated-operator；后者仅在调用者已有明确委托时使用，记录operator_accepted_at，不声称用户亲自操作。

Controller错误转HTTP400/409或job失败，禁止虚假success。UI不编辑SQLite或artifact、不执行自由shell。

项目按仓库根复用原生App Server project，线程创建/恢复后校验projectId；实际读回与错误写入事件。同一项目同时最多一个活动Run持有项目资源租约。原生项目不等于Desktop saved-project侧栏展示保证。

用量通知保留threadId/turnId；按每个turn已处理total高水位去重，将新的last.totalTokens增量与去重状态在同一CAS内持久化。恢复后新turn允许计数器重置；已观察行为不保证未收到的通知完整，usage_observability说明观察边界。缺少turn/last的旧记录只保留legacy基数，不静默回填或声称精确成本。

源码范围检查包括Git忽略的未跟踪文件；读取警告视为检查失败。仅显式保留目录.team-temporary及经过格式/源码所有权核对的Python字节码属于运行残留，不能因.gitignore而豁免任意文件。最终Git源码检查不等于证明所有.git内部元数据都未变化；本版核对HEAD/tree和源码边界。

## Proposal协议（rules.py负责）

模型输出的proposal是对象：`schema_version:'0.2'`、`objective:str`、`questions:list[str]`、`assumptions:list[str]`、`mode:'single-session'|'multi-session'`、`allocation_reason:str`、`checkpoint:{title:str,requires_user_acceptance:bool}`、`requirements:[{id,text,owner,gate_ids:list[str]}]`、`work_packages:[{id,title,goal,depends_on:list[str],write_paths:list[str],acceptance_notes:str}]`、`gates:[{id,argv:list[str],timeout_seconds:int,description:str}]`。若questions非空允许空packages/gates，以供用户回答；否则requirements/packages/gates均非空，owner引用package，Gate全部存在，DAG无环，write_paths为安全仓库相对路径或裸目录（本版无glob，'.'仅single允许）。不同package不能覆盖同一路径树。single只有一个package，multi至少两个。gate argv不使用shell，不允许shell解释器（powershell,pwsh,cmd,bash,sh等）或python -c/node -e；允许python/node执行仓库内脚本及常规测试CLI；Gate属于用户审阅方案。requirements每条至少一个Gate。只读package允许write_paths=[]；其结果由外部controller记录，不强制代码commit。

`team_runtime/rules.py`提供`PROPOSAL_SCHEMA`（供Codex outputSchema使用，strict所有字段required/additionalProperties=false）、`validate_proposal(proposal)->None`、`digest(value)->str`（sha256: canonical sorted compact UTF8）、`owns(path, roots)->bool`（bare树与single '.'）、`validate_policy(policy:dict)->dict`。策略默认可配置：model='gpt-5.6-luna',reasoning='max',max_sessions=2,max_subagents_per_session=1,max_turn_seconds=1200,max_run_seconds=3600,max_repair_attempts=2,token_budget=200000,network_access=False。这些数值是显式本地试验选择，非通用最佳常数。校验整型非bool、正数或允许0(max_subagents/max_repair)、max_run>=max_turn、资源有限，不从用户不提供推断无限。不得静默忽略未知策略key。Package ID和Gate ID要求ASCII slug避免路径注入。标准库实现，兼容JSON Schema概念但不依赖jsonschema。

## Board

`serve(engine,host='127.0.0.1',port=8765)`和`make_server(engine,host='127.0.0.1',port=0)`。后者返回ThreadingHTTPServer，供测试/CLI启动。拒绝非loopback绑定。HTTP操作需同源校验，mutation需随机进程token（页面本身提供，禁止URL query泄漏）。接口自行设计但用真实Engine API。长propose用服务端job返回202并可查询，避免阻塞UI。静态文件位于team_runtime/static。页面中文，桌面/窄屏可读，真实状态/未知/过期明确，不显示伪精确进度。可提交Brief、回答问题、审阅方案、授权并运行、查看请求/证据、暂停恢复取消、接受检查点。不要硬编码演示数据。
