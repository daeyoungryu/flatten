"""v2 driver: longer fixed tasks, extra condition E (= B + one-sentence "prefer Serena" nudge),
conservative memory policy (start only when RAM < 75%, wait 5 min between re-checks,
abort only the current run if RAM > 90% during it, retry later)."""
import ctypes, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
import bench as b

B = b.B
RAW = B / "raw_v2"
RAW.mkdir(exist_ok=True)
b.RAW = RAW

START_BELOW = 75.0
ABORT_ABOVE = 90.0
POLL_WAIT_S = 300
MAX_ATTEMPTS = 4

SENTENCE_E = ("Prefer Serena's symbolic tools (get_symbols_overview, find_symbol, find_referencing_symbols, "
              "replace_symbol_body) over Grep/Read to explore and edit code; fall back to Grep/Read only "
              "when they cannot answer.")

COMMON = b.COMMON

TASKS = {
    "flatten": {
        "T1": (
            "이 저장소에서 `capture_behavior` 가 어디에 정의되고 어디서 호출되는지 모두 찾아라. 그리고 그 호출부를 감싸는 "
            "각 함수/메서드가 `src/` 와 `tests/` 에서 다시 어디서 호출되는지(파일:줄)까지 2단계로 추적해 표로 정리하고, "
            "각 경로를 실제로 커버하는 테스트 파일도 적어라. 파일은 수정하지 마. " + COMMON
        ),
        "T2": (
            "버그 리포트: 함수 실행 중 출력된 텍스트를 함께 돌려주는 harness 유틸이 표준출력(stdout)이 아니라 표준에러(stderr) "
            "텍스트를 돌려준다. (1) 원인을 찾아 최소한으로 수정하고, (2) 회귀 테스트를 tests/ 아래에 추가하고, "
            "(3) 관찰 결과에서 stdout/stderr 를 꺼내는 다른 곳 중 같은 종류의 실수가 더 있는지 src/ 전체를 확인해 파일:줄로 보고하고, "
            "(4) 저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. " + COMMON
        ),
        "T3": (
            "`src/flatten/_cli_orchestration.py`(약 750줄)를 응집도 있는 여러 모듈로 나누는 리팩토링 계획을 세워라. "
            "새 모듈 이름, 각 모듈로 옮길 함수/클래스, 각 새 모듈의 공개 인터페이스 시그니처 스케치, 순환 임포트 위험, 단계별 순서를 포함하고, "
            "분할하면 임포트 경로가 깨질 src/·tests/ 의 파일을 grep 으로 확인해 목록으로 적어라. 900단어 이내. 파일은 수정하지 마. " + COMMON
        ),
    },
    "ish": {
        "T1": (
            "collector/ 아래에서 (테스트 파일 제외) 어떤 모듈들이 `load_config()` 를 호출하는지 모두 찾고, 각 모듈이 반환된 "
            "CollectorConfig 의 어떤 필드를 실제로 쓰는지 표로 정리해라(사용 위치 파일:줄 포함). 또 turso_url/turso_auth_token 을 쓰는 "
            "모듈은 빈 문자열일 때를 어떻게 처리하는지도 적어라. 파일은 수정하지 마. " + COMMON
        ),
        "T2": (
            "버그 리포트: 분봉(minute bars) 수집기의 숫자 파싱이 문자열 \"NaN\"(대소문자 혼합)을 값 없음(None)이 아니라 0.0 으로 저장한다. "
            "(1) 원인을 찾아 최소한으로 수정하고, (2) 회귀 테스트를 추가하고, (3) 같은 원인으로 잘못 처리될 수 있는 다른 숫자 파서가 "
            "collector/ 에 더 있는지 확인해 파일:줄로 보고하고, (4) `python -m pytest collector -q` 전체를 실행해라. "
            "이미 실패하던 테스트가 있으면 이번 변경과 무관한지 확인해 보고해라. " + COMMON
        ),
        "T3": (
            "`collector/minute_bars.py`(약 1050줄)를 응집도 있는 여러 모듈로 나누는 리팩토링 계획을 세워라. "
            "새 모듈 이름, 각 모듈로 옮길 함수/클래스, 각 새 모듈의 공개 인터페이스 시그니처 스케치, 순환 임포트 위험, 단계별 순서를 포함하고, "
            "분할하면 임포트 경로가 깨질 저장소 안의 파일(테스트 포함)을 grep 으로 확인해 목록으로 적어라. 900단어 이내. 파일은 수정하지 마. " + COMMON
        ),
    },
}
b.TASKS = TASKS

_orig_apply = b.apply_condition


def apply_condition(name, cond):
    if cond == "E":
        _orig_apply(name, "B")
        p = b.REPOS[name] / "CLAUDE.md"
        t = p.read_text(encoding="utf-8")
        p.write_text(t.rstrip("\n") + "\n\n## Code navigation\n\n" + SENTENCE_E + "\n", encoding="utf-8")
    else:
        _orig_apply(name, cond)


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


def wait_for_ram():
    """Start only below START_BELOW. While waiting, nothing is launched (in-process ctypes sampling only)."""
    waited = 0
    while True:
        r = ram_pct()
        if r < START_BELOW:
            return r, waited
        status(f"RAM {r}% >= {START_BELOW}% — waiting {POLL_WAIT_S}s (waited {waited}s)")
        time.sleep(POLL_WAIT_S)
        waited += POLL_WAIT_S


# extra graders -------------------------------------------------------------
def grade_read2(name, task, answer, changes):
    g = b.grade_read(name, task, answer, changes)
    a = answer or ""
    repo = b.REPOS[name]
    if (name, task) == ("flatten", "T1"):
        want = ["capture_side_effects", "compute_behavior_hash", "assert_equivalent", "compare", "comparator.py", "harness.py",
                "_cli_orchestration.py", "test_harness.py", "test_properties.py", "test_integration.py", "test_comparator.py", "__init__.py"]
        hit = [w for w in want if w in a]
        g.update(expected=len(want), found=len(hit), recall=len(hit) / len(want), missing=[w for w in want if w not in a])
    elif (name, task) == ("flatten", "T3"):
        want = ["cli.py", "test_cli.py", "Tracer"]
        g["break_expected"] = len(want); g["break_found"] = sum(w in a for w in want)
        g["break_recall"] = g["break_found"] / len(want)
    elif (name, task) == ("ish", "T3"):
        want = ["mark_contamination.py", "screen.py", "test_mark_contamination.py", "test_minute_bars.py", "test_minute_bars_v3.py"]
        g["break_expected"] = len(want); g["break_found"] = sum(w in a for w in want)
        g["break_recall"] = g["break_found"] / len(want)
    elif (name, task) == ("ish", "T1"):
        fields = ["molit_csv_base_url", "molit_csv_encoding", "sqlite_path", "state_path", "csv_path", "turso_url", "turso_auth_token"]
        tp = fr = fn = 0
        for m in ["cleanup_mock_quotes", "corporate_actions", "download_bulk", "fetch_stocks", "import_bulk", "main", "mark_contamination",
                  "migrate_dong_identity", "migrate_monthly_rent", "migrate_property_types", "migrate_ri_codes", "minute_bars",
                  "renormalize_rent", "screen"]:
            src = (repo / "collector" / f"{m}.py").read_text(encoding="utf-8", errors="replace")
            truth = {f for f in fields if re.search(r"\." + f + r"\b", src)}
            rows = "\n".join(l for l in a.splitlines() if re.search(r"\b" + m + r"(\.py)?\b", l))
            said = {f for f in fields if f in rows}
            tp += len(truth & said); fr += len(said - truth); fn += len(truth - said)
        g.update(field_tp=tp, field_fp=fr, field_fn=fn, field_f1=(2 * tp / (2 * tp + fr + fn)) if (2 * tp + fr + fn) else None)
    return g


def build_cmd(cond):
    cmd = b.build_cmd("B" if cond == "E" else cond)
    return cmd


def run_one2(name, task, cond, rep, attempt=1):
    rid = f"{name}-{task}-{cond}-r{rep}"
    if (RAW / f"{rid}.done").exists():
        return "done"
    r, waited = wait_for_ram()
    ram_before = r
    stale = b.bench_procs()
    for x in stale:
        b.kill_tree(x.split("|")[0])
    b.reset_repo(name)
    apply_condition(name, cond)
    repo = b.REPOS[name]
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "OPENROUTER_API_KEY")}
    env["PYTHONUTF8"] = "1"
    if name == "flatten":
        env["PYTHONPATH"] = str(repo / "src")
    else:
        env.pop("PYTHONPATH", None)
    prompt = TASKS[name][task]
    stream = RAW / f"{rid}.stream.jsonl"
    p = subprocess.Popen(build_cmd(cond), cwd=repo, env=env, stdin=subprocess.PIPE, stdout=open(stream, "w", encoding="utf-8"),
                         stderr=open(RAW / f"{rid}.stderr", "w", encoding="utf-8"), text=True, encoding="utf-8")
    start = time.time()
    p.stdin.write(prompt); p.stdin.close()
    timed_out = aborted = False
    peak = ram_before
    while p.poll() is None:
        time.sleep(8)
        cur = ram_pct(); peak = max(peak, cur)
        if cur > ABORT_ABOVE:
            aborted = True; break
        if time.time() - start > 1500:
            timed_out = True; break
    if aborted or timed_out:
        b.kill_tree(p.pid)
    wall = time.time() - start
    ram_after = ram_pct()
    orphans = b.bench_procs(since=start - 5)
    for x in orphans:
        b.kill_tree(x.split("|")[0])
    if aborted:
        with open(RAW / "aborted.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(id=rid, attempt=attempt, peak_ram=peak, wall_s=round(wall, 1), time=time.strftime("%F %T"))) + "\n")
        for suf in (".stream.jsonl", ".stderr"):
            (RAW / f"{rid}{suf}").rename(RAW / f"{rid}.abort{attempt}{suf}")
        b.reset_repo(name)
        status(f"ABORT {rid} attempt {attempt}: RAM peak {peak}% > {ABORT_ABOVE}% — will retry later")
        return "aborted"
    sid = None; result = {}; init = {}
    for line in stream.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            sid = d.get("session_id"); init = d
        if d.get("type") == "result":
            result = d
    row = dict(id=rid, repo=name, task=task, cond=cond, rep=rep, attempt=attempt, session_id=sid, wall_s=round(wall, 1),
               timed_out=timed_out, ram_before=ram_before, ram_peak=peak, ram_after=ram_after, waited_s=waited,
               orphan_procs=len(orphans), subtype=result.get("subtype"), is_error=result.get("is_error"),
               num_turns=result.get("num_turns"), duration_ms=result.get("duration_ms"), cost_usd=result.get("total_cost_usd"),
               mcp_servers=[(m.get("name"), m.get("status")) for m in init.get("mcp_servers", [])], n_tools=len(init.get("tools", [])))
    sp = b.find_session(sid) if sid else None
    if sp:
        shutil.copy(sp, RAW / f"{rid}.session.jsonl")
        row.update(b.session_metrics(sp))
    answer = result.get("result") or ""
    (RAW / f"{rid}.answer.txt").write_text(answer, encoding="utf-8")
    ch = b.changed_files(repo)
    try:
        row["grade"] = b.grade_bug(name, env) if task == "T2" else grade_read2(name, task, answer, [p_ for _, p_ in ch])
    except Exception as e:
        row["grade"] = dict(error=repr(e))
    (RAW / f"{rid}.diff.patch").write_text(b.git(repo, "diff").stdout + "\n--- untracked ---\n" + "\n".join(p_ for st, p_ in ch if st == "??"), encoding="utf-8")
    with open(RAW / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (RAW / f"{rid}.done").write_text("1")
    b.reset_repo(name)
    status(f"DONE {rid} wall={row['wall_s']}s calls={row.get('api_calls')} ctx={row.get('tok_ctx_total')} out={row.get('tok_out')} serena={row.get('serena_calls')} peak={peak}%")
    return "done"


def matrix2(conds="ABEDC", reps=(1, 2)):
    order = []
    for name in ("flatten", "ish"):
        for task in ("T1", "T2", "T3"):
            for rep in reps:
                cs = list(conds) if rep % 2 == 1 else list(reversed(conds))
                order += [(name, task, c, rep) for c in cs]
    return order


if __name__ == "__main__":
    b.apply_condition = apply_condition
    queue = [(x, 1) for x in matrix2()]
    gave_up = []
    while queue:
        if (B / "STOP").exists():
            status("STOP file present — exiting"); sys.exit(4)
        (n, t, c, r), att = queue.pop(0)
        res = run_one2(n, t, c, r, att)
        if res == "aborted":
            if att < MAX_ATTEMPTS:
                queue.append(((n, t, c, r), att + 1))   # retry after the rest of the queue
            else:
                gave_up.append(f"{n}-{t}-{c}-r{r}")
    (RAW / "ALLDONE").write_text(json.dumps(dict(gave_up=gave_up)))
    status(f"ALLDONE gave_up={gave_up}")
