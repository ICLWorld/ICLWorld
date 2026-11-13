带列头 key,before,after 的 CSV。CSV key,before,after  CSV 第一行固定 key,before,after；后续每个输入对象占一行，三列依次复制 key、before、after。含逗号或双引号的单元格按标准 CSV 引号转义。
使用标准 CSV，不加 Markdown 围栏；允许 CRLF/LF、末尾换行、可选的单元格双引号，以及单元格内 JSON 的等价空白和对象字段顺序。列顺序和数据类型必须正确，不要在单元格值外添加空格。
