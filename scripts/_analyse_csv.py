import csv

# Deep analysis of item.csv
with open(r'C:\Projects\Assistant\item.csv', encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

print(f'=== item.csv ({len(rows):,} rows) ===')
for field in ['type', 'routine', 'POSITIVE/NEGATIVE', 'bank', 'operation']:
    vals = {r[field].strip() for r in rows if r[field].strip()}
    print(f'\n  {field} ({len(vals)} unique): {sorted(vals)[:25]}')

did_vals = [int(r['description_id']) for r in rows if r['description_id'].strip()]
print(f'\n  description_id: {min(did_vals)}-{max(did_vals)}, missing={len(rows)-len(did_vals)}')
card_ids = sorted({r['card_id'] for r in rows if r['card_id'].strip()})
print(f'  card_id unique: {card_ids[:20]}')

# Check description.csv dimension
with open(r'C:\Projects\Assistant\description.csv', encoding='utf-8-sig', newline='') as f:
    descs = list(csv.DictReader(f))
print(f'\n=== description.csv ({len(descs)} rows) ===')
groups = sorted({d['group'] for d in descs if d['group']})
types  = sorted({d['type']  for d in descs if d['type']})
routines = sorted({d['routine'] for d in descs if d['routine']})
print(f'  group unique ({len(groups)}): {groups}')
print(f'  type unique: {types}')
print(f'  routine unique: {routines}')
active_vals = sorted({d['active'] for d in descs})
print(f'  active values: {active_vals}')

# cards.csv
with open(r'C:\Projects\Assistant\cards.csv', encoding='utf-8-sig', newline='') as f:
    cards = list(csv.DictReader(f))
print(f'\n=== cards.csv ({len(cards)} rows) ===')
for c in cards:
    print(f'  id={c["id"]:3} card={c["card"]:15} active={c["active"]} close_day={c["day_close"]}')

# audit_log sample - understand prev/new JSON keys
import json
with open(r'C:\Projects\Assistant\audit_log.csv', encoding='utf-8-sig', newline='') as f:
    logs = list(csv.DictReader(f))
print(f'\n=== audit_log.csv ({len(logs):,} rows) ===')
ops = sorted({l['operation_type'] for l in logs})
tables = sorted({l['table_name'] for l in logs})
print(f'  operations: {ops}')
print(f'  tables: {tables}')
# Show keys from a new_data JSON to understand full item schema
for l in logs:
    nd = l['new_data'].strip()
    if nd and nd.startswith('{'):
        try:
            keys = sorted(json.loads(nd).keys())
            print(f'  item JSON keys: {keys}')
            break
        except Exception:
            pass
