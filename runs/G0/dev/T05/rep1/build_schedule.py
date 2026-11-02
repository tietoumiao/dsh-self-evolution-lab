# -*- coding: utf-8 -*-
"""Compute the dependency-graph schedule for input/jobs.json."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
IN_PATH = os.path.join(BASE, "input", "jobs.json")
OUT_PATH = os.path.join(BASE, "schedule.json")

with open(IN_PATH, "r", encoding="utf-8-sig") as f:
    jobs = json.load(f)["jobs"]

dur = {j["id"]: int(j["duration"]) for j in jobs}
deps = {j["id"]: list(j["deps"]) for j in jobs}
ids = [j["id"] for j in jobs]
assert len(ids) == len(set(ids)), "duplicate ids"

# ---- earliest_start (memoised DFS; graph is acyclic by contract) ----
es = {}


def earliest_start(j):
    if j in es:
        return es[j]
    d = deps[j]
    es[j] = 0 if not d else max(earliest_start(p) + dur[p] for p in d)
    return es[j]


for j in ids:
    earliest_start(j)

finish = {j: es[j] + dur[j] for j in ids}
makespan = max(finish.values())
total_work = sum(dur.values())

# ---- Kahn topological order, smallest id (ASCII) first ----
indeg = {j: len(deps[j]) for j in ids}
children = {j: [] for j in ids}
for j in ids:
    for p in deps[j]:
        children[p].append(j)

ready = sorted([j for j in ids if indeg[j] == 0])
order = []
while ready:
    cur = ready.pop(0)
    order.append(cur)
    for c in children[cur]:
        indeg[c] -= 1
        if indeg[c] == 0:
            ready.append(c)
    ready.sort()

assert len(order) == len(ids), "cycle detected or order incomplete"

# ---- critical path ----
end = min((j for j in ids if finish[j] == makespan), key=lambda x: (finish[x], x))
chain = [end]
cur = end
while deps[cur]:
    nxt = min(deps[cur], key=lambda x: (-finish[x], x))
    chain.append(nxt)
    cur = nxt
chain.reverse()

schedule = {
    "makespan": int(makespan),
    "total_work": int(total_work),
    "order": order,
    "earliest_start": {j: int(es[j]) for j in ids},
    "critical_path": chain,
}

with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
    json.dump(schedule, f, ensure_ascii=False, indent=2, sort_keys=False)
    f.write("\n")

print(json.dumps(schedule, ensure_ascii=False, indent=2))
