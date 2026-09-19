# 安装与使用 Codex Team

[English](usage.md) · [简体中文](usage.zh-CN.md) · [首页](../README.zh-CN.md)

## 安装

准备 Python 3.12 及以上，以及已登录的 Codex CLI，确认命令可用：

```sh
python --version
codex --version
codex login status
```

未安装 Codex 时，按照 [Codex CLI 安装指南](https://developers.openai.com/codex/cli)安装，使用 `codex login` 登录。

安装 marketplace 与插件：

```sh
codex plugin marketplace add DrPei12/codex-team
codex plugin add codex-team@codex-team-local
```

也可以从本地源码安装：

```sh
git clone https://github.com/DrPei12/codex-team.git
cd codex-team
codex plugin marketplace add .
codex plugin add codex-team@codex-team-local
```

执行 `codex plugin list` 查看安装情况，打开新的 Codex 任务，在技能选择器中选择 **Team**。完整名称为 `codex-team:team`。

## 把目标交给 Team

说明目标、相关材料和重要限制。可以从初步想法开始，也可以直接提供完整需求。

> $team 为这些 CSV 文件做一个命令行导入器，校验输入后写入 SQLite，失败时保留已有数据。使用 Luna/max，最多同时运行两个会话。完成实现、测试和简短使用说明。

Team 调查现有信息，形成连贯的正式定义，在执行前解释建议的组织方式，并根据已有授权推进。你可以在同一对话中调整受众、范围、优先级和交付要求。

内部记录与运行命令由模型准备，使用插件无需手写 JSON 计划。

## 查看与调整工作

在 Codex 中让 Team 汇报进展、解释当前职责与等待原因、查看成果、暂停、继续或修改计划。Team 读取已保存状态，并按问题检索相关原始消息、决定和产物回执。

让 Team 暂停时，它会停止新派发并请求中断活跃的原生执行；让它继续时，恢复已停止的运行。控制程序中断后，Team 使用 `reconcile` 核对原生会话和后台执行，保留当前文件，让同一个运行能够继续。

保存项目的状态目录，其中包含 `team.sqlite3` 与按内容标识的产物；状态目录放在交付工作区之外。控制程序在对应终端进程运行期间推进工作。

## 开发者运行命令

源码入口为 `scripts/team.py`。已安装插件在 `skills/team/scripts` 下携带同一脚本，Team 会定位其安装绝对路径。

```sh
python -B scripts/team.py --state /absolute/path/to/state list
python -B scripts/team.py --state /absolute/path/to/state snapshot RUN_ID
python -B scripts/team.py --state /absolute/path/to/state run RUN_ID
python -B scripts/team.py --state /absolute/path/to/state pause RUN_ID
python -B scripts/team.py --state /absolute/path/to/state reconcile RUN_ID
python -B scripts/team.py --state /absolute/path/to/state history RUN_ID "source decision"
```

Windows 状态路径示例为 `D:/TeamState/my-project`，含空格路径加引号。

程序化登记时，`create` 从 UTF-8 文件读取定义、授权、初始工作和资源策略；具体参数见 `--help` 与 `create --help`。工作需要标题、目标和验收依据；成员身份、角色、目录、写入权限、依赖与优先级描述执行背景。

`delegate` 委托局部协调，`return-coordination` 交还职责。`replace-session` 保存已停止成员的交接记录，下一次分配使用新上下文。`revise` 记录局部计划变更，`message` 记录用户新信息。通常由 Team 在对话中管理这些操作。

## 模型与资源

默认模型为 `gpt-5.6-luna`，推理档位为 `max`。可按任务设置模型、推理档位、并发会话数、运行时间、单回合时间、修复尝试次数、可观察 token 预算和联网权限。协调与执行使用相同的模型和资源策略。Team 2.0 调度独立原生会话，`max_subagents_per_session` 设为 `0`。

运行程序为每个在途执行预留部分剩余 token 预算，记录原生用量通知，并在分配额度或时间到达限制时暂停。已结束执行释放未使用的预留；结果未知的执行保留预留，直到恢复核对完成。原生 token 报告包含缓存输入，在执行过程中陆续到达。账户百分点预算通过 Codex 账户额度单独监控，因为账户同时包含其他任务用量。自动定位 Codex 启动器需要指定路径时，设置 `CODEX_TEAM_CODEX`；`CODEX_TEAM_PYTHON` 指定原生检查使用的 Python。

## 升级

从 2.1 起，Team 在开始或恢复对话时检查已发布版本。从官方 Git marketplace 安装的版本默认自动更新。检查结果缓存一小时；检查失败后，下一次使用时在五分钟间隔后重试。检查无需后台轮询或额外模型会话。

同一主版本内的兼容更新，通过 Codex 在 Team 执行停止后安装。存在活动控制程序或尚未确认结束的原生执行时，安装延后。更新成功后，Team 读取新的 skill 与运行说明，改用新的运行程序绝对路径继续工作，并简短说明体验改善。项目状态、笔记、历史和成果保留在原目录。

直接在对话中选择偏好：

- “让 Team 保持自动更新。”
- “更新只通知我。”
- “关闭更新检查。”
- “现在检查一下 Team 更新。”

本地源码安装、自定义来源和明确固定的版本提供更新通知。需要将本地 marketplace 切换到官方自动更新时，使用上面的 marketplace add 命令注册 `DrPei12/codex-team` 并安装插件。跨主版本或需要改变状态格式的发布提供升级通知。

手动升级，或从 2.0 及更早版本首次升级时，先暂停活动 Team 项目并确认执行停止，再刷新 Git marketplace 并安装插件：

```sh
codex plugin marketplace upgrade codex-team-local
codex plugin add codex-team@codex-team-local
```

本地 marketplace 先更新源码，再执行 plugin add；marketplace upgrade 用于 Git 来源。手动安装后打开新任务，从原状态目录继续。

更新程序在安装前核对 GitHub 发布文件的哈希和安装包文件清单，将旧安装包与安装回执保存在插件缓存之外。安装失败时恢复旧包；中断的安装先核对实际结果，再处理恢复。偏好和回执保存在 `$CODEX_HOME/team-updates`，默认位置为 `~/.codex/team-updates`。联网失败时继续使用当前版本。

更新下载遵循命令行代理设置：`HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY`。

开发者可以使用下列内部命令，将 `scripts/team.py` 换成已安装运行程序的绝对路径：

```sh
python -B scripts/team.py updates
python -B scripts/team.py updates --mode notify
python -B scripts/team.py updates --mode auto
python -B scripts/team.py updates --mode off
python -B scripts/team.py updates --force --language zh-CN
```

2.0 只提供 **Team** 入口，六个阶段 skill 与 Auto 0.2 控制器已经退役。规划、状态查询、恢复、整合和交付继续由 Team 在对话中承接。

1.0.x 的自适应记录保留 0.3 状态格式、运行 ID、产物和历史，通过 `scripts/team.py` 接续，无需转换数据。开发者集成应将原自适应启动脚本改为这一入口，或在源码目录中使用 `python -m team_runtime`。

更早的 Auto 0.2 和 manifest 记录由原版本解释。保留其状态目录，查阅时使用对应的[历史版本](https://github.com/DrPei12/codex-team/releases/tag/v1.0.1)。需要继续发展早期项目时，将已采纳的定义、笔记和已核验产物带入新的 Team 项目。升级保留已保存数据，不转换旧执行状态。

## 常见问题

| 现象 | 处理 |
|---|---|
| 选择器里没有 Team | 查看 `codex plugin list`，然后打开新任务。 |
| 找不到 Codex 启动器 | 安装并登录 Codex，检查 `CODEX_TEAM_CODEX`。 |
| 原生执行无法运行 Python | 将 `CODEX_TEAM_PYTHON` 指向可访问的 Python 3.12+。 |
| 项目处于等待状态 | 查看排队工作、建议、待接受成果和最新控制程序错误。 |
| 现场被另一个运行占用 | 暂停并核对提示中指定的运行，然后继续目标运行。 |
| 外部动作结果未知 | 检查指定远端目标，记录原动作的实际结果。 |
| 产物提交后发生变化 | 检查变更，为当前产物安排验证。 |
