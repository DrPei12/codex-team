# Codex Team plugin 真实安装与触发验收

## 结论

`codex-team` v0.1 已在当前 Windows / Codex CLI `0.146.0` 环境完成两次
repo-scoped marketplace 注册、plugin 安装、新任务发现/触发、plugin 卸载与
marketplace 移除。最终全局安装状态已回滚；仓库保留可复现的
`.agents/plugins/marketplace.json`、builder 和被 Git ignore 的本地生成包。

该观察将“plugin 可移动”进一步升级为“当前 Codex 新任务可发现并加载
7 个 bundled skill”。它仍不证明长期触发准确率、旧会话热刷新、版本升级、
cachebuster、真实 worker dispatch 或 Team 相对 single baseline 的收益。

## 官方流程与安装前置

OpenAI 官方文档指定：repo marketplace 使用
`$REPO_ROOT/.agents/plugins/marketplace.json`，plugin 通常放在
`$REPO_ROOT/plugins/`；通过 CLI 添加 marketplace 后，从该 marketplace 安装 plugin，
并在新任务/会话中测试。

来源：[Package your plugin](https://developers.openai.com/plugins/build/plugins)、
[Build plugins](https://learn.chatgpt.com/docs/build-plugins)。

安装前快照：

- branch `codex/team-v01`，HEAD `50ffe21`，ordinary Git status clean；
- `.agents/plugins/marketplace.json` 与 `plugins/codex-team` 都不存在；
- configured marketplaces 只有 `openai-primary-runtime`、`openai-curated`、`chatcut-inc`；
- plugin list 无 `codex-team`；
- rollback 预注册为 `codex plugin remove codex-team@codex-team-local`，再
  `codex plugin marketplace remove codex-team-local`。

## Repo marketplace 与安装产物

仓库新增：

- `.agents/plugins/marketplace.json`：marketplace name `codex-team-local`，相对 source
  `./plugins/codex-team`，`AVAILABLE / ON_INSTALL`；
- `.gitignore`：忽略确定生成的 `plugins/codex-team/`，不在 Git 中维护第二份
  runtime source。

该 contract 进入 commit `19c81520560e44deba5ca768d63de0553967956c` / tree
`a548cc34b9d4ec9d238a27c8376ebc991f0f3cf2`。Plugin tests 增至
`9 passed, 0 failed`；与原 Team 回归合计 99 项。

第一次安装：

```text
codex plugin marketplace add . --json
codex plugin add codex-team@codex-team-local --json
```

CLI 返回 marketplace `alreadyAdded=false`，plugin `version=0.1.0`，安装路径为
`C:\Users\lenovo\.codex\plugins\cache\codex-team-local\codex-team\0.1.0`，状态
`installed, enabled`。安装缓存与 repo source 除 bytecode 外的 38 份文件 SHA-256
完全相同；缓存内 self-check 为 `PASS: 37 bundle files and 7 runtime entrypoints`。

本轮没有重启 Desktop 进程。安装后创建的新任务已能发现 plugin，说明当前
环境的“新任务”边界可以拾取新安装；这不能外推为所有 Desktop 版本都
无需重启，也没有测试当前旧任务是否热刷新。

## 安装后新任务证据

### Discovery + 总入口显式调用

Thread `01a03c22-5838-76c3-8e74-1ee6c9666de0` 在 managed worktree 中报告 7 个精确名称：

`codex-team:team`、`team-plan`、`team-run`、`team-status`、`team-integrate`、
`team-finish`、`team-recover`（后 6 个同样带 `codex-team:` 前缀）。

它显式调用 `$codex-team:team`，从安装缓存解析
`TEAM_SKILL_DIR` 并运行 self-check，结果 37/7 PASS；开始/结束 Git status 均为空。

### Implicit routing

Thread `01a03c22-58e9-75b0-aba6-0b15bb0b1694` 的 prompt 没有给出 skill 名称，只描述
一次 manifest-driven multi-task run 需选择 planning/preparation/status/integration/finish/recovery。
任务选择 `codex-team:team`，因 checkout 无 canonical run manifest/artifacts 而路由到
planning / `team-plan`；安装路径 self-check 37/7 PASS，Git 前后 clean。

这是一个正向隐式触发观察，不是触发准确率。Prompt 内容与 skill description 高度匹配，
未覆盖模糊请求、多 skill 冲突或版本漂移。

### Negative trigger

Thread `01a03c22-58db-7311-81c4-27ba1cc399ab` 只读 README 首个 Markdown 标题，返回
`Codex 多任务工程系统`，开始/结束 Git status 为空，没有 bundle-check 输出。

当前 thread reader 只暴露最终消息和命令 marker，没有独立的 skill-invocation telemetry。
因此该结果只能记为“行为与不触发相符”，不能完全证明内部从未加载 skill。

### 7-skill 显式调用矩阵

第二次重新注册/安装后，projectless thread
`01a03c2b-cc74-7a53-b374-9107a629d755` 在同一回合显式加载全部 7 个
`$codex-team:*` skill，逐个返回 SKILL.md 中独有的命令或安全边界：

- `team`：只读 route，不创建/消息 task；
- `team-plan`：validate/project 后停止，不 dispatch；
- `team-run`：prepare 只生成 non-live bundle；
- `team-status`：render facts，worker prose 不是 project truth；
- `team-integrate`：Git mutation / Gate command 分别需两个显式授权；
- `team-finish`：finalize 不 archive/delete；
- `team-recover`：project brief 不原地 retry/rewrite predecessor。

任务只运行一次共享 self-check，37/7 PASS；没有读仓库源码 skill/scripts。

## 卸载与回滚

两个安装周期都按以下顺序成功回滚：

```text
codex plugin remove codex-team@codex-team-local --json
codex plugin marketplace remove codex-team-local --json
```

第一次卸载后，projectless thread `01a03c2a-77c8-7552-905e-cbc14c39b855`
只从新任务 skill catalog 判定，返回 `ABSENT`。第二次最终卸载后，thread
`01a03c2d-a3ea-7a80-ba20-d6c3842400aa` 再次返回 `ABSENT`。两条任务都没有工具调用。

最终现场：

- `codex plugin marketplace list` 无 `codex-team-local`；
- `codex plugin list` 无 `codex-team`；
- 版本缓存路径不存在；`...\cache\codex-team-local` 父目录存在但为空；
- repo `plugins/codex-team` 作为 ignored 生成 source 保留，其 self-check 通过；
- repo marketplace 文件保留，但已从全局 configured sources 移除。

## 任务与 worktree 残余边界

本轮共得到 6 条可读任务身份：三条安装后 worktree task、两条卸载后
projectless catalog task、一条 7-skill projectless matrix task。它们仍保留为 idle，
未获单独授权 archive。

另有一次卸载后 worktree task create 只返回
`client-new-thread:89d96e50-0fd3-45e8-abe9-f54b26864d36`，产生了 worktree root `6387`，
但在等待窗口内没有出现 thread ID。主任务没有将它计为负验证，改用
projectless task。最终 `git worktree list` 已无本轮 4 个 managed worktree；对应容器目录
`4d8c/551e/fdba/6387` 仍存在，但每个内部 item count 为 0。本轮没有手工删除它们。

## 成熟度结论

可以声称：

- 当前记录环境中 repo marketplace 可注册，plugin `0.1.0` 可安装/重新安装/卸载；
- 新任务可发现并显式加载 7 个 skill；
- 一条高匹配 prompt 隐式选择 `codex-team:team`；
- 卸载后两条新 projectless task 均不再发现这组 skill。

不能声称：

- 所有请求的隐式/非触发都准确；
- 旧任务会热刷新或卸载后立即丢失已加载 skill；
- 版本升级、cachebuster 或非同版重安已验证；
- 套件已稳定、已验证真实 worker dispatch/handoff/archive，或已证明边际效用。

因此 7 个 skill 继续保持 `incubating`。
