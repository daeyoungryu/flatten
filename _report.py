import json, collections
outcomes = collections.Counter()
survived = []
with open("dump_interim.txt", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            pair = json.loads(line)
            to = pair[1].get("test_outcome", "pending")
            outcomes[to] += 1
            if to == "survived":
                mod = pair[0]["mutations"][0]["module_path"]
                op  = pair[0]["mutations"][0]["operator_name"]
                fn  = pair[0]["mutations"][0].get("definition_name","?")
                survived.append(f"{mod} | {op} | {fn}")
        except:
            pass
print("=== Outcome Distribution ===")
for k,v in sorted(outcomes.items(), key=lambda x:-x[1]):
    print(f"  {k}: {v}")
print(f"  TOTAL: {sum(outcomes.values())}")
print()
if survived:
    print("=== Surviving Mutants ===")
    for s in survived:
        print(" ", s)
else:
    print("=== Surviving Mutants: NONE ===")
