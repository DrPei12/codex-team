# Changelog

本文件记录 Codex Team 的公开版本。完整设计决策见 [`docs/13-decisions.md`](docs/13-decisions.md)。

## [Unreleased]

- 尚无已承诺内容。

## [0.1.3] - 2026-09-01

### Added

- Requirement coverage lattice：绑定 requirement、owner、path、Gate 和 reviewer。
- `change` / `verification-only` requirement 类型。
- Hash-bound worker backbrief 与 `passed` / `needs-input` / `failed` receipt。
- Stage checkpoint、material-progress facts、manifest-specific heartbeat 与 turn budget。

### Changed

- Active lane 必须同时具备 passed preflight、passed backbrief 和未过期 progress fact才能显示为 `working`。
- Plugin version 升为 0.1.3；旧 manifest/facts 不自动升级。

## [0.1.2] - 2026-08-30

### Added

- `user_locale`、`execution_surface`、独立 `task_title` 与 lane `lifecycle`。
- Finish 按 lane 输出 archive/retain/not-applicable task disposition。

### Changed

- Visible task 标题与 prompt 分离；internal subagent 不再创建 sidebar task。

## [0.1.1] - 2026-08-30

### Fixed

- Ownership 裸路径统一表示路径自身与子树；`forbidden_paths` 始终覆盖 write allow。
- Reviewer preflight 绑定 passed integration Gate 的 post-integration exact commit/tree，而不是错误回退到 manifest base。

## [0.1.0] - 2026-08-26

### Added

- 七个 manifest-driven Team skills。
- Plan/run/status/integrate/finish/recover/router 离线主链。
- Deterministic skills-only plugin builder、bundle manifest/self-check 与 repo marketplace。
- 首次真实安装、discovery、explicit load、implicit routing 与卸载回滚证据。

[Unreleased]: https://github.com/DrPei12/codex-team/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/DrPei12/codex-team/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/DrPei12/codex-team/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/DrPei12/codex-team/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/DrPei12/codex-team/releases/tag/v0.1.0
