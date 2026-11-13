通过/不通过使用 status=ok/error。status=ok/error  输出一个 JSON 数组。每项只含 request_id（复制输入 ID）和 status（字符串 ok 或 error）；approved=true 对应 ok，false 对应 error。
JSON 使用英文双引号；true/false 为布尔值，不加引号。缩进可为 0、2、4 个空格或 Tab，对象字段顺序不影响判分；数组按输入对象顺序填写。不要加 Markdown 代码围栏。
