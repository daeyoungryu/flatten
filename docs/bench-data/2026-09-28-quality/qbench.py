"""Ponytail on/off code-quality A/B on the flatten repo (separate git worktrees, nothing committed).

RAM policy (user decision 2026-09-28): start a run only below 80%, abort the current run above 90%
and retry it later.  Results are compared but never committed; worktrees are removed after each run.
"""
import ctypes, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

Q = Path(r"C:\Users\Com\AppData\Local\Temp\qbench")
RAW = Q / "raw"
WT = Q / "wt"
ORIG = Path(r"C:\Users\Com\Documents\Claude\Projects\flatten")
BASE = "331f899"
HOME = Path.home()
CLAUDE = shutil.which("claude")
MODEL = "claude-sonnet-5"
PONY = Q / "ponytail_src"
PONY_HOME = Q / "ponytail_home"
START_BELOW, ABORT_ABOVE, POLL_S, MAX_ATT = 80.0, 90.0, 300, 3
COMMON = "질문하지 말고 끝까지 진행해. 커밋은 하지 마."

TASKS = {
    "Q1": ("버그 리포트: `BehaviorComparator.compare` 로 여러 케이스를 비교하면 앞쪽 케이스에서 난 불일치가 결과에서 사라진다"
           "(뒤 케이스가 일치하면 `equivalent` 가 True 로 나오기도 한다). 원인을 찾아 최소한으로 수정하고, 회귀 테스트를 tests/ 아래에 "
           "추가한 뒤 저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. " + COMMON),
    "Q2": ("작은 기능 추가: `BehaviorComparator.compare` 에 키워드 전용 선택 인자 `max_mismatches: int | None = None` 을 추가해라. "
           "None 이면 지금 동작과 완전히 같다. 정수면 케이스를 순서대로 비교하다가 누적 불일치 수가 `max_mismatches` 이상이 되는 순간 "
           "나머지 케이스 비교를 중단한다(한 케이스에서 나온 불일치는 잘라내지 않고 모두 포함한다). 반환값의 `cases` 는 지금처럼 전체 케이스 수를 "
           "유지한다. `BehaviorComparisonResult` 에 `truncated: bool = False` 필드를 추가해, 남은 케이스를 건너뛰고 중단했을 때만 True 로 하고 "
           "`to_json()` 결과에도 `\"truncated\"` 키를 넣어라. `max_mismatches < 1` 이면 ValueError. tests/ 아래에 테스트를 추가하고 "
           "저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. " + COMMON),
    "Q3": ("리팩토링: `src/flatten/harness.py` 의 `capture_behavior` 는 정상 종료 경로와 예외 경로에서 stdout/stderr 와 effect collector 수집 "
           "코드가 중복된다. 동작은 정확히 그대로 두고(공개 시그니처, 반환값, effect 딕셔너리 키 순서, collector 호출 방식 포함) 중복을 제거해라. "
           "기존 테스트가 모두 통과해야 하고, 동작 보존을 확인하는 테스트가 필요하면 tests/ 아래에 추가해라. "
           "저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. " + COMMON),
}

SENT = None  # (Ponytail is the treatment; no extra sentence condition here)


class _MS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def ram_pct():
    s = _MS(); s.dwLength = ctypes.sizeof(_MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return round((1 - s.ullAvailPhys / s.ullTotalPhys) * 100, 1)


def status(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    (RAW / "status.txt").write_text(line + "\n", encoding="utf-8")


def sh(cmd, cwd=None, env=None, timeout=None, inp=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, input=inp)


def git(repo, *a):
    return sh(["git", "-C", str(repo), *a])


def wait_for_ram():
    waited = 0
    while True:
        r = ram_pct()
        if r < START_BELOW:
            return r, waited
        status(f"RAM {r}% >= {START_BELOW}% — waiting {POLL_S}s (waited {waited}s)")
        time.sleep(POLL_S); waited += POLL_S


def kill_tree(pid):
    sh(["taskkill", "/F", "/T", "/PID", str(pid)])


# ---------------------------------------------------------------- setup / teardown
def setup(task, cond, rid):
    path = WT / rid
    r = git(ORIG, "worktree", "add", "-q", "--detach", str(path), BASE)
    assert r.returncode == 0, r.stderr
    # keep MCP servers inside the sandbox (tool definitions unchanged)
    mp = path / ".mcp.json"
    if mp.exists():
        d = json.loads(mp.read_text(encoding="utf-8-sig"))
        d["mcpServers"]["flatten-filesystem"]["args"][-1] = str(path)
        d["mcpServers"]["flatten-obsidian"]["env"]["SEEKSTONE_VAULT"] = str(Q / "vault")
        mp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if task == "Q1":  # inject the bug
        cp = path / "src/flatten/comparator.py"
        s = cp.read_text(encoding="utf-8")
        old = "mismatches.extend(_compare_observation(index, left, right))"
        assert old in s
        cp.write_text(s.replace(old, "mismatches = _compare_observation(index, left, right)"), encoding="utf-8", newline="")
    if cond == "ON":
        def hk(script, matcher=None):
            cmd = f'CLAUDE_CONFIG_DIR="{PONY_HOME.as_posix()}" node "{(PONY / "hooks" / script).as_posix()}"'
            h = {"hooks": [{"type": "command", "command": cmd, "timeout": 5}]}
            if matcher:
                h["matcher"] = matcher
            return [h]
        st = {"hooks": {"SessionStart": hk("ponytail-activate.js", "startup|resume|clear|compact"),
                        "UserPromptSubmit": hk("ponytail-mode-tracker.js"), "SubagentStart": hk("ponytail-subagent.js")}}
        (path / ".claude").mkdir(exist_ok=True)
        (path / ".claude" / "settings.local.json").write_text(json.dumps(st, indent=2), encoding="utf-8")
        sk = path / ".claude" / "skills"; sk.mkdir(parents=True, exist_ok=True)
        for sd in (PONY / "skills").iterdir():
            shutil.copytree(sd, sk / sd.name, dirs_exist_ok=True)
    # index = baseline (bug + repoint + condition files), so `git diff` later shows only the agent's work
    git(path, "config", "user.name", "qbench"); git(path, "config", "user.email", "q@example.invalid")
    git(path, "add", "-A")
    if (PONY_HOME / ".ponytail-active").exists():
        (PONY_HOME / ".ponytail-active").unlink()
    return path


def teardown(path):
    git(ORIG, "worktree", "remove", "--force", str(path))
    shutil.rmtree(path, ignore_errors=True)
    git(ORIG, "worktree", "prune")


# ---------------------------------------------------------------- metrics
def find_session(sid):
    for p in (HOME / ".claude" / "projects").glob(f"*/{sid}.jsonl"):
        return p


def session_metrics(path):
    calls, order, tools, seen = {}, [], {}, set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message", {}); mid = m.get("id") or d.get("uuid"); u = m.get("usage") or {}
        for blk in m.get("content", []) or []:
            if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("id") not in seen:
                seen.add(blk.get("id")); tools[blk["name"]] = tools.get(blk["name"], 0) + 1
        if mid not in calls:
            order.append(mid); calls[mid] = u
        elif (u.get("output_tokens") or 0) >= (calls[mid].get("output_tokens") or 0):
            calls[mid] = u
    tot = dict(i=0, r=0, c=0, o=0)
    for mid in order:
        u = calls[mid]
        tot["i"] += u.get("input_tokens") or 0; tot["r"] += u.get("cache_read_input_tokens") or 0
        tot["c"] += u.get("cache_creation_input_tokens") or 0; tot["o"] += u.get("output_tokens") or 0
    return dict(api_calls=len(order), tok_ctx_total=tot["i"] + tot["r"] + tot["c"], tok_out=tot["o"], tool_counts=tools)


# ---------------------------------------------------------------- grading
def pytest(path, args, env, timeout=600):
    r = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args], cwd=path, env=env, timeout=timeout)
    tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
    return r.returncode == 0, tail[0]


def grade(task, path, env):
    st = git(path, "status", "--porcelain", "-uall").stdout.splitlines()
    git(path, "add", "-N", ".")  # so new files show up in `git diff`
    patch = git(path, "diff").stdout
    numstat = git(path, "diff", "--numstat").stdout.strip().splitlines()
    numstat_w = git(path, "diff", "-w", "--numstat").stdout.strip().splitlines()
    files = []
    for l in numstat:
        a, d, f = l.split("\t", 2); files.append((f, int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0))
    test_files = [f for f, _, _ in files if re.search(r"(^|/)test_[^/]*\.py$", f)]
    src_files = [f for f, _, _ in files if f.startswith("src/")]
    expected_src = {"Q1": {"src/flatten/comparator.py"}, "Q2": {"src/flatten/comparator.py"}, "Q3": {"src/flatten/harness.py"}}[task]
    stray = [f for f, _, _ in files if f not in expected_src and not re.search(r"(^|/)test_[^/]*\.py$", f)]
    g = dict(files=[f for f, _, _ in files], src_added=sum(a for f, a, d in files if f.startswith("src/")),
             src_removed=sum(d for f, a, d in files if f.startswith("src/")),
             test_added=sum(a for f, a, d in files if f in test_files), test_removed=sum(d for f, a, d in files if f in test_files),
             stray_files=stray, whitespace_only_lines=sum(int(x.split("\t")[0]) + int(x.split("\t")[1]) for x in numstat)
             - sum(int(x.split("\t")[0]) + int(x.split("\t")[1]) for x in numstat_w),
             ponytail_marker=("ponytail" in patch.lower()), patch_lines=len(patch.splitlines()))
    hid = Path(rf"{Q}\hidden\{task.lower()}.py")
    dst = path / f"tests/test_zz_hidden_{task.lower()}.py"
    dst.write_text(hid.read_text(encoding="utf-8"), encoding="utf-8")
    g["hidden_ok"], g["hidden_tail"] = pytest(path, [str(dst.relative_to(path))], env)
    dst.unlink()
    g["suite_ok"], g["suite_tail"] = pytest(path, ["tests"], env)
    own = [t for t in test_files]
    g["agent_tests"] = own
    if own:
        g["agent_tests_pass"], _ = pytest(path, own, env)
        # regression/feature test must FAIL on the pre-change source; refactor tests must PASS on it
        swap = [f for f in src_files]
        saved = {f: (path / f).read_bytes() for f in swap}
        for f in swap:
            (path / f).write_bytes(subprocess.run(["git", "-C", str(path), "show", f":{f}"], capture_output=True).stdout)
        ok_on_base, _ = pytest(path, own, env)
        for f, b in saved.items():
            (path / f).write_bytes(b)
        g["agent_tests_pass_on_base"] = ok_on_base
        g["test_effective"] = (not ok_on_base) if task in ("Q1", "Q2") else ok_on_base
    else:
        g["agent_tests_pass"] = g["agent_tests_pass_on_base"] = g["test_effective"] = None
    g["success"] = bool(g["hidden_ok"] and g["suite_ok"] and (g["test_effective"] is True))
    return g, patch


# ---------------------------------------------------------------- one run
def run_one(task, cond, rep, attempt=1):
    rid = f"{task}-{cond}-r{rep}"
    if (RAW / f"{rid}.done").exists():
        return "done"
    r, waited = wait_for_ram()
    path = setup(task, cond, rid)
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "OPENROUTER_API_KEY")}
    env["PYTHONUTF8"] = "1"; env["PYTHONPATH"] = str(path / "src")
    deny = ["WebFetch", "WebSearch", "Bash(git push:*)", "Bash(git commit:*)", "Bash(git reset:*)", "Bash(git remote:*)",
            "Bash(git stash:*)", "Bash(git clean:*)", "Bash(git checkout:*)", "Bash(git add:*)", "Bash(git worktree:*)", "Bash(git branch:*)"]
    cmd = [CLAUDE, "-p", "--model", MODEL, "--output-format", "stream-json", "--verbose",
           "--settings", json.dumps({"enabledPlugins": {"claude-mem@thedotmack": False}}), "--max-turns", "60",
           "--allowedTools", "Bash", "Read", "Edit", "Write", "Glob", "Grep", "mcp__flatten-filesystem", "--disallowedTools", *deny]
    stream = RAW / f"{rid}.stream.jsonl"
    p = subprocess.Popen(cmd, cwd=path, env=env, stdin=subprocess.PIPE, stdout=open(stream, "w", encoding="utf-8"),
                         stderr=open(RAW / f"{rid}.stderr", "w", encoding="utf-8"), text=True, encoding="utf-8")
    start = time.time(); p.stdin.write(TASKS[task]); p.stdin.close()
    aborted = timed_out = False; peak = r
    while p.poll() is None:
        time.sleep(8); cur = ram_pct(); peak = max(peak, cur)
        if cur > ABORT_ABOVE:
            aborted = True; break
        if time.time() - start > 1500:
            timed_out = True; break
    if aborted or timed_out:
        kill_tree(p.pid)
    wall = time.time() - start
    if aborted:
        (RAW / f"{rid}.stream.jsonl").rename(RAW / f"{rid}.abort{attempt}.stream.jsonl")
        teardown(path)
        status(f"ABORT {rid} attempt {attempt}: RAM peak {peak}% > {ABORT_ABOVE}% — retry later")
        return "aborted"
    sid = None; result = {}
    for line in stream.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            sid = d.get("session_id")
        if d.get("type") == "result":
            result = d
    row = dict(id=rid, task=task, cond=cond, rep=rep, attempt=attempt, wall_s=round(wall, 1), timed_out=timed_out, ram_peak=peak,
               waited_s=waited, subtype=result.get("subtype"), is_error=result.get("is_error"), num_turns=result.get("num_turns"),
               cost_usd=result.get("total_cost_usd"))
    sp = find_session(sid) if sid else None
    if sp:
        shutil.copy(sp, RAW / f"{rid}.session.jsonl"); row.update(session_metrics(sp))
    (RAW / f"{rid}.answer.txt").write_text(result.get("result") or "", encoding="utf-8")
    try:
        g, patch = grade(task, path, env)
        row["grade"] = g
        (RAW / f"{rid}.patch").write_text(patch, encoding="utf-8")
    except Exception as e:
        row["grade"] = dict(error=repr(e))
    with open(RAW / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (RAW / f"{rid}.done").write_text("1")
    teardown(path)
    status(f"DONE {rid} wall={row['wall_s']}s calls={row.get('api_calls')} out={row.get('tok_out')} success={row['grade'].get('success')} peak={peak}%")
    return "done"


def matrix(reps=(1, 2, 3)):
    order = []
    for task in ("Q1", "Q2", "Q3"):
        for rep in reps:
            cs = ["OFF", "ON"] if rep % 2 == 1 else ["ON", "OFF"]
            order += [(task, c, rep) for c in cs]
    return order


if __name__ == "__main__":
    RAW.mkdir(exist_ok=True); WT.mkdir(exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "one":
        run_one(sys.argv[2], sys.argv[3], int(sys.argv[4])); sys.exit(0)
    queue = [(x, 1) for x in matrix()]; gave_up = []
    while queue:
        if (Q / "STOP").exists():
            status("STOP file present — exiting"); sys.exit(4)
        (t, c, r), att = queue.pop(0)
        if run_one(t, c, r, att) == "aborted":
            (queue.append(((t, c, r), att + 1)) if att < MAX_ATT else gave_up.append(f"{t}-{c}-r{r}"))
    (RAW / "ALLDONE").write_text(json.dumps(dict(gave_up=gave_up))); status(f"ALLDONE gave_up={gave_up}")
