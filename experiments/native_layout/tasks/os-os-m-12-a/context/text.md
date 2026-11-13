同字段冲突优先主分支。Conflicts use main. 双方独有字段都保留；C 时间相同取 main。 输出一个 JSON 对象，字段为 x、y、z、main_only、review_only；x/y/z 取 main，两个独有字段分别从所属分支保留。不要把 baseline、main、review、times 这些输入容器写进结果。
JSON 使用英文双引号；true/false 为布尔值，不加引号。缩进可为 0、2、4 个空格或 Tab，对象字段顺序不影响判分；数组按输入对象顺序填写。不要加 Markdown 代码围栏。
