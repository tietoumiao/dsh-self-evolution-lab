# 任务：修好日志清洗脚本并产出汇总

当前目录的 `input\` 里有一份日志和一个人写的清洗脚本。脚本能跑，但汇总结果不对。请修好脚本，并用它产出汇总文件。

## 输入

- `input\events.log` —— 每行一条服务日志；其中混有注释行、被截断的行和字段多余的行。
- `input\clean_buggy.py` —— 有缺陷的脚本。

## 产出

就在当前目录产出两样东西：

1. `clean.py` —— 修好的脚本，必须能在当前目录下用 `python clean.py` 运行（读 `input\events.log`，写 `out\summary.json`）。
2. `out\summary.json` —— 用修好的脚本生成出来的汇总（脚本真的跑出来的，不是手填的）。

## 契约

### `parse_line(line: str)` 的返回

`clean.py` 必须导出 `parse_line`（函数名一字不差），而且**被 import 时不得产生任何副作用**（不许在导入时读文件或写文件）。它对一行文本返回：

- 该行严格符合下面这个形状时，返回 `dict`，键恰好是 `ts`、`level`、`svc`、`code`、`ms` 五个：
  `<时间戳> <级别> svc=<服务名> code=<三位数> ms=<整数>`
  - 时间戳：恰好 `YYYY-MM-DDTHH:MM:SSZ`（UTC，字面量 `Z` 结尾）。
  - 级别：只能是 `DEBUG`、`INFO`、`WARN`、`ERROR` 之一（全大写）。
  - 字段之间恰好一个半角空格；行尾不许有多余空格；不许有多余字段。
  - `code` 恰好 3 位数字；`ms` 是 1～5 位数字。
  - 返回值的类型：`ts`、`level`、`svc` 是 `str`；`code`、`ms` 是 `int`。
- 其它任何行（空行、注释、截断、级别不在枚举内、多余字段、缺字段）一律返回 `None`（不要抛异常）。

### `out\summary.json` 的形状

顶层键恰好是 `schema`、`total`、`levels`、`services`、`slowest`，不许有别的键，也不许少。

```json
{
  "schema": 1,
  "total": 12,
  "levels": {"DEBUG": 0, "INFO": 6, "WARN": 1, "ERROR": 2},
  "services": {"api": {"count": 6, "error_count": 1, "max_ms": 120}},
  "slowest": [{"line_no": 3, "svc": "api", "ms": 120}]
}
```

- `schema` 固定是整数 `1`；`total` 是识别成功的行数（`int`）。
- `levels` 必须同时有四个键（`DEBUG`/`INFO`/`WARN`/`ERROR`，没出现过的写 `0`），值都是 `int`。
- `services` 每个服务一个键，值是恰好三个键的对象：`count`（该服务行数）、`error_count`（级别为 `ERROR` 的行数）、`max_ms`（该服务最大的 `ms`），都是 `int`。
- `slowest` 恰好 3 条，按 `ms` 从大到小排；`ms` 相同时按 `line_no` 从小到大排；每条恰好三个键 `line_no`、`svc`、`ms`（`line_no` 是该行在 `input\events.log` 里的行号，从 1 开始，注释行与非法行也占行号）。总行数不足 3 条时按实际条数输出。

## 自检

交之前必须自己验证：把 `input\events.log` 跑一遍，确认 `total`、四个级别的计数、每个服务的 `error_count`/`max_ms`、以及 `slowest` 的排序都符合上面的规则；再单独测几种非法行是否都返回 `None`。
