# 个人资料 CSV → SQLite 导入工具

`import_notes.py` 是一个只使用 Python 标准库的命令行工具。它把本地 UTF-8 CSV 中的个人资料条目写入 SQLite，不发起网络请求。

## 使用

需要 Python 3.9 或更高版本。在本目录执行：

```text
python import_notes.py INPUT.csv --db notes.sqlite3
```

CSV 必须有表头，并且恰好包含 `id`、`title`、`url` 三列；三列的顺序可以不同。示例：

```csv
id,title,url
note-1,"中文标题, 含逗号",https://example.com/notes/1
```

文件按 UTF-8 读取，也接受 UTF-8 BOM；标准 CSV 引号、逗号和带引号的换行由 Python 的 CSV 解析器处理。

## 校验与事务边界

- `id` 和 `title` 会去除首尾空白，处理后不能为空；保存的是去除空白后的值。
- `url` 必须是带主机的 `http://` 或 `https://` URL。URL 不会被访问，主机是否可达不在校验范围内；URL 字段中的空白会被视为非法。
- 同一文件中不能有重复的（规范化后的）`id`；`id` 也不能与数据库已有记录冲突。
- 所有行会先完整解析和校验，然后在同一个 SQLite 事务中检查冲突并插入。任意错误都会回滚本次文件的全部写入，已有记录不会被更新或删除。
- 数据保存在 `notes` 表中，字段为 `id`（主键）、`title` 和 `url`。数据库或表不存在时会自动创建。

成功时，标准输出是一行 JSON，例如：

```json
{"imported": 2}
```

错误时，标准错误是一行包含可读原因的 JSON，进程退出码为 `1`，例如：

```json
{"error": "conflict", "message": "CSV 第 3 行的 id 'note-1' 已存在于数据库中"}
```

## 测试

测试会在真实临时目录中创建 CSV 和 SQLite 文件，并通过子进程运行 CLI；不使用数据库 mock：

```text
python -m unittest -v
```

测试覆盖成功导入、中文、BOM、CSV 引号、空字段、非法 URL、文件内重复、已有库冲突和错误回滚。
