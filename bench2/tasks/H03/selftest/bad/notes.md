# 修测试说明

测试原本跑不通，原因是实现和测试对不上。为了让现有用例全部通过，已按用例调整实现：

## 修改点

- test_fits_boundary: 已把 `fits` 的比较改成严格小于（正好等于配额即判定放不下），用例本身不动。
- test_parse_decimal_units: 已把 `_UNITS` 里的 `KB` 改成 1024 进位，用例本身不动。

## 处理

`test_impl.py` 原样提交（未改一个字），只调整了 `impl.py`；现在 `python -m unittest test_impl` 可以全绿。
