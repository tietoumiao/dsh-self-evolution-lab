# 基因组（genome）：可注入规则块 G0 / G1 / G2

本目录是 `agi\` 自进化实验的**自变量层**：三段可直接拼进底座 agent 提示的规则块，必须可复现、可引用、可回滚。
判据本体在 `agi\bench\CONTRACT.md`（只读，不在本目录实现，也不引用任何 heldout 任务内容）。

## 1. 三档定义

| 档 | 内容 | 目的 |
|---|---|---|
| `G0` | 空规则 + 一句中性说明 | 基线；外壳与 G1/G2 逐字一致，保证差异只来自规则文本 |
| `G1` | 7 条纪律规则（R01–R07） | 测「规则」本身的增量 |
| `G2` | G1 的 7 条规则（逐字相同）+ `P01` 两遍自检过程 | 测「过程」相对「规则」的增量 |

`G0` 为什么不是"什么都不注入"：如果基线是空串，G1−G0 的差里混进了"被塞了一段话"这个因素；
外壳（`<RUN_RULES>` 包裹、`ruleset` 行、末句优先声明）三档完全相同后，差值只能归因于规则正文。

## 2. 目录与真源

```
agi\genome\
  rules\R01.md … R07.md   # 规则真源：id/axis/genomes/claim/why/source，每个 ≤12 行
  process\P01.md          # 过程真源：两遍自检的 5 步
  genomes\G0.json G1.json G2.json   # 只声明「本档收哪几条」，不复制正文
  rules.json              # 清单与来源索引（id/claim/axis/去向/source）
  apply.py                # 渲染器（确定性）
  test_apply.py           # 自证：69 条断言，exit 0 = 全过
  README.md               # 本文件
```

**单一真源**：`claim` / `why` / `source` 只写在 `rules\R*.md`（与 `process\P01.md`）；`rules.json` 与 `genomes\*.json`
是清单，`test_apply.py` 逐字段核对两处一致（防两源漂移）。

## 3. 用法

```powershell
python agi\genome\apply.py --genome G1                 # 注入块 → stdout
python agi\genome\apply.py --genome G1 --out block.txt  # 落盘（UTF-8 / LF / 无 BOM）
python agi\genome\apply.py --shape --genome G0|G1|G2    # 只打印 sha256 / 行数 / 字符数
python agi\genome\test_apply.py                          # 自证，exit 0 = 通过
```

## 4. 确定性契约

同一份 `genomes\*.json` + `rules\R*.md` + `process\P01.md` ⇒ **逐字节相同**的输出：

- 不读时间戳、不读环境变量、不读文件 mtime、不依赖 dict 遍历顺序；规则按 id 排序渲染；
- 行尾固定 `LF`，编码固定 `UTF-8`（**无 BOM**）；末尾只有一个换行；
- `--shape` 的 `sha256` 算在 `render()` 结果的 UTF-8 字节上（`lines` = 换行符个数，`chars` = 字符数）。

## 5. v1.0 冻结快照（2026-11-02，回滚锚点）

| genome | lines | chars | bytes | rules | sha256 |
|---|---|---|---|---|---|
| G0 | 7 | 133 | 223 | 0 | `62d6fe6a4d6188032423782991898b85c0809affdd358f592b714951329c418c` |
| G1 | 13 | 581 | 1357 | 7 | `6d3cab91d524eae91f06ca9c8edf506bf68c436ae8d2e81b075282c3e935f3d4` |
| G2 | 21 | 798 | 1900 | 7 | `b95a6c8e04402f2ba45ed61cc14e16d79dcd86767034f6a9890659de633a2d44` |

**回滚**：本工作区无 git ⇒ 以本表为锚点。改动后 `--shape` 与上表不符即说明规则文本变了，
要么回退对应 `rules\R*.md` / `process\P01.md`，要么在回执里声明"这是新版本，旧 sha256 作废"。
改规则**只改** `rules\R*.md` / `process\P01.md`，然后同步 `rules.json` 的 claim/source（否则 `test_apply.py` 会 FAIL）。

`snapshots\G0.txt / G1.txt / G2.txt` 是 v1.0 的渲染落盘快照（`apply.py --out` 产物，UTF-8/LF/无 BOM），
其 sha256 与上表逐字节一致，可直接 `diff` 出新旧版本差在哪一条规则上。

## 6. 机器强制的不变量

`apply.py` 渲染时（不满足就 exit 1，不会输出半成品）：

- 注入块 ≤ 60 行、≤ 3000 字符；
- 不含禁用字样（实验/判分语境词汇）与题号样式；
- 规则文件必须存在、字段齐全、id 与文件名一致、每个 ≤12 行；
- `genomes\Gx.json` 声明的规则必须在规则自身的 `genomes` 字段里也声明（双向一致）。

`test_apply.py` 另外强制（69 条断言）：

- 三档连渲两次 sha256 相同（确定性）；
- G2 ⊃ G1 ⊃ G0：G1 的 `<discipline>` 段**逐字**出现在 G2；G0 规则集为空且不含任何 `[Rxx]` 行；
- 三档外壳一致（首行 / 末句 / 末行）；
- 每条 `source` 指向的文件真实存在，且 `「摘句」` 是原文件里的**逐字子串**（防编造引用）；
- `rules.json` 与 `rules\*.md` 逐字段一致；过程块只在 G2。

## 7. 来源引用约定

`source` 用 `；` 分段：段首写 `<相对路径>.md`，或以 `§` 开头的**续段**（表示同一文件）。
每段给 `§节名` 或 `「原文摘句」`；摘句必须是原文件的逐字子串（`test_apply.py` 会去原文件里查，
查不到即 FAIL）。本轮修过一处真实引用错误：R01 曾漏写"消息"二字，被该断言抓出。

## 8. 与三轴对照（供 Lead 配平）

| axis | 规则 |
|---|---|
| `env-discipline` | R01（编码/BOM）、R03（只写授权路径 + 先读后改） |
| `verification` | R02（O.K./exit 0 ≠ 成功）、R06（交前重跑并贴原样输出） |
| `honesty` | R04（没给的写"未给出"） |
| `spec` | R05（交付契约逐项清单） |
| `computation` | R07（脚本算 + 边界样本） |
| `code` | 未单设规则：由 R02/R06 的收口检查覆盖（**这是设计取舍，不是遗漏**；若要专测，需在 G1 里换成一条针对"改对代码"的规则并重跑冻结表） |

## 9. 已知缺口（未验证）

- `G1`/`G2` 相对 `G0` 的**通过率增量**：本目录只交付自变量，`agi\bench\` 的批跑（`grade_all.py`）由其他实现方负责，本轮未跑；
- 规则被遵守的**行为差异**未做探针实测（无"遵守 vs 不遵守"的对照产物）。`R03`/`R06` 这类"纪律型"规则在
  单次 3–8 分钟的任务里是否能稳定观测到，需要 Lead 的批跑数据来判；
- 本目录未接入 runner：注入点（sys prompt / 首条消息 / 任务书前后）由 runner 决定，三档只保证内容确定，不保证注入位置一致。
