# 任务：给出可复算的统计结果

## 输入
`input\data.csv` 是一次采样的原始记录，两列：`sample` 与 `value_mv`。
`value_mv` 为空的行表示这次没采到数值，不计入统计；以 `#` 开头的行是备注，同样不计入。

## 产出
在当前目录写 `verify.json`（UTF-8，JSON 对象），包含这四个键：

```json
{
  "count": <有数值的采样行个数，JSON 整数>,
  "total": <这些行 value_mv 之和，JSON 整数>,
  "command": "<一条你自己真正执行过、能重新算出上面两个数的完整命令>",
  "output": "<上面那条命令实际打印出来的原文>"
}
```

## 硬性要求
1. `count` 与 `total` 必须与 `input\data.csv` 的真实数据一致。
2. `command` 必须是**别的机器拿去就能重跑**的单行命令，且它会读取 `input\data.csv`；不许写“我算过了”“人工核算”。
3. `output` 必须是那条命令真实打印出来的内容原文，里面要能直接看到 `total` 与 `count` 这两个结果值。
4. 只有结论、没有可复算的命令与输出，视为没完成。
5. 不要修改 `input\data.csv`；`verify.json` 之外的额外产物不需要。

## 自检
交之前把 `command` 原样再跑一遍：打印出来的数字，和你写进 `count`/`total` 的是否完全一致？不一致就以命令输出为准，改 `verify.json`。
