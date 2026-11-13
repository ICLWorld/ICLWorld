同字段冲突选修改时间较新者，并列取主分支。Conflicts use newer field timestamp; ties main. 双方独有字段都保留；C 时间相同取 main。 输出一个 JSON 对象，字段为 x、y、z、main_only、review_only；每个冲突字段比较 times.main 与 times.review，取时间较大分支的值，相同取 main。两个独有字段分别保留；不输出 times 容器。
JSON 使用英文双引号；true/false 为布尔值，不加引号。缩进可为 0、2、4 个空格或 Tab，对象字段顺序不影响判分；数组按输入对象顺序填写。不要加 Markdown 代码围栏。
