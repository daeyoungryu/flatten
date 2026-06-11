
import json, collections
outcomes = collections.Counter()
errors = []
with open('dump_out.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line.startswith('['):
            continue
        try:
            pair = json.loads(line)
            to = pair[1].get('test_outcome', 'pending')
            outcomes[to] += 1
            if to == 'incompetent' and len(errors) < 1:
                errors.append(pair[1].get('output',''))
        except:
            pass
print('Total:', sum(outcomes.values()))
for k,v in sorted(outcomes.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
for e in errors:
    print('SAMPLE:', e[:800])

