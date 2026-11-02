import json, heapq, io, os

base = r"<workspace>/agi/runs/G0/dev/T05/rep2"
raw = open(os.path.join(base, "input", "jobs.json"), "rb").read()
jobs = json.loads(raw.decode("utf-8"))["jobs"]
dur = {j["id"]: j["duration"] for j in jobs}
deps = {j["id"]: list(j["deps"]) for j in jobs}
ids = [j["id"] for j in jobs]

# earliest_start (iterative relaxation via topo order)
indeg = {i: len(deps[i]) for i in ids}
children = {i: [] for i in ids}
for i in ids:
    for d in deps[i]:
        children[d].append(i)
heap = [i for i in ids if indeg[i] == 0]
heapq.heapify(heap)
order = []
es = {}
while heap:
    x = heapq.heappop(heap)
    order.append(x)
    es[x] = 0 if not deps[x] else max(es[d] + dur[d] for d in deps[x])
    for c in children[x]:
        indeg[c] -= 1
        if indeg[c] == 0:
            heapq.heappush(heap, c)

finish = {i: es[i] + dur[i] for i in ids}
makespan = max(finish.values())
total_work = sum(dur.values())

term = sorted(ids, key=lambda i: (-finish[i], i))[0]
path = [term]
cur = term
while deps[cur]:
    cur = sorted(deps[cur], key=lambda i: (-finish[i], i))[0]
    path.append(cur)
path.reverse()

expected = {
    "makespan": makespan,
    "total_work": total_work,
    "order": order,
    "earliest_start": es,
    "critical_path": path,
}

sraw = open(os.path.join(base, "schedule.json"), "rb").read()
problems = []
if sraw.startswith(b"\xef\xbb\xbf"):
    problems.append("schedule.json has UTF-8 BOM")
got = json.loads(sraw.decode("utf-8"))

if list(got.keys()).__len__() != 5 or set(got.keys()) != set(expected.keys()):
    problems.append("top-level keys mismatch: %r" % (list(got.keys()),))
if set(got["earliest_start"].keys()) != set(ids):
    problems.append("earliest_start key set mismatch")
for k in ("makespan", "total_work"):
    if not isinstance(got[k], int) or isinstance(got[k], bool):
        problems.append("%s is not a JSON integer" % k)
if any(not isinstance(v, int) or isinstance(v, bool) for v in got["earliest_start"].values()):
    problems.append("earliest_start has non-integer value")
if got["order"] == expected["order"] and len(got["order"]) == len(ids) and sorted(got["order"]) == sorted(ids):
    pass
else:
    problems.append("order mismatch: %r != %r" % (got["order"], expected["order"]))
if got["earliest_start"] != es:
    problems.append("earliest_start mismatch: %r != %r" % (got["earliest_start"], es))
if got["makespan"] != makespan:
    problems.append("makespan mismatch")
if got["makespan"] != finish[got["critical_path"][-1]]:
    problems.append("makespan != terminal finish")
if got["total_work"] != total_work:
    problems.append("total_work mismatch")
if got["critical_path"] != path:
    problems.append("critical_path mismatch: %r != %r" % (got["critical_path"], path))
for a, b in zip(got["critical_path"], got["critical_path"][1:]):
    if a not in deps[b]:
        problems.append("critical_path edge %s->%s is not a real dependency" % (a, b))

# independent Kahn min-id check
print("expected:", json.dumps(expected, sort_keys=False))
print("got     :", json.dumps(got, sort_keys=False))
print("BOM free:", not sraw.startswith(b"\xef\xbb\xbf"))
print("RESULT:", "PASS" if not problems else "FAIL " + "; ".join(problems))
