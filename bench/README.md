# bench 实现说明（bench-code 侧：T01–T06 + 自检/批跑工具）

判据本体是 `CONTRACT.md`（Lead 所有，只读）。本文件只写**契约条款 → 实现位置**的对照，以及怎么跑。

## 1. 契约 → 实现对照

| 契约条款 | 落地位置 | 实现方式 |
|---|---|---|
| §1 目录布局 | `tasks/T01..T06/`、`selftest.py`、`grade_all.py` | 6 个任务目录各自含 `task.md` / `meta.json` / `fixtures/` / `grade.py` / `selftest/good/` / `selftest/bad/` |
| §2.1 无网络、无外部依赖 | 全部 `grade.py` 与两个工具 | 只用标准库（`json`/`pathlib`/`re`/`csv`/`hashlib`/`subprocess`/`decimal`/`heapq`） |
| §2.2 确定性、判分器不写文件 | 全部 `grade.py` | 真值每次从 `fixtures/` 重算；进程内导入被测模块前设 `sys.dont_write_bytecode = True`，不留 `.pyc` |
| §2.3 单任务 < 5 秒 | 全部 `grade.py` | 无子进程、无网络；12 个任务全量双向判别一轮约 3 秒 |
| §2.5/§2.6 不泄题、不读任务目录 | `tasks/T0*/task.md` | 只写 `input\...` 与"当前目录"相对写法；不出现任务目录路径、`grade.py`、`selftest`、`meta.json`、不出现"评测/实验/判分" |
| §3 `task.md` | 6 份 | ≤60 行；首行 `# 任务：<短标题>`；写清输入、产出、精确契约；含"必须自己验证再交" |
| §4 `meta.json` | 6 份 | 恰好 7 个键：`task`/`title`/`split`/`axis`/`weight`/`time_budget_min`/`requires`；`split` 全 `dev`；`weight` 全 1 |
| §5 `grade.py` CLI + 退出码 | 6 份 `grade.py` | `--run-dir` / `--task-dir`；0=PASS、1=FAIL、2=判分器自身错误（用法错/缺 fixture）；stdout 恰好一行 JSON，日志走 stderr |
| §5 编码要求 | 6 份 `grade.py` + 两个工具 | 开头 `sys.stdout/sys.stderr.reconfigure(encoding="utf-8")` |
| §5 缺产物按 FAIL | 6 份 `grade.py` | 被测产物缺失/为空 ⇒ `pass:false` + exit 1；只有缺 `fixtures/`、`--task-dir` 不存在、参数错才 exit 2 |
| §5 checks ≥ 2、失败给期望值/实际值 | 6 份 `grade.py` | 每任务 6–14 条可单独判真假的 check；失败 detail 写"期望 X，实际 Y"，截断 200 字符 |
| §6 轴分配 | `meta.json` | T01/T02=`code`、T03/T04=`spec`、T05/T06=`computation` |
| §7 `selftest.py` | `selftest.py` | 自动发现 `tasks/*`（读 `meta.json`）；good 必须 PASS（且判两次输出一致）、bad 必须 FAIL；打印 4 列表格与末行 `PASS=<n> FAIL=<m>`；任一不满足 exit 1；另校验 `meta.json` 键集与取值、`bad/` 非空目录 |
| §8 `grade_all.py` | `grade_all.py` | 逐条调 `grade.py`；判分器 exit 2 / stdout 不合契约 ⇒ 记 `error` 且按 FAIL 计、`grader_errors++`、自身 exit 2 |
| §9 自证 | 本文件 + 回执 | 见第 3 节命令 |

## 2. 怎么跑（三行）

```powershell
python agi\bench\selftest.py                                                   # 门禁：good 必须 PASS、bad 必须 FAIL
python agi\bench\grade_all.py --manifest <manifest.json> --out <score.json>    # 批跑：出汇总 score.json
python agi\bench\tasks\T01\grade.py --run-dir <RUN_DIR> --task-dir agi\bench\tasks\T01   # 单任务判分
```

manifest 形状（契约 §8；`run_dir` 相对路径按 **manifest 所在目录** 解析）：

```json
{"genome": "G0", "split": "dev",
 "runs": [{"task": "T01", "rep": 1, "run_dir": "../tasks/T01/selftest/good"}]}
```

## 3. 实现注意（环境事实，非契约修改）

1. **本机沙箱禁止子进程管道**：`subprocess.run(..., stdout=PIPE)` 抛 `PermissionError: [Errno 13]`（实测 `capture_output=True`/`input=`/`stdin=DEVNULL+pipe` 全部被拒）。
   两个工具因此采用"**管道优先 + 文件重定向回退**"：两条路径都是契约 §5 的同一条 CLI
   （`python <TaskDir>\grade.py --run-dir ... --task-dir ...`），只是 stdout 的承接方式不同；只有两者都失败才记判分器缺陷。
2. **判分器只用 CLI 调用，不做进程内 import**：stdout 按**最后一行** JSON 解析；stdout 为空 / 多行 / 末行非 JSON / JSON 形状不合契约 ⇒ 记判分器缺陷。
   缺陷分型：`defect-exit2-json`（exit 2 但自报了合法 JSON）与 `defect-exit2-traceback`（exit 2 且没有合法 JSON，多半是崩溃）。
3. **T01/T02 的判分器在进程内导入被测模块**（`importlib` + 线程超时 + 全局重定向 stdout/stderr），
   这是为了"判分器不写文件、不依赖子进程管道"；被测代码死循环时按 FAIL 记，不会挂死判分器。
4. **真值放在判分器里，不放 fixtures**：T01/T02 额外带隐藏用例（`fixtures/` 只给少量示例），避免"照抄样本"或"把答案写死"。

## 4. 任务清单（dev 分片）

| 任务 | axis | 难度抓手 | 反作弊设计 |
|---|---|---|---|
| T01 | code | 修缺陷模块：`MM:SS` / `HH:MM:SS` 解析 + 格式化 + 严格 `ValueError` | 隐藏解析/格式化用例与示例不同；类型必须精确 `int`/`str` |
| T02 | code | 修日志清洗脚本 + 产出 `out/summary.json` | 工件按行号/服务/排序逐键比对真值 + 隐藏 `parse_line` 向量 |
| T03 | spec | 严格键集/类型/格式 + 制品 `sha256` 与字节数 | fixtures 制品含非 UTF-8 字节，逼着按原始字节算哈希；键集多一个即 FAIL |
| T04 | spec | 固定字节 CSV（LF、无 BOM、无前导零）+ JSON 自洽 | 判分按字节比对 + 要求 `sha256_csv` 与自写文件一致 |
| T05 | computation | 依赖图：Kahn 拓扑序（最小 id）+ 最早开始 + 关键路径（回溯规则唯一） | 真值由判分器独立实现；并列取舍规则写死，答案唯一 |
| T06 | computation | 十进制精确汇率换算（`.5` 进位）+ 账户/月度双路聚合 | 真值用 `Decimal(...).quantize(ROUND_HALF_UP)`；浮点实现会差 1 分 |
