# 个人资料导入小工具

做一个可直接运行的 Python 标准库命令行工具 `import_notes.py`，把 UTF-8 CSV 中的个人资料条目导入 SQLite。CSV 列为 id、title、url；id 和 title 去除首尾空白后不能为空；url 必须是 http/https 且有主机。一个文件内重复 id 或与库中已有 id 冲突都应报告错误，整个文件原子回滚，已有数据不丢失。

命令为 `python import_notes.py INPUT.csv --db notes.sqlite3`。成功以 JSON 报告导入数，错误以 JSON 报告可读原因且退出码非零；正确处理中文、UTF-8 BOM、CSV 引号。README 说明使用方法与边界。请以真实临时 CSV 和 SQLite 文件运行 unittest，覆盖成功、空字段、非法 URL、批次内重复、与已有库冲突及回滚，不使用数据库 mock。

这是 Team 第二个真实场景，目标是检查新运行机制仍能交付可验证的软件产物。不需要网页界面、网络请求、部署、额外依赖或新建其他项目；实现和验证都在当前隔离目录内完成。
