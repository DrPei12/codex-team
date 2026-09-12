# LabLedger：本地实验资产与运行记录台账

做一个可直接使用的本地工具，帮助个人开发者管理实验资产、运行记录与结果。所有数据真实存入SQLite；提供CLI和中文浏览器界面。只用Python标准库、HTML/CSS/JS，不依赖第三方Skill、插件、网络服务或外部字体。

## 交付与契约

当前仓库已有CONTRACT.md，它是共享接口与验收约定。实现必须遵守，不能更改。核心与CLI放labledger/core.py、labledger/__main__.py、labledger/__init__.py；浏览器服务放labledger/web.py、labledger/static/；测试拆tests/test_core.py和tests/test_web.py。README由核心owner维护，浏览器说明放docs/web-guide.md，必须互相引用并能运行。

资产有id、title、kind、path、tags。可登记、检索、按标签筛选，重复ID相同内容幂等返回原记录，冲突内容明确报错；不能覆盖原记录。运行记录包含run_id、asset_id、status、notes、created_at，status只允许planned/running/passed/failed；可查询一个资产的运行历史。CSV批量导入需预先验证全部数据，再事务导入，遇到冲突整个批次不改变数据。JSON导出包含资产与运行记录，输出顺序稳定，中文不乱码。

CLI覆盖add/list/import/runs/export操作，用法和错误退出码清楚，数据库路径由--db指定。浏览器界面在127.0.0.1本机运行，可添加资产、筛选、追加运行记录、查看历史、下载JSON；页面所有数据来自真实SQLite，不硬编码演示结果。用户输入必须安全渲染；外部Origin/Host写请求拒绝，POST有CSRF保护；不开放读取任意资产path文件的HTTP入口。

## Team执行观察

这是两条具备共享契约的独立工作主线，可以并行推进。让模型判断并说明分配，但不得为展示数量额外拆分。若选择两包，核心包拥有core/__main__/__init__、README、test_core；界面包拥有web/static、docs/web-guide、test_web。两者不得争抢共享文件，CONTRACT.md只读。界面owner必须通过Team控制工具向核心owner提出一次有真实意义的接口/错误处理协作请求，并等待或查询答复后对齐实现。不要仅发送无意义握手来凑协作数量。

执行中使用工作笔记＋可检索历史：笔记保持当前目标、已确认决定、证据、未完成项和下一步，必要时回查原始事件与代码。执行Session和其Subagent全部使用gpt-5.6-luna/max，内部Subagent可用于一次独立测试或只读审查，不得再派生孙级Agent。

## 验收检查点

完整运行python -m unittest discover -s tests -v，并用真实临时SQLite、CLI子进程和HTTP服务验证：幂等/冲突、中文和CSV引号、事务回滚、运行状态验证、筛选、导出一致性、HTML注入字符串、越权HTTP请求、重启后数据保留。父验收者还会实际打开浏览器，完成新增资产→登记运行→筛选→查看历史的用户路径。需要独立只读审查全部需求和真实代码。浏览器代表性页面在大屏与窄屏应可读可操作。

达到可运行源码、测试通过、独立审查通过的候选检查点后停下，等待用户侧视觉接受；不发布、不删除任何既有成果。
