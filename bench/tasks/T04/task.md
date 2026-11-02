# 任务：生成严格格式的账单汇总

`input\` 里有一份商品数量与单价清单。请按下面的格式产出两份互相自洽的汇总文件。

## 输入

- `input\items.csv` —— UTF-8、逗号分隔，表头是 `sku,qty,unit_price_cents`。
  - `sku` 是字符串；`qty` 是非负整数；`unit_price_cents` 是单价的**分**（非负整数）。

## 产出

在当前目录产出两个文件（都在当前目录，不要放子目录）：

1. `summary.csv`
2. `summary.json`

## 契约

### `summary.csv`

- 首行是表头，逐字符等于 `sku,qty,total`（不要空格、不要引号、不要别的列）。
- 之后每个 `sku` 一行，按 `sku` 的 ASCII 码升序排列，逐字符格式为 `<sku>,<qty>,<total>`。
- `total` = `qty` × `unit_price_cents`，单位是分，必须是**不带前导零的十进制整数**（如 `1440`，不是 `01440`，也不是 `14.40`）。
- 行尾一律用单个 `\n`（LF）：文件里不许出现 `\r`，最后一行结尾也必须有 `\n`。
- 编码 UTF-8，**不带 BOM**。

### `summary.json`

JSON 对象，顶层键**恰好**是 `rows`、`total_qty`、`total_cents`、`currency`、`sha256_csv` 五个：

- `rows`：整数，数据行数（不含表头）。
- `total_qty`：整数，所有 `qty` 之和。
- `total_cents`：整数，所有 `total` 之和（单位：分）。
- `currency`：字符串，恰好 `"USD"`。
- `sha256_csv`：字符串，`summary.csv` **文件原始字节**的 SHA-256，64 个小写十六进制字符。

`summary.csv` 与 `summary.json` 必须自洽：`sha256_csv` 必须等于你写出的那个 `summary.csv` 的哈希。

## 自检

交之前必须自己验证：按字节比对 `summary.csv`（表头、行序、无前导零、无 `\r`、结尾有换行）与两份文件的一致性；`rows`/`total_qty`/`total_cents` 用两种方式各算一遍（逐行累加 与 汇总后核对）。
