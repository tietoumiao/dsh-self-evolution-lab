# 任务：生成发布元数据清单

`input\` 里有一份发布说明和一个制品文件。请把发布信息整理成一个机器可读的清单。

## 输入

- `input\release.md` —— 发布说明（组件名、版本、发布日期、制品文件名、依赖清单都在里面）。
- `input\artifact.bin` —— 制品文件本体（二进制）。

## 产出

在当前目录写一个文件 `manifest.json`（UTF-8，不要 BOM，不要放子目录）。

## 契约

`manifest.json` 顶层必须是一个 JSON 对象，**键恰好**是 `schema_version`、`component`、`artifact`、`dependencies` 四个；多一个键、少一个键都算不合规。嵌套对象同样只允许下面列出的键。

```json
{
  "schema_version": "1.0",
  "component": {
    "name": "gridd",
    "version": "2.4.1",
    "release_date": "2026-03-09"
  },
  "artifact": {
    "file": "artifact.bin",
    "sha256": "64 个小写十六进制字符",
    "bytes": 1234
  },
  "dependencies": [
    {"name": "libfast", "min_version": "1.8.0"}
  ]
}
```

逐项要求：

- `schema_version`：字符串，恰好 `"1.0"`。
- `component`：键恰好 `name`、`version`、`release_date` 三个，值都是字符串；取值照发布说明抄。
  - `version` 必须是 `主.次.修订` 三段纯十进制数字、用 `.` 分隔（如 `2.4.1`）。
  - `release_date` 必须是 `YYYY-MM-DD`（年 4 位、月 2 位、日 2 位，连字符分隔）。
- `artifact`：键恰好 `file`、`sha256`、`bytes` 三个。
  - `file` 是字符串，等于发布说明里写的制品文件名（不要加路径）。
  - `sha256` 是字符串：`input\` 下该制品文件**原始字节**的 SHA-256，64 个小写十六进制字符（大写不算）。
  - `bytes` 是 JSON 整数：该文件的字节数（不是字符数）。
- `dependencies`：JSON 数组，元素键恰好 `name`、`min_version` 两个，都是字符串；**顺序必须与发布说明里的清单顺序一致**，条数也要一致。

## 自检

交之前必须自己验证：`manifest.json` 能被 JSON 解析；四个顶层键与两处嵌套键完整且无多余键；`sha256`、`bytes` 是从 `input\artifact.bin` 的真实字节算出来的；版本与日期格式符合上面的正则形状。
