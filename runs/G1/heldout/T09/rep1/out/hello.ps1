# hello.ps1 —— 温度传感器自检（演示）
# 目标环境：Windows PowerShell 5.1（系统本地代码页 GBK/936）
# 文件编码：UTF-8 + BOM（前三个字节为 EF BB BF）；缺 BOM 时 5.1 会按 GBK 解码，中文变乱码，甚至报出一堆假语法错。

$ErrorActionPreference = 'Stop'

# 自检项目：温度传感器（演示脚本，不访问真实硬件）
Write-Host "输出结果：温度传感器自检完成"
