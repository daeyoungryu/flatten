import json, statistics as st, sys
from pathlib import Path
RAW = Path(r"C:\Users\Com\AppData\Local\Temp\tokbench\raw")
rows = [json.loads(l) for l in (RAW / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
rows = [r for r in rows if "_pilot" not in r["id"]]
by = {}
for r in rows:
    by[(r["repo"], r["task"], r["cond"], r["rep"])] = r

METRICS = [("tok_ctx_total", "ctx합계"), ("tok_out", "out"), ("api_calls", "API호출"), ("num_turns", "턴"),
           ("ctx_slope", "기울기"), ("wall_s", "초"), ("cost_usd", "USD")]


def q(r, k):
    v = r.get(k)
    return v if isinstance(v, (int, float)) else None


def success(r):
    g = r.get("grade", {})
    if r["task"] == "T2":
        return 1.0 if g.get("success") else 0.0
    if r["task"] == "T1":
        return g.get("recall")
    return g.get("coverage")


def verdict(repo, task, cond, key):
    """pairwise-by-rep vs A: effect only if both reps same sign and |delta|>=5%."""
    ds = []
    for rep in (1, 2):
        a, x = by.get((repo, task, "A", rep)), by.get((repo, task, cond, rep))
        if not a or not x or q(a, key) in (None, 0) or q(x, key) is None:
            return None
        ds.append((q(x, key) - q(a, key)) / q(a, key) * 100)
    if all(d >= 5 for d in ds):
        return "+", ds
    if all(d <= -5 for d in ds):
        return "-", ds
    return "0", ds


def fmt(v, k):
    if v is None:
        return "-"
    return f"{v:,.0f}" if k in ("tok_ctx_total", "tok_out", "ctx_slope") else f"{v:.2f}" if k == "cost_usd" else f"{v:.1f}"


out = []
for repo in ("flatten", "ish"):
    for task in ("T1", "T2", "T3"):
        out.append(f"\n### {repo} {task}\n")
        out.append("| 조건 | rep | " + " | ".join(m[1] for m in METRICS) + " | 성공/점수 | serena호출 |")
        out.append("|---|---|" + "---|" * (len(METRICS) + 2))
        for cond in "ABCD":
            for rep in (1, 2):
                r = by.get((repo, task, cond, rep))
                if not r:
                    out.append(f"| {cond} | {rep} | (없음) |"); continue
                s = success(r)
                out.append(f"| {cond} | {rep} | " + " | ".join(fmt(q(r, k), k) for k, _ in METRICS) +
                           f" | {'-' if s is None else f'{s:.2f}'} | {r.get('serena_calls', 0)} |")
        out.append("")
        out.append("A 대비 (rep별 Δ%, 판정: 두 rep 모두 같은 방향·≥5%일 때만 효과) — ctx합계 / out / USD")
        for cond in "BCD":
            parts = []
            for key in ("tok_ctx_total", "tok_out", "cost_usd"):
                v = verdict(repo, task, cond, key)
                parts.append(f"{key}: " + ("-" if v is None else f"{v[0]} ({v[1][0]:+.0f}%, {v[1][1]:+.0f}%)"))
            out.append(f"- {cond}: " + " ; ".join(parts))

# pooled (sum over the 6 repo-tasks, per rep)
out.append("\n### 전체 합산 (6개 과제, rep별)\n")
out.append("| 조건 | rep | ctx합계 | out | USD | 초 | 성공점수 평균 |")
out.append("|---|---|---|---|---|---|---|")
tot = {}
for cond in "ABCD":
    for rep in (1, 2):
        rs = [by.get((rp, t, cond, rep)) for rp in ("flatten", "ish") for t in ("T1", "T2", "T3")]
        if any(r is None for r in rs):
            continue
        c = sum(q(r, "tok_ctx_total") or 0 for r in rs); o = sum(q(r, "tok_out") or 0 for r in rs)
        u = sum(q(r, "cost_usd") or 0 for r in rs); w = sum(q(r, "wall_s") or 0 for r in rs)
        sc = st.mean([success(r) or 0 for r in rs])
        tot[(cond, rep)] = (c, o, u, w, sc)
        out.append(f"| {cond} | {rep} | {c:,.0f} | {o:,.0f} | {u:.2f} | {w:.0f} | {sc:.2f} |")
out.append("")
for cond in "BCD":
    ds = []
    for i, name in enumerate(("ctx", "out", "USD", "wall")):
        pr = []
        for rep in (1, 2):
            if ("A", rep) in tot and (cond, rep) in tot:
                pr.append((tot[(cond, rep)][i] - tot[("A", rep)][i]) / tot[("A", rep)][i] * 100)
        ds.append(f"{name} " + "/".join(f"{d:+.1f}%" for d in pr))
    out.append(f"- {cond} vs A (합산): " + " ; ".join(ds))
Path(RAW / "analysis.md").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
