# -*- coding: utf-8 -*-
"""Independent self-check of schedule.json against input/jobs.json."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
raw = open(os.path.join(BASE, "schedule.json"), "rb").read()
assert not raw.startswith(b"\xef\xbb\xbf"), "BOM present"
text = raw.decode("utf-8")
sched = json.loads(text)
jobs = json.loads(open(os.path.join(BASE, "input", "jobs.json"), encoding="utf-8-sig").read())["jobs"]

dur = {j["id"]: j["duration"] for j in jobs}
deps = {j["id"]: j["deps"] for j in jobs}
ids = set(dur)
errs = []

# 1 key set at top level
if set(sched) != {"makespan", "total_work", "order", "earliest_start", "critical_path"}:
    errs.append("top-level keys wrong: %s" % sorted(sched))
elif len(sched) != 5:
    errs.append("top-level key count != 5")

# 2 integer types (reject strings / floats)
for k in ("makespan", "total_work"):
    if not isinstance(sched[k], int) or isinstance(sched[k], bool):
        errs.append("%s not int" % k)
if not isinstance(sched["order"], list):
    errs.append("order not list")
for j, v in sched["earliest_start"].items():
    if not isinstance(v, int) or isinstance(v, bool):
        errs.append("earliest_start[%s] not int" % j)

es = sched["earliest_start"]

# 3 key set of earliest_start
if set(es) != ids:
    errs.append("earliest_start keys mismatch: missing=%s extra=%s" % (ids - set(es), set(es) - ids))

# 4 recompute earliest_start by brute force over all topological layers
calc = {}


def es_of(j, seen=()):
    if j in calc:
        return calc[j]
    assert j not in seen, "cycle"
    v = 0 if not deps[j] else max(es_of(p, seen + (j,)) + dur[p] for p in deps[j])
    calc[j] = v
    return v


for j in ids:
    calc[j] = es_of(j)
if calc != es:
    errs.append("earliest_start values differ from recomputation")

# 5 makespan / total_work
fin = {j: calc[j] + dur[j] for j in ids}
if sched["makespan"] != max(fin.values()):
    errs.append("makespan mismatch")
if sched["total_work"] != sum(dur.values()):
    errs.append("total_work mismatch")

# 6 order: permutation, topological, min-id greedy (replayed independently)
order = sched["order"]
if sorted(order) != sorted(ids):
    errs.append("order not a permutation of ids")
if len(order) != len(ids):
    errs.append("order length != job count")
placed = set()
for j in order:
    if not set(deps[j]) <= placed:
        errs.append("order violates deps at %s" % j)
        break
    placed.add(j)
# replay greedy
rem = set(ids)
replay = []
while rem:
    cand = sorted(j for j in rem if set(deps[j]) <= set(replay))
    if not cand:
        errs.append("replay: no candidate (cycle)")
        break
    replay.append(cand[0])
    rem.discard(cand[0])
if replay != list(order):
    errs.append("order is not the min-id Kahn order; expected %s" % replay)

# 7 critical path
cp = sched["critical_path"]
if not cp:
    errs.append("critical_path empty")
else:
    # array is forward-ordered: cp[i] must be a real dependency of cp[i+1],
    # and must be the max-finish / min-id choice among cp[i+1]'s dependencies.
    for a, b in zip(cp, cp[1:]):
        if a not in deps[b]:
            errs.append("critical_path edge %s->%s is not a real dependency" % (a, b))
            continue
        want = min(deps[b], key=lambda x: (-fin[x], x))
        if want != a:
            errs.append("critical_path step into %s should come from %s not %s" % (b, want, a))
    end = cp[-1]
    if fin[end] != max(fin.values()):
        errs.append("critical_path end %s is not a makespan job" % end)
    if end != min((j for j in ids if fin[j] == max(fin.values())), key=lambda x: (fin[x], x)):
        errs.append("critical_path end tie-break wrong")
    if deps[cp[0]]:
        errs.append("critical_path first element still has deps")
    if sched["makespan"] != calc[end] + dur[end]:
        errs.append("makespan != start(end)+duration(end)")

print("PASS" if not errs else "FAIL")
for e in errs:
    print(" -", e)
