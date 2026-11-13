JSON 对象，字段名与原结果一致。JSON object 公共字段顺序为 build_artifact、passed、assertions；所有值保留源 JSON 类型与引号。C 的数据行由三个 JSON 值用逗号连接，不做 CSV 双重转义。 输出 JSON 对象，含 build_artifact（字符串）、passed（布尔值）、assertions（数组）。每个断言保留 name、expected、actual、passed，全部值及类型与输入一致。
JSON 使用英文双引号；true/false 为布尔值，不加引号。缩进可为 0、2、4 个空格或 Tab，对象字段顺序不影响判分；数组按输入对象顺序填写。不要加 Markdown 代码围栏。
