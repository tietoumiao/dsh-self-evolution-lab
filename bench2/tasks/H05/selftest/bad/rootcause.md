# 根因分析：为什么脚本不报错，数据却是错的

## 缺陷 1（第 21 行）：用 GBK 解码 UTF-8 字节

`ledger.csv` 是 UTF-8 编码。`data.decode("gbk", errors="replace")` 把同一串字节按 GBK 的
双字节规则去切分，切出来的码点完全不同（`茶叶` 被解成 `鑼跺彾`），而 `errors="replace"`
又把切不动的残余字节替换成 U+FFFD 而不是抛错。于是：

- 解码这一步**不会**抛 `UnicodeDecodeError`，看起来一切正常；
- 但字符串已经错了，后续所有按品类聚合的键都变成乱码，同一个真实品类还可能因为
  替换字符而拆成两个键。

改法：`data.decode("utf-8")`，让编码错误直接抛出来，不要用 `errors="replace"` 掩盖。

## 缺陷 2（第 32 行，配第 33 行 `continue`）：`except Exception: continue` 静默丢行

解析用的是 `line.split(",")`。`"礼盒,精品"` 这种带引号、引号内含逗号的字段会被切成
两段，字段下标整体后移，`int(parts[2])` 拿到的是 `精品"`，抛 `ValueError`；而
`except Exception: continue` 把这个异常吞掉、直接跳过整行。

- 后果：该行**完全消失**，既不计行数也不计金额，脚本照样正常退出；
- 这是「静默丢数据」：错误被 `except` 吞在本层，调用方永远看不到。

改法：用 `csv.reader` 处理引号与逗号，并让不合规输入抛 `ValueError` 而不是 `continue`。
