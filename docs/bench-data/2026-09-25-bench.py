"""Serial headless benchmark driver for token-tool comparison (Serena / Ponytail).

Everything runs against clones under %TEMP%\tokbench. User-scope files
(~/.claude.json, ~/.claude/settings.json) are never modified.
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

B = Path(r"C:\Users\Com\AppData\Local\Temp\tokbench")
RAW = B / "raw"
RAW.mkdir(exist_ok=True)
HOME = Path.home()
CLAUDE = shutil.which("claude")
MODEL = "claude-sonnet-5"

REPOS = {"flatten": B / "flatten", "ish": B / "ish"}

SENTENCE = (
    "When coding, take the laziest path that works: skip what isn't needed, reuse what already "
    "exists in this codebase, prefer the standard library and already-installed dependencies, "
    "write the minimum code, fix bugs at the shared root cause, and leave one small runnable "
    "check for non-trivial logic."
)

COMMON = "질문하지 말고 끝까지 진행해. 커밋은 하지 마."

TASKS = {
    "flatten": {
        "T1": (
            "이 저장소에서 `capture_behavior` 함수가 어디에 정의되어 있고 어디서 호출되는지 모두 찾아서, "
            "각 호출부(파일:줄)가 반환값(BehaviorObservation)을 어떻게 쓰는지 설명해줘. 파일은 수정하지 마. " + COMMON
        ),
        "T2": (
            "버그 리포트: 함수 실행 중 출력된 텍스트를 함께 돌려주는 harness 유틸이 표준출력(stdout)이 아니라 "
            "표준에러(stderr) 텍스트를 돌려준다. 원인을 찾아 최소한으로 수정하고, 회귀 테스트를 tests/ 아래에 추가한 뒤 "
            "저장소 루트에서 `python -m pytest` 로 관련 테스트를 실행해 통과를 확인해줘. " + COMMON
        ),
        "T3": (
            "`src/flatten/_cli_orchestration.py`(약 750줄)를 응집도 있는 여러 모듈로 나누는 리팩토링 계획을 세워줘. "
            "새 모듈 이름, 각 모듈로 옮길 함수/클래스, 순환 임포트 위험, 단계별 순서를 포함하고 600단어 이내로. "
            "파일은 수정하지 마. " + COMMON
        ),
    },
    "ish": {
        "T1": (
            "collector/ 아래에서 (테스트 파일 제외) 어떤 모듈들이 `load_config()` 를 호출하는지 모두 찾고, "
            "각 모듈이 반환된 CollectorConfig 의 어떤 필드를 실제로 쓰는지 표로 정리해줘. 파일은 수정하지 마. " + COMMON
        ),
        "T2": (
            "버그 리포트: 분봉(minute bars) 수집기의 숫자 파싱이 문자열 \"NaN\"(대소문자 혼합)을 값 없음(None)이 아니라 "
            "0.0 으로 저장한다. 원인을 찾아 최소한으로 수정하고, 회귀 테스트를 추가한 뒤 "
            "`python -m pytest collector/test_minute_bars.py collector/test_minute_bars_v3.py` 를 실행해 통과를 확인해줘. " + COMMON
        ),
        "T3": (
            "`collector/minute_bars.py`(약 1050줄)를 응집도 있는 여러 모듈로 나누는 리팩토링 계획을 세워줘. "
            "새 모듈 이름, 각 모듈로 옮길 함수/클래스, 순환 임포트 위험, 단계별 순서를 포함하고 600단어 이내로. "
            "파일은 수정하지 마. " + COMMON
        ),
    },
}

SERENA_ENV = {
    "UV_CACHE_DIR": str(B / "uv_cache"),
    "UV_PYTHON_INSTALL_DIR": str(B / "uv_python"),
    "SERENA_HOME": str(B / "serena_home"),
    "SERENA_USAGE_REPORTING": "false",
    "PYRIGHT_PYTHON_CACHE_DIR": str(B / "pyright_cache"),
    "PYTHONUTF8": "1",
}
SERENA_ARGS = [
    "--from", str(B / "serena_src"), "serena", "start-mcp-server",
    "--context", "claude-code",
    "--mode", "interactive", "--mode", "editing", "--mode", "no-memories", "--mode", "no-onboarding",
    "--project-from-cwd",
    "--enable-web-dashboard", "false", "--open-web-dashboard", "false",
    "--log-level", "WARNING",
]

PONY = B / "ponytail_src"
PONY_HOME = B / "ponytail_home"


def sh(cmd, cwd=None, env=None, check=False, timeout=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, check=check)


def git(repo, *args):
    return sh(["git", "-C", str(repo), *args])


def ram_pct():
    out = sh(["powershell", "-NoProfile", "-Command",
              "$o=Get-CimInstance Win32_OperatingSystem;"
              "[math]::Round((1-$o.FreePhysicalMemory/$o.TotalVisibleMemorySize)*100,1)"]).stdout.strip()
    return float(out)


def bench_procs(since=None):
    pat = 'tokbench|serena|pyright' if since is None else 'tokbench|serena|pyright|seekstone|server-filesystem'
    """orphaned helper processes (dead parent) left behind by a headless run: serena/pyright/uv/npx-MCP node.
    Only processes whose parent no longer exists are returned, so live sessions of the user are never touched."""
    since_ps = "$null" if since is None else "[datetime]'" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(since)) + "'"
    ps = (
        "$all=Get-CimInstance Win32_Process; $live=@{}; $all|ForEach-Object{$live[[int]$_.ProcessId]=1};"
        f"$since={since_ps};"
        "$all|Where-Object{ ($_.Name -match '^(node|python|pythonw|uv|uvx)[.]exe$') -and -not $live.ContainsKey([int]$_.ParentProcessId) -and "
        "$_.CommandLine -match '" + pat + "' -and "
        "($since -eq $null -or $_.CreationDate -ge $since) } | ForEach-Object { \"$($_.ProcessId)|$($_.Name)\" }"
    )
    out = sh(["powershell", "-NoProfile", "-Command", ps]).stdout.strip().splitlines()
    return [x for x in out if x]


def kill_tree(pid):
    sh(["taskkill", "/F", "/T", "/PID", str(pid)])


# ---------------------------------------------------------------- repo state
def reset_repo(name):
    repo = REPOS[name]
    git(repo, "checkout", "-q", "bench-base")
    git(repo, "reset", "-q", "--hard")
    git(repo, "clean", "-fdq", "-e", ".serena")
    for p in [repo / ".claude" / "settings.local.json"]:
        if p.exists():
            p.unlink()
    for d in (repo / ".claude" / "skills").glob("ponytail*") if (repo / ".claude" / "skills").exists() else []:
        shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(repo / ".serena" / "memories", ignore_errors=True)
    for f in (PONY_HOME / ".ponytail-active",):
        if f.exists():
            f.unlink()


def apply_condition(name, cond):
    repo = REPOS[name]
    if cond == "A":
        return
    if cond == "B":
        p = repo / ".mcp.json"
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"mcpServers": {}}
        d["mcpServers"]["serena"] = {"command": "uvx", "args": SERENA_ARGS, "env": SERENA_ENV}
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif cond == "C":
        def hk(script, matcher=None):
            cmd = f'CLAUDE_CONFIG_DIR="{PONY_HOME.as_posix()}" node "{(PONY / "hooks" / script).as_posix()}"'
            h = {"hooks": [{"type": "command", "command": cmd, "timeout": 5}]}
            if matcher:
                h["matcher"] = matcher
            return [h]
        s = {"hooks": {
            "SessionStart": hk("ponytail-activate.js", "startup|resume|clear|compact"),
            "UserPromptSubmit": hk("ponytail-mode-tracker.js"),
            "SubagentStart": hk("ponytail-subagent.js"),
        }}
        (repo / ".claude").mkdir(exist_ok=True)
        (repo / ".claude" / "settings.local.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
        skills = repo / ".claude" / "skills"
        skills.mkdir(parents=True, exist_ok=True)
        for sd in (PONY / "skills").iterdir():
            shutil.copytree(sd, skills / sd.name, dirs_exist_ok=True)
    elif cond == "D":
        p = repo / "CLAUDE.md"
        t = p.read_text(encoding="utf-8")
        p.write_text(t.rstrip("\n") + "\n\n## Coding style\n\n" + SENTENCE + "\n", encoding="utf-8")
    else:
        raise ValueError(cond)


# ---------------------------------------------------------------- metrics
def find_session(sid):
    for p in (HOME / ".claude" / "projects").glob(f"*/{sid}.jsonl"):
        return p
    return None


def session_metrics(path):
    calls = {}  # message id -> usage (max output)
    order = []
    tool_counts = {}
    seen_tu = set()
    sidechain = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message", {})
        mid = m.get("id") or d.get("uuid")
        u = m.get("usage") or {}
        if d.get("isSidechain"):
            sidechain += 1
        for blk in m.get("content", []) or []:
            if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("id") not in seen_tu:
                seen_tu.add(blk.get("id"))
                tool_counts[blk["name"]] = tool_counts.get(blk["name"], 0) + 1
        if mid not in calls:
            order.append(mid)
            calls[mid] = u
        else:
            if (u.get("output_tokens") or 0) >= (calls[mid].get("output_tokens") or 0):
                calls[mid] = u
    ctx = []
    tot = dict(input=0, cache_read=0, cache_create=0, output=0)
    for mid in order:
        u = calls[mid]
        i, cr, cc, o = (u.get("input_tokens") or 0, u.get("cache_read_input_tokens") or 0,
                        u.get("cache_creation_input_tokens") or 0, u.get("output_tokens") or 0)
        tot["input"] += i; tot["cache_read"] += cr; tot["cache_create"] += cc; tot["output"] += o
        ctx.append(i + cr + cc)
    n = len(ctx)
    slope = None
    if n >= 2:
        xs = list(range(n)); mx = sum(xs) / n; my = sum(ctx) / n
        den = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ctx)) / den if den else None
    return dict(api_calls=n, tok_in=tot["input"], tok_cache_read=tot["cache_read"], tok_cache_create=tot["cache_create"],
                tok_out=tot["output"], tok_ctx_total=tot["input"] + tot["cache_read"] + tot["cache_create"],
                ctx_first=ctx[0] if ctx else None, ctx_last=ctx[-1] if ctx else None, ctx_slope=slope,
                sidechain_msgs=sidechain, tool_counts=tool_counts,
                serena_calls=sum(v for k, v in tool_counts.items() if k.startswith("mcp__serena__")))


# ---------------------------------------------------------------- graders
def changed_files(repo):
    out = git(repo, "status", "--porcelain", "-uall").stdout.splitlines()
    res = []
    for l in out:
        path = l[3:].strip().strip('"')
        if path.startswith(".serena/") or path.startswith(".claude/skills/ponytail") or path in (".claude/settings.local.json", ".mcp.json", "CLAUDE.md"):
            continue
        res.append((l[:2], path))
    return res


def pytest(repo, args, env, timeout=600):
    r = sh([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *args], cwd=repo, env=env, timeout=timeout)
    tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
    return r.returncode == 0, tail[0]


def grade_bug(name, env):
    repo = REPOS[name]
    ch = changed_files(repo)
    test_files = [p for st, p in ch if re.search(r"(^|/)test_[^/]*\.py$", p) and p.endswith(".py")]
    src_files = [p for st, p in ch if p.endswith(".py") and p not in test_files]
    if name == "flatten":
        gsrc = "import sys\nfrom flatten.harness import capture_side_effects\n\ndef _f():\n    print('out')\n    print('err', file=sys.stderr)\n    return 7\n\n\ndef test_grader():\n    assert capture_side_effects(_f) == (7, 'out\\n')\n"
        gdst = "tests/test_zz_grader.py"; suite = ["tests"]; bugfile = "src/flatten/harness.py"
    else:
        gsrc = "from collector.minute_bars import _num\n\n\ndef test_grader():\n    assert _num('NaN') is None\n    assert _num('nan') is None\n    assert _num('1.5') == 1.5\n"
        gdst = "collector/test_zz_grader.py"; suite = ["collector/test_minute_bars.py", "collector/test_minute_bars_v3.py"]; bugfile = "collector/minute_bars.py"
    (repo / gdst).write_text(gsrc, encoding="utf-8")
    fix_ok, gtail = pytest(repo, [gdst], env)
    suite_ok, stail = pytest(repo, suite, env)
    (repo / gdst).unlink()
    own_ok = None; effective = None
    tf = [t for t in test_files if t != gdst]
    if tf:
        own_ok, _ = pytest(repo, tf, env)
        fixed = (repo / bugfile).read_bytes()
        (repo / bugfile).write_bytes(git(repo, "show", f"bench-base:{bugfile}").stdout.encode("utf-8") if False else
                                     subprocess.run(["git", "-C", str(repo), "show", f"bench-base:{bugfile}"], capture_output=True).stdout)
        eff_pass, _ = pytest(repo, tf, env)
        (repo / bugfile).write_bytes(fixed)
        effective = not eff_pass
    return dict(fix_ok=fix_ok, suite_ok=suite_ok, suite_tail=stail, tests_added=bool(tf), own_tests_pass=own_ok,
                test_effective=effective, changed=[p for _, p in ch],
                success=bool(fix_ok and suite_ok and tf and own_ok and effective))


def defs_in(path):
    import ast
    t = ast.parse(Path(path).read_text(encoding="utf-8"))
    return [n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]


def grade_read(name, task, answer, repo_changes):
    repo = REPOS[name]
    out = dict(modified_files=repo_changes)
    a = answer or ""
    if (name, task) == ("flatten", "T1"):
        want = ["comparator", "compare", "capture_side_effects", "compute_behavior_hash", "assert_equivalent", "harness.py"]
        hit = [w for w in want if w in a]
        out.update(expected=len(want), found=len(hit), recall=len(hit) / len(want), missing=[w for w in want if w not in a])
    elif (name, task) == ("ish", "T1"):
        truth = ["cleanup_mock_quotes", "corporate_actions", "download_bulk", "fetch_stocks", "import_bulk", "main",
                 "mark_contamination", "migrate_dong_identity", "migrate_monthly_rent", "migrate_property_types",
                 "migrate_ri_codes", "minute_bars", "renormalize_rent", "screen"]
        allmods = [p.stem for p in (repo / "collector").glob("*.py")]
        found = [m for m in truth if re.search(r"\b" + re.escape(m) + r"(\.py)?\b", a)]
        # false positives: other collector modules named as callers (table rows); rough
        fp = [m for m in allmods if m not in truth and m not in ("config", "__init__") and re.search(r"\b" + re.escape(m) + r"(\.py)\b", a)]
        out.update(expected=len(truth), found=len(found), recall=len(found) / len(truth), missing=[m for m in truth if m not in found], false_pos=fp)
    else:
        target = repo / ("src/flatten/_cli_orchestration.py" if name == "flatten" else "collector/minute_bars.py")
        names = defs_in(target)
        mentioned = [n for n in names if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", a)]
        toks = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\(\))?`", a))
        allnames = set()
        for f in list(repo.glob("src/**/*.py")) + list(repo.glob("collector/*.py")):
            try:
                allnames.update(defs_in(f))
            except Exception:
                pass
        unknown = sorted(t for t in toks if ("_" in t) and t not in allnames and not t.endswith("py"))
        out.update(target_defs=len(names), mentioned=len(mentioned), coverage=len(mentioned) / max(1, len(names)),
                   unknown_identifiers=unknown[:40], n_unknown=len(unknown), words=len(a.split()))
    return out


# ---------------------------------------------------------------- run
def build_cmd(cond):
    allowed = ["Bash", "Read", "Edit", "Write", "Glob", "Grep", "mcp__flatten-filesystem"]
    if cond == "B":
        allowed.append("mcp__serena")
    deny = ["WebFetch", "WebSearch", "Bash(git push:*)", "Bash(git commit:*)", "Bash(git reset:*)",
            "Bash(git remote:*)", "Bash(git stash:*)", "Bash(git clean:*)", "Bash(git checkout:*)"]
    return [CLAUDE, "-p", "--model", MODEL, "--output-format", "stream-json", "--verbose",
            "--settings", json.dumps({"enabledPlugins": {"claude-mem@thedotmack": False}}),
            "--max-turns", "60",
            "--allowedTools", *allowed, "--disallowedTools", *deny]


def run_one(name, task, cond, rep, tag=""):
    rid = f"{name}-{task}-{cond}-r{rep}{tag}"
    if (RAW / f"{rid}.done").exists():
        print("skip", rid); return None
    # RAM gate
    t0 = time.time()
    while True:
        r = ram_pct()
        if r >= 90:
            print("RAM >=90% abort", r); (B / "STOP").write_text(f"RAM {r} before {rid}")
            sys.exit(3)
        if r > 85:
            if time.time() - t0 > 1200:
                (B / "STOP").write_text(f"RAM stuck {r} before {rid}"); sys.exit(3)
            print("RAM", r, "waiting..."); time.sleep(30); continue
        break
    ram_before = r
    stale = bench_procs()
    for x in stale:
        kill_tree(x.split("|")[0])
    reset_repo(name)
    apply_condition(name, cond)
    repo = REPOS[name]
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "OPENROUTER_API_KEY")}
    env["PYTHONUTF8"] = "1"
    if name == "flatten":
        env["PYTHONPATH"] = str(repo / "src")
    else:
        env.pop("PYTHONPATH", None)
    prompt = TASKS[name][task]
    cmd = build_cmd(cond)
    start = time.time()
    timed_out = False
    p = subprocess.Popen(cmd, cwd=repo, env=env, stdin=subprocess.PIPE, stdout=open(RAW / f"{rid}.stream.jsonl", "w", encoding="utf-8"),
                         stderr=open(RAW / f"{rid}.stderr", "w", encoding="utf-8"), text=True, encoding="utf-8")
    try:
        p.stdin.write(prompt); p.stdin.close()
        p.wait(timeout=1500)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(p.pid)
    wall = time.time() - start
    ram_after = ram_pct()
    orphans = bench_procs(since=start - 5)
    for x in orphans:
        kill_tree(x.split("|")[0])
    # parse stream
    sid = None; result = {}; init = {}
    for line in (RAW / f"{rid}.stream.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            sid = d.get("session_id"); init = d
        if d.get("type") == "result":
            result = d
    row = dict(id=rid, repo=name, task=task, cond=cond, rep=rep, session_id=sid, wall_s=round(wall, 1), timed_out=timed_out,
               ram_before=ram_before, ram_after=ram_after, orphan_procs=len(orphans), stale_killed_before=len(stale),
               subtype=result.get("subtype"), is_error=result.get("is_error"), num_turns=result.get("num_turns"),
               duration_ms=result.get("duration_ms"), cost_usd=result.get("total_cost_usd"),
               mcp_servers=[(m.get("name"), m.get("status")) for m in init.get("mcp_servers", [])],
               n_tools=len(init.get("tools", [])))
    sp = find_session(sid) if sid else None
    if sp:
        shutil.copy(sp, RAW / f"{rid}.session.jsonl")
        row.update(session_metrics(sp))
    answer = result.get("result") or ""
    (RAW / f"{rid}.answer.txt").write_text(answer, encoding="utf-8")
    ch = changed_files(repo)
    try:
        if task == "T2":
            row["grade"] = grade_bug(name, env)
        else:
            row["grade"] = grade_read(name, task, answer, [p for _, p in ch])
    except Exception as e:  # keep the run
        row["grade"] = dict(error=repr(e))
    (RAW / f"{rid}.diff.patch").write_text(git(repo, "diff").stdout + "\n--- untracked ---\n" + "\n".join(p for st, p in ch if st == "??"), encoding="utf-8")
    with open(RAW / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (RAW / f"{rid}.done").write_text("1")
    reset_repo(name)
    print(json.dumps({k: row.get(k) for k in ("id", "wall_s", "num_turns", "api_calls", "tok_ctx_total", "tok_out", "serena_calls", "cost_usd")}, ensure_ascii=False))
    return row


def matrix(reps=(1, 2), conds="ABCD"):
    order = []
    for name in ("flatten", "ish"):
        for task in ("T1", "T2", "T3"):
            for rep in reps:
                cs = list(conds) if rep % 2 == 1 else list(reversed(conds))
                for c in cs:
                    order.append((name, task, c, rep))
    return order


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "matrix":
        for (n, t, c, r) in matrix():
            if (B / "STOP").exists():
                print("STOP file present"); sys.exit(4)
            run_one(n, t, c, r)
    elif args and args[0] == "one":
        n, t, c, r = args[1], args[2], args[3], int(args[4])
        run_one(n, t, c, r, tag=(args[5] if len(args) > 5 else ""))
