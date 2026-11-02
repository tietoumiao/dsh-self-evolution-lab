# 脱敏记录（SANITIZATION）

本发布目录由 **一次已跑完的完整实验目录** 整包复制 + 脱敏得到，**不是**重新跑出来的结果。
原始实验目录未做任何修改（只读取）；发布目录内所有相对路径、目录结构、文件名与原始实验目录一致，
仅有两类差异：① 文本文件里的绝对路径 / 用户名字面量被替换为占位符；② 源 `README.md` 改名为 `EXPERIMENT-INDEX.md`
（根 `README.md` 由发布方另写，不占用该文件名）。

- 脱敏时间：`2026-11-02T23:45:57+08:00`（`tools/sanitize-stats.json` 的 `generated` 字段）
- 生成命令：`python tools/sanitize.py`
- 逐文件明细：`tools/sanitize-stats.json`（每个文件的改动次数、替换前后字节数、替换前后 sha256）
- 工具：`tools/sanitize.py`（复制+脱敏）、`tools/make_manifest.py`（清单生成/校验）、`tools/verify_cells.py`（逐格重算校验）

> §1 的"原字面量"一栏用占位写法（`‹workspace-name›` / `‹user›`），因为**本文件自身也在发布目录里**，
> 若把原字面量整串写进来，脱敏门禁（§5 自检 #5）会命中它自己。原字面量的真实取值由
> `tools/sanitize.py` 顶部的 `_ORIG_WORKSPACE_DEFAULT` / `_ORIG_HOME_DEFAULT` 拼接给出
> （运行时值与原文完全一致），也可用 `--orig-workspace` / `--orig-home` 或同名环境变量覆盖。

## 1. 替换规则（顺序敏感：长的先替换）

顺序设计：**JSON 转义形式（双反斜杠）> 原生反斜杠 > 正斜杠**；每种形式内部**带尾分隔符优先于裸根**。
原因：`manifest.json` 等 JSON 文件里的绝对路径按 JSON 规则写作双反斜杠，只替换单反斜杠形式会漏；
裸根先替换则会留下孤立的尾分隔符。

| # | 规则名（与 `sanitize-stats.json` 同名） | 原字面量（占位写法） | 替换为 | 命中处数 |
|---|---|---|---|---|
| 1 | `workspace.json_escaped.trailing` | `D:\\‹workspace-name›\\` | `<workspace>/` | 3 |
| 2 | `workspace.backslash.trailing` | `D:\‹workspace-name›\` | `<workspace>/` | 253 |
| 3 | `workspace.backslash.bare` | `D:\‹workspace-name›` | `<workspace>` | 2 |
| 4 | `workspace.slash.trailing` | `D:/‹workspace-name›/` | `<workspace>/` | 72 |
| 5 | `workspace.slash.bare` | `D:/‹workspace-name›` | `<workspace>` | 0 |
| 6 | `home.json_escaped.trailing` | `C:\\‹user›\\` | `<home>/` | 0 |
| 7 | `home.backslash.trailing` | `C:\‹user›\` | `<home>/` | 1 |
| 8 | `home.backslash.bare` | `C:\‹user›` | `<home>` | 0 |
| 9 | `home.slash.trailing` | `C:/‹user›/` | `<home>/` | 0 |
| 10 | `home.slash.bare` | `C:/‹user›` | `<home>` | 0 |
| 11 | `normalize.backslash_to_slash` | `<workspace>` / `<home>` 之后残留的反斜杠路径段 | 该路径段的反斜杠统一改 `/` | 329 |

**合计替换 660 处，涉及 106 个文件。**

第 11 条只作用于**占位符之后的路径段**（例如 `<workspace>\agi\runs…` → `<workspace>/agi/runs…`），
不碰文件里其它位置的反斜杠（Python 正则/转义字面量等），避免破坏代码语义。

## 2. 明确不改的东西（红线）

| 对象 | 结论 | 证据 |
|---|---|---|
| 任何 sha256 / 哈希值的**字面量** | 0 处改动 | 替换表只匹配两个路径字面量；哈希是十六进制串，不在匹配集内 |
| `score.json` 的分数与结构 | 12/12 文件与原始实验目录**逐字节一致** | 见 §3 |
| `ledger.jsonl` 的 25 条记录与哈希链 | 与原始实验目录**逐字节一致**，链完好 | 见 §3 |
| 二进制文件 | 14 个原样复制（7 个 `.bin` fixture + 7 个 `.sql` fixture） | `.bin` 是二进制；`.sql` 不在声明的文本后缀白名单内，故原样复制（已核验其内容不含待脱敏字面量、0 个反斜杠） |
| 文件名 | 0 处改动（唯一变化是 `README.md` → `EXPERIMENT-INDEX.md`） | `tools/sanitize-stats.json` 的 `path` 字段即发布目录内的相对路径 |

## 3. 哈希未被改动的自证

**3.1 抽样：3 个 `score.json`（种子固定的随机抽样，`random.Random("agi-publish-sha256-sample")`）**

抽样方法与取值都与 `MANIFEST.sha256` 里对应行一致（同一 sha256 值，逐字符相同）：

| 相对路径 | sha256（与 `MANIFEST.sha256` 对应行相同） |
|---|---|
| `runs2/G1/heldout/score.json` | `a0d91ecde77dfd4b8a7287bcdb83f60e918d8a9da042c3a441be6bbe2a3c54ea` |
| `runs2/G0/heldout/score.json` | `888efaa6dad28af0a5554ec40a9f5179506fd6a1831991b52ccc2fdae3a234fb` |
| `runs2/G2/dev/score.json` | `4f6e7330fe45e6670c000012d6be99242b56c58331a928ab9e956bd406f7d6ac` |

**3.2 全量：与原始实验目录逐文件比对**

| 检查 | 结果 |
|---|---|
| `score.json` 与原始目录同路径文件 sha256 相同 | **12 / 12** |
| `ledger.jsonl` 与原始目录逐字节相同 | **是**（sha256 `29bab643d51b4198ff12adf5f3d040425106b61ab212b310b6d601849fa1b4e6`） |
| `ledger.jsonl` 的 `prev` 哈希链在发布目录内重算 | **断点 0**；25 条记录；head `5ae7f47a6c2695b9…`（与 `python runner/ledger.py verify` 输出一致） |
| 177 个 `.json` / `.jsonl` 文件仍可被 `json` 解析 | **0 个"源合法→发布非法"回归** |
| 111 个 `.py` 文件仍可通过 `py_compile` | **0 个语法错误** |
| `tools/sanitize-stats.json` 里每个文件的 `sha256_src` / `sha256_out` | 已逐文件落盘，可就地复核 |

**3.3 规模**

| 项 | 原实验目录（`agi/`，全树） | 复制进发布目录的范围 | 脱敏后 |
|---|---|---|---|
| 文件数 | 622 | 616 | 616（+ `tools/` 3 个脚本 + 1 个统计 = 620；再加 `SANITIZATION.md`/`MANIFEST.sha256` 见清单） |
| 字节 | 1,338,056 | 1,300,453 | 1,294,808（−5,645 B，全部是路径前缀变短所致） |
| 文本文件 | — | 602 | 其中 **106 个内容被改动** |
| 排除项 | — | 6 个文件 | `runner/probe-cred.ps1`（凭据探测脚本，不外发）、`runner/_pilot/out/hello.txt`、`genome/__pycache__/apply.cpython-313.pyc`、`runner/__pycache__/{freeze,prepare,_genome}.cpython-313.pyc`（`.pytest_cache` 源目录中不存在） |

改动次数最多的 6 个文件（其余 100 个文件改动次数 ≤ 6）：

| 文件 | 改动次数 | 字节（前 → 后） |
|---|---|---|
| `runs/G0/dev/manifest.json` | 24 | 2865 → 2661 |
| `runs/G1/dev/manifest.json` | 24 | 2865 → 2661 |
| `runs/G2/dev/manifest.json` | 24 | 2865 → 2661 |
| `runs/G0/heldout/manifest.json` | 12 | 1605 → 1503 |
| `runs/G1/heldout/manifest.json` | 12 | 1605 → 1503 |
| `runs/G2/heldout/manifest.json` | 12 | 1605 → 1503 |

## 4. 发布目录内的自检结论（原样命令，均在发布目录内执行）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `python bench/selftest.py` | `PASS=12 FAIL=0`（12 个任务 good=PASS / bad=FAIL 双向判别全绿） |
| 2 | `python bench2/selftest.py` | `PASS=6 FAIL=0` |
| 3 | `python runner/ledger.py verify` | `LEDGER OK records=25 head=5ae7f47a6c2695b9…`（**注意 §5.b 的路径解析**） |
| 4 | `python bench/grade_all.py --manifest runs/G1/dev/manifest.json --out <tmp>` | **不可复现**：12 格全部 `run_dir 不存在，按 FAIL 计` → `pass=0`，与 `runs/G1/dev/score.json` 的 `pass=10` 不符。原因见 §5.a（脱敏的必然代价）。**替代验证**：`python tools/verify_cells.py --all` → 12/12 格子与 `score.json` 逐条一致（含 `per_task`） |
| 5 | `grep -r "<原工作区名>\|<原用户名>" .` | **0 命中**（脱敏门禁通过；`tools/` 与被改写的 106 个文件都在扫描范围内） |

## 5. 已知副作用与做不到的事（照实写）

**a. 脱敏后 `grade_all.py --manifest …` 无法重算分数。**
`runs*/＜genome＞/＜split＞/manifest.json` 的 `run_dir` 原本是绝对路径，脱敏后是 `<workspace>/agi/runs/…`。
它既不是本机绝对路径（`os.path.isabs` 为假），又相对 manifest 所在目录解析不到任何真实目录，
于是 `grade_all.py` 逐格判 `run_dir 不存在 → FAIL`。这是**脱敏的必然代价，不是实验数据损坏**：
- manifest 里的 `run_dir_rel`（`agi/runs/G1/dev/T01/rep1`）原样保留，未脱敏（它本来就是工作区相对路径）；
- `tools/verify_cells.py` 用 `run_dir_rel` 重建格子并复用 `grade_all.py` 的口径重算，12/12 格子与 `score.json`
  逐条一致（例如 `runs/G1/dev`：`n=12 pass=10 weighted=10.0/12.0`，`per_task` 逐条相同）。
- 复现原命令的诚实记录：该命令输出的分数文件 sha256 为 `e9e9948e…`，`runs/G1/dev/score.json` 为 `7e2b225a…`，**不相同**。

**b. `runner/ledger.py verify` 校验的不是发布目录里的副本。**
该脚本用 `Path(__file__).resolve().parents[2] / "agi" / "ledger.jsonl"` 定位账本；发布目录的上一级仍是原工作区根，
所以它会**解析到同级的原始实验目录**（存在的路径），输出 `LEDGER OK`。由于发布目录内 `ledger.jsonl` 与原始文件
**逐字节一致**（§3.2：25 行、断点 0、head 相同），这次校验覆盖的字节与发布副本完全相同；但请知悉：
它读的确实是原始文件，不是发布副本。要做到"只读发布副本"，需要把 `LEDGER` 改成 `ROOT / "ledger.jsonl"` 之类的相对定位——
那会改动实验工具源码，超出本次"只复制+脱敏"的范围，故未动。

**c. `runner/prepare.py` 依赖 `__file__` 推导的 `ROOT`，重跑"生成 rollout"这步需要手工指路。**
它的注释里出现过原绝对路径（已脱敏成占位符），代码本身按 `parents[2] / "agi"` 拼路径。
读判分/自检不需要它；若要重跑数据生成阶段，需把 `ROOT` 指到发布目录自己的父级并把 `AGI` 指到发布目录。

**d. `tools/` 不进 `MANIFEST.sha256`。**
清单只覆盖发布内容（排除 `MANIFEST.sha256` 自身与 `tools/`）。`tools/` 里是脱敏器/清单器/校验器与其统计产物，
属"工具面"，其完整性可用 `git`/人工复核，未纳入逐文件清单——这是清单规格的一部分，不是漏项。

**e. 本目录没有 `README.md` / `LICENSE` / `.gitignore` / `context/`。**
按发布流程，这四项由发布方补充；补充后请重跑 `python tools/make_manifest.py` 刷新清单
（否则 `MANIFEST.sha256` 会缺这几行）。

**f. 未做（也不该由本次做的）事**：没有重新跑实验、没有重新判分写出新的 `score.json`、没有修改任何
实验工具源码、没有删除任何原始文件。所有 `score.json` 都是原实验产物，逐字节搬运。

## 6. 复核方法（在发布目录内执行）

```bash
# 1) 复算脱敏规则与统计（不写盘）
python tools/sanitize.py --dry-run

# 2) 逐文件哈希自查（清单与磁盘是否一致）
python tools/make_manifest.py --check

# 3) 逐格重算，替代"manifest 绝对路径"的验证路径
python tools/verify_cells.py --all

# 4) 脱敏门禁（须 0 命中）
grep -r "<原工作区名>\|<原用户名>" .

# 5) 发布后自检
python bench/selftest.py        # PASS=12 FAIL=0
python bench2/selftest.py       # PASS=6 FAIL=0
python runner/ledger.py verify  # LEDGER OK records=25（见 §5.b）
```
