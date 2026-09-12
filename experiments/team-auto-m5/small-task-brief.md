# CheckCSV：单会话负例与真实交付

做一个可以直接使用的Python标准库命令行工具checkcsv.py，为实验记录做CSV质量检查。调用方式：python checkcsv.py INPUT.csv --required id,name。读取UTF-8含可选BOM的CSV，报告总数据行数、表头、空白必需字段、重复id、格式不合法和缺少表头的问题。成功输出机器可读JSON到stdout，错误诊断同样是JSON；合法返回0，数据质量不合格返回2，文件不可读返回3。可用--output报告.json保存同一报告。不能联网，不能使用第三方库、Skill或插件。README说明用法、退出码和限制。

这是一个小而连贯的工作，请判断是否需要独立并行Session；用户预期以单个执行Session完成。可以调用至多1个内部subagent，只允许gpt-5.6-luna/max。编写unittest并用真实子进程测试CLI：合法CSV、BOM、空值、重复id、缺列、不可读文件、含引号逗号与换行。验收运行python -m unittest discover -s tests -v。本轮检查点是可用源码、README、测试通过及独立审查，无需用户对主观视觉作决定；检查点达成后停止，不发布。
