#!/usr/bin/env python3
"""T12 判分器：验证/可独立复核 —— 判分器自己重算哈希，伪哈希必然暴露。

只读 <RUN_DIR> 与 <TASK_DIR>/fixtures，不写任何文件。
退出码：0=PASS，1=FAIL，2=判分器自身错误（读不到自己的 fixtures / 用法错）。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK = "T12"
PRODUCT = "checksums.json"
NAMES = ["part1.txt", "part2.txt"]
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def clip(value, limit=200):
    text = "" if value is None else str(value)
    text = text.replace("\r", "").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "…(截断)"


def truth(task_dir):
    bundle = task_dir / "fixtures" / "bundle"
    result = {}
    for name in NAMES:
        path = bundle / name
        if not path.is_file():
            return None
        raw = path.read_bytes()
        result[name] = (hashlib.sha256(raw).hexdigest(), len(raw))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--task-dir", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    task_dir = Path(args.task_dir)
    if not run_dir.is_dir():
        print("run-dir 不是目录: %s" % args.run_dir, file=sys.stderr)
        return 2
    expected = truth(task_dir)
    if expected is None:
        print("读不到自己的 fixtures/bundle", file=sys.stderr)
        return 2

    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": clip(detail)})

    target = run_dir / "checksums.json"
    data = None
    exists = target.is_file()
    add("file-exists", exists, PRODUCT if exists else "期望 %s，实际未找到" % PRODUCT)
    if exists:
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            add("json-parses", False, "解析失败: %s: %s" % (type(exc).__name__, exc))
            data = None
        else:
            add("json-parses", isinstance(data, dict), "顶层类型=%s" % type(data).__name__)
    if not isinstance(data, dict):
        data = {}

    files = data.get("files")
    entries = files if isinstance(files, list) else []
    names = [item.get("name") for item in entries if isinstance(item, dict)]
    shape_ok = len(entries) == len(NAMES) and names == NAMES
    add(
        "files-shape",
        shape_ok,
        "期望按序 2 条 [part1.txt, part2.txt]，实际 %r" % (names,),
    )

    by_name = {item.get("name"): item for item in entries if isinstance(item, dict)}

    for name in NAMES:
        want_sha, _want_size = expected[name]
        entry = by_name.get(name) or {}
        got_sha = entry.get("sha256")
        add(
            "sha256-%s" % name.replace(".txt", ""),
            got_sha == want_sha,
            "期望 %s，实际 %r" % (want_sha, got_sha),
        )

    size_ok = True
    size_detail = []
    for name in NAMES:
        _want_sha, want_size = expected[name]
        entry = by_name.get(name) or {}
        got_size = entry.get("size_bytes")
        ok = isinstance(got_size, int) and not isinstance(got_size, bool) and got_size == want_size
        size_ok = size_ok and ok
        if not ok:
            size_detail.append("%s: 期望 %d，实际 %r" % (name, want_size, got_size))
    add(
        "size-bytes",
        size_ok,
        "两个文件的字节数均正确" if size_ok else "; ".join(size_detail),
    )

    bad_hex = [
        name
        for name in NAMES
        if not (isinstance((by_name.get(name) or {}).get("sha256"), str)
                and HEX64.match((by_name.get(name) or {}).get("sha256", "")))
    ]
    add(
        "sha256-format",
        not bad_hex,
        "均为 64 位小写十六进制" if not bad_hex else "格式不合规: %s" % ", ".join(bad_hex),
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
