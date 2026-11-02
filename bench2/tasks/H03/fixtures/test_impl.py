"""impl.py 的单元测试。运行：python -m unittest test_impl"""

import unittest

from impl import fits, parse_size, split_even


class TestImpl(unittest.TestCase):
    def test_parse_binary_units(self):
        self.assertEqual(parse_size("1.5KiB"), 1536)
        self.assertEqual(parse_size("2MiB"), 2 * 1024 * 1024)

    def test_parse_decimal_units(self):
        # 十进制单位
        self.assertEqual(parse_size("1.5KB"), 1536)

    def test_fits_boundary(self):
        # 边界：正好等于配额上限
        self.assertFalse(fits(4096, "4KiB"))

    def test_parse_rejects_bad_input(self):
        for bad in ("1.5", "", "1 kb", "1.5KIB", None, "1.5KiBx"):
            with self.assertRaises(ValueError):
                parse_size(bad)

    def test_split_even_remainder(self):
        self.assertEqual(split_even(10, 3), [4, 3, 3])
        self.assertEqual(split_even(7, 7), [1, 1, 1, 1, 1, 1, 1])

    def test_split_even_rejects_invalid(self):
        for args in ((5, 0), (-1, 3), (5, -2)):
            with self.assertRaises(ValueError):
                split_even(*args)


if __name__ == "__main__":
    unittest.main()
