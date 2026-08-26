# Codex Team plugin packaging v0.1 验收

## 结论

Team v0.1 已从“只能在源码仓库运行”推进到“可确定构建为独立、
可移动的 skills-only Codex plugin”。生成包不依赖源码仓库 cwd 或绝对路径，
并在临时目录中实际跑通 plan、run、status、integrate、finish、recover 和
router。

这不等于已安装。本轮没有写入 personal/repo marketplace，没有复制到全局
skills 目录，没有在 Codex UI 安装、启用、卸载或刷新，也没有用新会话
验证显式/隐式触发。

## 为什么是 plugin，不是七次单独复制

当前官方文档将 plugin 定义为 ChatGPT/Codex 可发现、安装和分发的包，
可包含一组相关 skills，MCP server 可选。Skill 本身可携带 `scripts/`、
`references/` 和 `assets/`；只需指令与本地资源的 workflow 无需为打包而
引入 MCP server。Plugin 根目录必须有 `.codex-plugin/plugin.json`，用相对于
plugin root 的 `./skills/` 指向 bundled skills。

来源：[Plugin architecture](https://developers.openai.com/plugins/concepts/plugins)、
[Build skills](https://developers.openai.com/plugins/build/skills)、
[Package your plugin](https://developers.openai.com/plugins/build/plugins)。

## 实现

构建命令：

```text
python -B scripts/build-team-plugin.py --out <existing-parent>/codex-team
```

Builder 要求输出目录名严格为 `codex-team`，父目录已存在，且目标不存在。
它先在同一父目录的临时 staging 中构建，全部成功后再 rename；不覆盖旧包。

生成布局的核心是：

```text
codex-team/
  .codex-plugin/plugin.json
  skills/
    team/
      SKILL.md
      scripts/                 # 7 个 runtime entrypoint + bundle self-check
      references/schemas/      # 7 份 Team runtime schema
      references/bundle-manifest.json
    team-plan|run|status|integrate|finish|recover/
```

源码 skill 中的 repo-local `python scripts/...` 只在构建产物中改写为从 bundled
`<TEAM_SKILL_DIR>` 定位。源码仍保持一份；没有在仓库内手工复制七套
runtime。`bundle-manifest.json` 绑定除自身外的全文件 SHA-256。
`bundle-self-check.py` 核对精确 inventory/hash、plugin name/version 和 7 个 runtime
`--help` import。

## 验收证据

实现 commit `e4fa221df00f5dd37ff03a567ccfda9bf6760294` / tree
`62c282010c699d036d35d0678cb575ebcac11b4c`。

`tests/test_team_plugin.py` 结果为 `8 passed, 0 failed`，覆盖：

- 完整 manifest/7-skill/runtime/schema 布局；
- 两次构建的相对文件集和 bytes 完全一致；
- 错误包名、已存在输出拒绝且不覆盖；
- 任意 bundled reference 篡改使 self-check 非零；
- 在源码仓库外的临时目录实际运行 plan/run/status/router；
- 在 packaged runtime 中冻结 candidates、真实临时 Git merge、离线 Gate、
  review/audit/finalize；
- 在 packaged runtime 中完成 dirty recovery candidate/plan/brief。

原 Team 八组 90 项与新增 8 项一起重跑，最终 `98 passed, 0 failed`。
临时生成包通过官方 `plugin-creator` validator，7/7 packaged skill 通过
`quick_validate.py`，bundle self-check 报告 37 份绑定文件和 7 个 runtime entrypoint
通过。

## 执行事故与处置

一次临时检查误将构建输出指向 `D:\Desktop\codex-team`，超出了本轮承诺的
临时目录范围。主任务核对绝对路径与 plugin manifest 后删除了该纯生成目录，
并确认路径不再存在。该事故没有写 marketplace、全局 skill 目录或 Codex
配置，但仍作为 scope-discipline 记录保留。

## 仍未证明

- 没有将 plugin 加入 local/personal marketplace 或在 Codex UI 安装；
- 没有新会话中的 7-skill discovery、显式调用、隐式路由和非触发对照；
- 没有验证 plugin 升级、cachebuster、重装、禁用或卸载；
- 项目仍没有 LICENSE，本轮 manifest 因此不伪造 license 字段；
- 没有创建真实 Codex worker task，Team 套件仍为 `incubating`。
