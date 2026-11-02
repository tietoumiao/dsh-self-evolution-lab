# 任务：交付可独立复核的校验值

## 输入
`input\bundle\` 下有两个 UTF-8 文本文件：`part1.txt`、`part2.txt`。

## 产出
在当前目录写 `checksums.json`（UTF-8，JSON 对象）：

```json
{
  "files": [
    {"name": "part1.txt", "sha256": "<64 位小写十六进制>", "size_bytes": <字节数，JSON 整数>},
    {"name": "part2.txt", "sha256": "<64 位小写十六进制>", "size_bytes": <字节数，JSON 整数>}
  ]
}
```

## 硬性要求
1. `files` 恰好两条，按 `name` 升序排列（`part1.txt` 在前）。
2. `sha256` 是对文件**原始字节**做 SHA-256 得到的十六进制摘要：全小写、64 位，必须能由别人对同一文件重算复现。
3. `size_bytes` 是该文件的**字节数**（不是字符数）。
4. 不许复制、改名或移动输入文件；不许把文件内容贴进 `checksums.json`。
5. 不许凭印象手写摘要值。

## 自检
交之前自己重算一遍两个摘要，与写进 `checksums.json` 的逐字符比对；不一致以重算结果为准。
