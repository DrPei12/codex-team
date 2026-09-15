# 贡献指南

[English](CONTRIBUTING.md) · [简体中文](CONTRIBUTING.zh-CN.md)

先阅读[正式定义](docs/project-definition.zh-CN.md)、[运行原理](docs/architecture.zh-CN.md)与[已接受决策](docs/13-decisions.zh-CN.md)。改动应改善 Team 理解委托、组织工作或交付成果的能力。

运行程序使用 Python 3.12+ 与标准库，开发检查安装 `pytest` 和 `jsonschema`。真实模型验证使用独立工作区与状态目录，明确选择模型和预算。

修改 `team_runtime`、`scripts` 与 `skills` 后，构建新的插件目录：

```sh
python -B scripts/build-team-plugin.py --out /existing/parent/codex-team
```

将生成的插件包复制到 `plugins/codex-team`，然后执行：

```sh
python -B scripts/check-release.py
```

发布检查运行运行时与兼容测试，构建新包、校验清单和导入，并与仓库内分发包比较。回归测试验证真实状态变化或用户结果；原生测试替身明确标注，执行行为变化同时进行真实 Codex 验证。

中英文公共文档保持同步。修改核心概念或生命周期规则时，同步定义与决策日志。工作笔记和私有验证结果保存在分发目录之外。

拉取请求说明具体问题、改动后的行为与验证结果。保留已有成果和失败记录；并行工作为每个可变文件指定明确负责人，根据实际产物进行集成。
