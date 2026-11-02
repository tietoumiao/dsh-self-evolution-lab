"""Build aggregate.json from input/transactions.csv using exact decimal arithmetic."""
import csv
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'input', 'transactions.csv')
DST = os.path.join(HERE, 'aggregate.json')


def round_half_away_from_zero(fr: Fraction) -> int:
    """Exact rational rounding: .5 goes away from zero."""
    if fr >= 0:
        return int((fr + Fraction(1, 2)).__floor__())
    return -int((-fr + Fraction(1, 2)).__floor__())


rows = []
with open(SRC, newline='', encoding='utf-8') as f:
    for d in csv.DictReader(f):
        rows.append(d)

accounts = {}
monthly = {}
grand = 0
detail = []

for d in rows:
    txn = d['txn_id']
    amt = int(d['amount_cents'])
    rate_str = d['fx_rate'].strip()
    rate = Decimal(rate_str)

    # 1) exact decimal product
    exact = Decimal(amt) * rate
    # 2) exact rational product (independent path)
    fr = Fraction(amt) * Fraction(rate_str)

    usd_dec = int(exact.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    usd_frac = round_half_away_from_zero(fr)
    assert usd_dec == usd_frac, (txn, usd_dec, usd_frac)

    detail.append((txn, d['account'], d['date'], d['currency'], amt, rate_str,
                   str(exact), usd_dec))

    grand += usd_dec

    a = accounts.get(d['account'])
    if a is None:
        a = {'count': 0, 'usd_cents': 0, 'largest_txn': None, '_best': None}
        accounts[d['account']] = a
    a['count'] += 1
    a['usd_cents'] += usd_dec
    if a['_best'] is None or usd_dec > a['_best'] or (
            usd_dec == a['_best'] and txn < a['largest_txn']):
        a['_best'] = usd_dec
        a['largest_txn'] = txn

    mk = d['date'][:7]
    m = monthly.get(mk)
    if m is None:
        m = {'count': 0, 'usd_cents': 0}
        monthly[mk] = m
    m['count'] += 1
    m['usd_cents'] += usd_dec

for a in accounts.values():
    del a['_best']

result = {
    'accounts': accounts,
    'monthly': monthly,
    'grand_total_cents': grand,
}

# --- self checks ---
assert list(result.keys()) == ['accounts', 'monthly', 'grand_total_cents']
assert sum(v['usd_cents'] for v in accounts.values()) == grand
assert sum(v['usd_cents'] for v in monthly.values()) == grand
assert sum(v['count'] for v in accounts.values()) == len(rows)
assert sum(v['count'] for v in monthly.values()) == len(rows)
for v in accounts.values():
    assert set(v.keys()) == {'count', 'usd_cents', 'largest_txn'}
    assert isinstance(v['usd_cents'], int) and isinstance(v['count'], int)
for v in monthly.values():
    assert set(v.keys()) == {'count', 'usd_cents'}
    assert isinstance(v['usd_cents'], int) and isinstance(v['count'], int)
assert isinstance(grand, int)

with open(DST, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('txn_id  acct  date  cur  amount  rate  exact_product -> usd_cents')
for t in detail:
    print('  %-5s %-11s %s %s %8d %-7s %-14s -> %d' % t)
print()
print(json.dumps(result, ensure_ascii=False, indent=2))
