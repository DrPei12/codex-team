# 2026-08-12 Codex 隔离会话 Pilot

> 历史证据说明：本报告测试的是 CLI 创建的会话。D-023 之后它不再代表 active Desktop baseline，也不能作为 CLI fallback 的依据；结论仅保留用于提示 Desktop preflight 需要检查的风险。

## 一句话结论

我们已经证明：可以把 Codex CLI 会话的实际工作目录和 Git worktree 全部限制在独立实验场中，并从主任务向已结束会话发消息、等待回复、在同一目录 fork 历史；但这只隔离了文件和 Git，**没有隔离 Codex 自动加载的全局 memory、skills、plugins 和用户配置**。

因此，项目的第一批能力不能只是“创建更多任务”，还必须包含 worker 启动检查、允许目录、上下文预算、全局依赖审计和失败停止。

## 实验场

- 实验根目录：`D:\Desktop\Codex多任务工程系统实验场`
- 干净 fixture：`source`，HEAD `a4288a5905abbd4efd5ddd4a9b4acafd021366ab`
- 两个保留的 worktree：`worktrees\worker-a`、`worktrees\worker-b`
- 分支：`lab/worker-a`、`lab/worker-b`
- 当前项目 checkout：未被 worker 使用，原有未提交修改保持不变
- 本地完整运行记录：`runs\2026-08-12-pilot-01\run.json`
- 记录 SHA-256：`9213b537f089a5abe11d4ca03404ca78e40474f4e65f9c1e98f8b3d8ce8f4e2a`

Codex 自己的任务元数据仍保存在 Codex 管理的全局 session store。当前 App/CLI 接口只能控制会话 cwd，不能把内部 session store 搬进实验目录；这里不能写成“所有物理数据完全在实验场内”。

## 实际通过的能力

### 1. 两个独立 CLI 会话绑定两个指定 worktree

两个 `codex exec -C` 会话分别报告并被 Desktop `read_thread` 复核为：

- worker A：`...\worktrees\worker-a`，`lab/worker-a`；
- worker B：`...\worktrees\worker-b`，`lab/worker-b`。

两者从相同 HEAD 启动，fixture verifier 均通过，结束后 Git 仍干净。主任务又独立运行了一遍 verifier 和 Git 检查，不能只依赖 worker 自报。

### 2. 主任务可以重新唤醒已结束的 CLI 会话

主任务向 worker A 发送唯一 nonce。目标任务完成后，`wait` 以 `turnCompleted` 唤醒，返回新的 cursor；回复中的 nonce、cwd、clean 状态和“未写文件”均匹配。

这只证明一个 idle/completed 本地 CLI 会话的单次 happy path，不证明消息有 exactly-once、顺序、重启持久化或 active-turn 可靠性。

### 3. Same-directory fork 继承已完成历史

从 worker A 在两个回合都完成后创建 same-directory fork。child：

- cwd 仍是 worker A 的实验 worktree；
- 读取时包含两个已完成父回合；
- 能从继承历史中找回只出现在父任务中的 nonce；
- child 自己完成一个只读回合后，Git 仍干净。

没有测试源任务正在生成回复时的历史截止点，也没有测试两个 same-directory 任务同时写文件。

### 4. Wait cursor 有一个容易误判的细节

最新 cursor 确实会隐藏已交付的最终消息正文：`changed=false`，没有重复 final body。但对于 Desktop 状态为 `notLoaded` 的已结束 CLI 会话，`wait` 仍会立即以 `inactiveStatus` 唤醒，而不是安静超时。

因此编排逻辑不能把“wait 返回”直接解释为“有新结果”；还要同时判断 cursor 是否变化、最新回合状态和消息是否存在。

## 暴露出来的问题

### 目录隔离不等于上下文隔离

两个 CLI 会话都自动加载了全局 memory、skills 和 plugins。虽然任务只有几条只读 Git 命令，初始回合仍分别消耗约：

- worker A：113,136 input tokens，87,040 cached；
- worker B：64,308 input tokens，40,448 cached。

这不是多任务方法本身的收益或成本结论，但足以证明“给 worker 一个空仓库和短 prompt”并不会自动得到轻量上下文。需要用相同 prompt 和 verifier 比较 normal profile 与经过审查的 minimal profile。

### 并发启动会碰共享全局状态

两个会话接近同时启动时，其中一个报告更新 system skills 目录被拒绝访问。两者最终都完成，所以当前只能说存在共享状态竞争信号，不能直接断言稳定复现或确定根因。

还观察到模型缓存字段不兼容、模型刷新超时、skill 描述超出上下文预算、两个 skill 名称超过 64 字符、MCP/plugin 认证失败、PowerShell shell snapshot 不支持和 Git 全局 ignore 读取被拒等非致命告警。这些应进入 worker preflight，而不是淹没在长日志里。

### CLI 会话不会自动注册为 Desktop 项目

实验前后 `list_projects` 都没有出现新 fixture repo，但 Desktop 可以用 ID 读取 CLI 创建的任务。因此当前可行路径是：手工在实验场创建 worktree，再用 `codex exec -C` 派发；无法在保持自定义 worktree 根目录的同时测试 Desktop `create_thread` managed-worktree 路径。

## 对 skills 架构的直接影响

第一条纵向 workflow 增加三个前置检查：

1. **Workspace boundary**：允许的 cwd/worktree 根目录、branch、HEAD 和 dirty 状态；
2. **Runtime context boundary**：会加载哪些 memory、skills、plugins、MCP 和用户配置，以及预计上下文预算；
3. **Coordination semantics**：message/wait/fork 的目标 identity、cursor、历史截止点和失败策略。

这些先作为 `team-capability-audit`、`team-run` 和共享 preflight 的职责，不急着新增一个只有名称的 skill。只有 minimal-profile 切换形成独立触发、独立行为和恢复路径后，再决定是否拆成 worker-bootstrap skill。

## 没有测试的能力

- Desktop managed-worktree create 与 worktree fork；
- handoff、archive 和 worktree cleanup；
- subagent；
- active-turn fork/message；
- dirty、ignored、untracked、submodule、LFS 和 conflict；
- 消息重复、顺序、无效目标、重启持久性；
- normal profile 与 minimal profile 的成本和正确率对照。

预注册预算已经用满：3 个会话、2 个 worktree。两个 worktree 和三个任务均保留，未归档、未删除，便于用户检查；下一批实验必须另行登记预算，不能看到结果后临时扩大本轮样本。

## 后续对照

首轮 pilot 结束后另行预注册了两个串行会话、零新增 worktree 的 profile mechanism test。结果否定了 `--ignore-user-config` 加禁用 memories/plugins/skill_search 的粗粒度方案：verifier 被执行策略阻止，skills 仍被发现，总 input 反而约为 normal 的 5.19 倍。详见 [Worker profile 对照](profile-comparison-2026-08-12.md)。
