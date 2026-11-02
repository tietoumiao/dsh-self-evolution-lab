#!/usr/bin/env python3
"""T09 判分器：环境纪律/编码 —— 必须是 UTF-8 BOM + UTF-8 正文。

只读 <RUN_DIR>，不写任何文件。按原始字节判定，绝不用 utf-8-sig 掩盖 BOM 是否存在。
退出码：0=PASS，1=FAIL，2=判分器自身错误。
"""
import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK = "T09"
PRODUCT = "out/hello.ps1"
BOM = b"\xef\xbb\xbf"
REQUIRED_SENTENCE = "输出结果：温度传感器自检完成"


def clip(value, limit=200):
    text = "" if value is None else str(value)
    text = text.replace("\r", "").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "…(截断)"


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--task-dir", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print("run-dir 不是目录: %s" % args.run_dir, file=sys.stderr)
        return 2

    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": clip(detail)})

    target = run_dir / "out" / "hello.ps1"
    data = b""
    exists = target.is_file()
    add("file-exists", exists, PRODUCT if exists else "期望 %s，实际未找到" % PRODUCT)
    if exists:
        try:
            data = target.read_bytes()
        except OSError as exc:
            print("读取产物失败: %s" % exc, file=sys.stderr)
            return 2

    head = data[:3]
    head_hex = " ".join("%02X" % byte for byte in head) if head else "(空文件)"
    add(
        "utf8-bom",
        head == BOM,
        "期望前 3 字节 EF BB BF，实际 %s" % head_hex,
    )

    body = data[3:] if head == BOM else data
    text = None
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        add(
            "body-utf8-decodable",
            False,
            "正文按 UTF-8 解码失败（%s，位置 %d）；文件头 %s"
            % (exc.reason, exc.start, head_hex),
        )
    else:
        add(
            "body-utf8-decodable",
            True,
            "正文按 UTF-8 解码成功，共 %d 字符" % len(text),
        )

    body_text = text if text is not None else body.decode("utf-8", errors="replace")
    add(
        "contains-chinese-line",
        REQUIRED_SENTENCE in body_text,
        "期望含 %r，实际正文首行: %r"
        % (REQUIRED_SENTENCE, body_text.splitlines()[0] if body_text.splitlines() else ""),
    )
    add(
        "uses-write-host",
        "Write-Host" in body_text,
        "期望出现 Write-Host，实际%s出现" % ("" if "Write-Host" in body_text else "未"),
    )
    add(
        "no-replacement-char",
        "\ufffd" not in body_text,
        "不得含 U+FFFD"
        if "\ufffd" not in body_text
        else "正文含 U+FFFD（编码链路丢字节）",
    )

    passed = all(item["pass"] for item in checks)
    failed = [item["name"] for item in checks if not item["pass"]]
    if passed:
        reason = "全部 %d 项判据通过" % len(checks)
    elif "file-exists" in failed:
        reason = "缺少产物 %s（按缺文件判 FAIL）；其余未通过判据: %s" % (PRODUCT, ", ".join(failed))
    else:
        reason = "未通过判据: %s" % ", ".join(failed)
    result = {
        "task": TASK,
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "checks": checks,
        "reason": reason,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
