#!/usr/bin/env python3
"""T03 判分器：manifest.json 的键名/类型/格式逐项合规 + 多键精确匹配。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
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

TASK_ID = "T03"
TOP_KEYS = {"schema_version", "component", "artifact", "dependencies"}
COMPONENT_KEYS = {"name", "version", "release_date"}
ARTIFACT_KEYS = {"file", "sha256", "bytes"}
DEP_KEYS = {"name", "min_version"}
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def clamp(text, limit=200):
    text = str(text).replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def dump(value):
    try:
        return clamp(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except Exception:
        return clamp(repr(value))


def emit(ok, checks, reason):
    payload = {
        "task": TASK_ID,
        "pass": bool(ok),
        "score": 1.0 if ok else 0.0,
        "checks": [{"name": n, "pass": bool(p), "detail": clamp(d)} for n, p, d in checks],
        "reason": clamp(reason),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(0 if ok else 1)


def grader_error(message):
    sys.stderr.write("[%s] grader error: %s\n" % (TASK_ID, clamp(message)))
    raise SystemExit(2)


def load_truth(task_dir):
    """从 fixtures 独立重算真值（发布说明 + 制品字节）。"""
    fixtures = Path(task_dir) / "fixtures"
    notes = fixtures / "release.md"
    if not notes.is_file():
        grader_error("缺少 fixtures/release.md: %s" % notes)
    try:
        text = notes.read_text(encoding="utf-8")
    except Exception as exc:
        grader_error("fixtures/release.md 不可读: %r" % (exc,))

    fields = {}
    for line in text.splitlines():
        m = re.match(r"^- (组件名|版本|发布日期|制品):\s*(\S.*)$", line.strip())
        if m:
            fields[m.group(1)] = m.group(2).strip()
    missing = [k for k in ("组件名", "版本", "发布日期", "制品") if k not in fields]
    if missing:
        grader_error("fixtures/release.md 缺字段: %s" % missing)

    dependencies = []
    for line in text.splitlines():
        m = re.match(r"^\|\s*([A-Za-z0-9][A-Za-z0-9_.-]*)\s*\|\s*([0-9][0-9A-Za-z.\-]*)\s*\|\s*$", line.strip())
        if m:
            dependencies.append({"name": m.group(1), "min_version": m.group(2)})
    if not dependencies:
        grader_error("fixtures/release.md 里解析不到依赖表")

    artifact_file = fields["制品"]
    artifact_path = fixtures / artifact_file
    if not artifact_path.is_file():
        grader_error("缺少制品文件 fixtures/%s" % artifact_file)
    data = artifact_path.read_bytes()

    return {
        "schema_version": "1.0",
        "component": {
            "name": fields["组件名"],
            "version": fields["版本"],
            "release_date": fields["发布日期"],
        },
        "artifact": {
            "file": artifact_file,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        },
        "dependencies": dependencies,
    }


def check_keys(name, value, expected_keys, label):
    if not isinstance(value, dict):
        return (name, False, "期望 %s 是 JSON 对象，实际 %s" % (label, type(value).__name__))
    actual = set(value)
    if actual != expected_keys:
        return (name, False, "期望 %s 键集 %s，实际 %s"
                % (label, sorted(expected_keys), sorted(actual)))
    return (name, True, "%s 键集与契约一致" % label)


def main(argv=None):
    ap = argparse.ArgumentParser(description="T03 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    truth = load_truth(task_dir)

    checks = []
    path = run_dir / "manifest.json"
    exists = path.is_file() and path.stat().st_size > 0
    checks.append(("file-exists", exists,
                   "期望 %s 存在且非空，实际 %s" % (path, "存在" if exists else "缺失或为空")))

    data = None
    if exists:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            checks.append(("json-parse", False, "期望合法 JSON，实际解析失败: %s" % clamp(exc, 160)))
    if data is None and exists:
        for name in ("top-keys", "schema-version", "component", "artifact-sha256",
                     "artifact-bytes", "dependencies"):
            checks.append((name, False, "未执行：manifest.json 无法解析"))
        emit(False, checks, "manifest.json 不是合法 JSON")

    if not exists:
        for name in ("json-parse", "top-keys", "schema-version", "component",
                     "artifact-sha256", "artifact-bytes", "dependencies"):
            checks.append((name, False, "未执行：manifest.json 缺失"))
        emit(False, checks, "产物 manifest.json 不存在，判据无法满足")

    checks.append(("json-parse", True, "JSON 解析通过"))
    if not isinstance(data, dict):
        for name in ("top-keys", "schema-version", "component", "artifact-sha256",
                     "artifact-bytes", "dependencies"):
            checks.append((name, False, "未执行：顶层不是对象"))
        emit(False, checks, "manifest.json 顶层不是 JSON 对象")

    checks.append(check_keys("top-keys", data, TOP_KEYS, "顶层"))

    schema_ok = isinstance(data.get("schema_version"), str) and data.get("schema_version") == "1.0"
    checks.append(("schema-version", schema_ok,
                   "期望 \"1.0\"（字符串），实际 %s" % dump(data.get("schema_version"))))

    component = data.get("component")
    component_checks = [check_keys("component-keys", component, COMPONENT_KEYS, "component"),
                        ("component-version-format",
                         isinstance(component, dict) and isinstance(component.get("version"), str)
                         and bool(VERSION_RE.match(component.get("version") or "")),
                         "期望 version 形如 2.4.1，实际 %s" % dump((component or {}).get("version") if isinstance(component, dict) else component)),
                        ("component-date-format",
                         isinstance(component, dict) and isinstance(component.get("release_date"), str)
                         and bool(DATE_RE.match(component.get("release_date") or "")),
                         "期望 release_date 形如 2026-03-09，实际 %s" % dump((component or {}).get("release_date") if isinstance(component, dict) else component)),
                        ("component-values", component == truth["component"],
                         "期望 %s，实际 %s" % (dump(truth["component"]), dump(component)))]
    checks.extend(component_checks)

    artifact = data.get("artifact")
    checks.append(check_keys("artifact-keys", artifact, ARTIFACT_KEYS, "artifact"))
    actual_sha = artifact.get("sha256") if isinstance(artifact, dict) else None
    sha_ok = isinstance(actual_sha, str) and bool(SHA_RE.match(actual_sha)) and actual_sha == truth["artifact"]["sha256"]
    checks.append(("artifact-sha256", sha_ok,
                   "期望 %s（小写 64 位），实际 %s" % (truth["artifact"]["sha256"], dump(actual_sha))))
    actual_bytes = artifact.get("bytes") if isinstance(artifact, dict) else None
    bytes_ok = (isinstance(actual_bytes, int) and not isinstance(actual_bytes, bool)
                and actual_bytes == truth["artifact"]["bytes"])
    checks.append(("artifact-bytes", bytes_ok,
                   "期望 %r（int），实际 %s" % (truth["artifact"]["bytes"], dump(actual_bytes))))
    actual_file = artifact.get("file") if isinstance(artifact, dict) else None
    checks.append(("artifact-file", actual_file == truth["artifact"]["file"],
                   "期望 %s，实际 %s" % (dump(truth["artifact"]["file"]), dump(actual_file))))

    deps = data.get("dependencies")
    deps_ok = isinstance(deps, list) and len(deps) == len(truth["dependencies"]) and all(
        isinstance(item, dict) and set(item) == DEP_KEYS for item in deps
    ) and deps == truth["dependencies"]
    detail = "期望 %s，实际 %s" % (dump(truth["dependencies"]), dump(deps))
    checks.append(("dependencies", deps_ok, detail))

    all_ok = all(p for _, p, _ in checks)
    passed = sum(1 for _, p, _ in checks if p)
    emit(all_ok, checks, "%d/%d 项检查通过" % (passed, len(checks)))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        sys.stderr.write("[%s] grader crash: %r\n" % (TASK_ID, exc))
        raise SystemExit(2)
