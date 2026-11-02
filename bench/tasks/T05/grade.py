#!/usr/bin/env python3
"""T05 判分器：从 fixtures/jobs.json 独立重算调度真值，与产物逐键比对。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
"""

import argparse
import heapq
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK_ID = "T05"
TOP_KEYS = {"makespan", "total_work", "order", "earliest_start", "critical_path"}


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


def load_jobs(task_dir):
    source = Path(task_dir) / "fixtures" / "jobs.json"
    if not source.is_file():
        grader_error("缺少 fixtures/jobs.json: %s" % source)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        jobs = data["jobs"]
        ids = [job["id"] for job in jobs]
        durations = {job["id"]: int(job["duration"]) for job in jobs}
        deps = {job["id"]: list(job["deps"]) for job in jobs}
    except Exception as exc:
        grader_error("fixtures/jobs.json 不可解析: %r" % (exc,))
    if len(set(ids)) != len(ids):
        grader_error("fixtures/jobs.json 里 id 重复")
    for job_id, items in deps.items():
        for item in items:
            if item not in durations:
                grader_error("jobs.json 依赖了不存在的 id: %s -> %s" % (job_id, item))
    return ids, durations, deps


def compute_truth(ids, durations, deps):
    # 拓扑序（Kahn，最小 id 优先）
    remaining = {job_id: len(deps[job_id]) for job_id in ids}
    children = {job_id: [] for job_id in ids}
    for job_id in ids:
        for item in deps[job_id]:
            children[item].append(job_id)
    ready = [job_id for job_id in ids if remaining[job_id] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        current = heapq.heappop(ready)
        order.append(current)
        for child in sorted(children[current]):
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, child)
    if len(order) != len(ids):
        grader_error("fixtures/jobs.json 有环，无法给出真值")

    # 最早开始与完成时刻
    earliest = {}
    for job_id in order:
        if deps[job_id]:
            earliest[job_id] = max(earliest[item] + durations[item] for item in deps[job_id])
        else:
            earliest[job_id] = 0
    finish = {job_id: earliest[job_id] + durations[job_id] for job_id in ids}
    makespan = max(finish.values())
    total_work = sum(durations.values())

    # 关键路径：终点 = finish 最大（并列取 id 最小），回溯取 finish 最大的依赖（并列取 id 最小）
    chain = [min((job_id for job_id in ids if finish[job_id] == makespan))]
    while deps[chain[-1]]:
        current = chain[-1]
        best = max(finish[item] for item in deps[current])
        chain.append(min(item for item in deps[current] if finish[item] == best))
    critical_path = list(reversed(chain))

    return {
        "makespan": makespan,
        "total_work": total_work,
        "order": order,
        "earliest_start": {job_id: earliest[job_id] for job_id in sorted(ids)},
        "critical_path": critical_path,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="T05 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    truth = compute_truth(*load_jobs(task_dir))

    checks = []
    path = run_dir / "schedule.json"
    exists = path.is_file() and path.stat().st_size > 0
    checks.append(("file-exists", exists,
                   "期望 %s 存在且非空，实际 %s" % (path, "存在" if exists else "缺失或为空")))
    if not exists:
        for name in ("json-parse", "top-keys", "order", "earliest-start",
                     "makespan-total-work", "critical-path"):
            checks.append((name, False, "未执行：schedule.json 缺失"))
        emit(False, checks, "产物 schedule.json 不存在，判据无法满足")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.append(("json-parse", False, "期望合法 JSON，实际解析失败: %s" % clamp(exc, 160)))
        for name in ("top-keys", "order", "earliest-start", "makespan-total-work", "critical-path"):
            checks.append((name, False, "未执行：JSON 无法解析"))
        emit(False, checks, "schedule.json 不是合法 JSON")
    checks.append(("json-parse", True, "JSON 解析通过"))

    if not isinstance(payload, dict):
        for name in ("top-keys", "order", "earliest-start", "makespan-total-work", "critical-path"):
            checks.append((name, False, "未执行：顶层不是对象"))
        emit(False, checks, "schedule.json 顶层不是 JSON 对象")

    checks.append(("top-keys", set(payload) == TOP_KEYS,
                   "期望键集 %s，实际 %s" % (sorted(TOP_KEYS), sorted(payload))))

    checks.append(("order", payload.get("order") == truth["order"],
                   "期望 %s，实际 %s" % (dump(truth["order"]), dump(payload.get("order")))))

    checks.append(("earliest-start", payload.get("earliest_start") == truth["earliest_start"],
                   "期望 %s，实际 %s" % (dump(truth["earliest_start"]),
                                       dump(payload.get("earliest_start")))))

    makespan_ok = (type(payload.get("makespan")) is int and payload.get("makespan") == truth["makespan"]
                   and type(payload.get("total_work")) is int
                   and payload.get("total_work") == truth["total_work"])
    checks.append(("makespan-total-work", makespan_ok,
                   "期望 makespan=%r total_work=%r，实际 makespan=%s total_work=%s"
                   % (truth["makespan"], truth["total_work"],
                      dump(payload.get("makespan")), dump(payload.get("total_work")))))

    checks.append(("critical-path", payload.get("critical_path") == truth["critical_path"],
                   "期望 %s，实际 %s" % (dump(truth["critical_path"]),
                                       dump(payload.get("critical_path")))))

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
