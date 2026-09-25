# 토큰 절감 도구 측정 — Serena / Ponytail (2026-09-25)

> **상태: 측정 중단 (7/48 완료).** 규칙(RAM 90% 초과 시 중단)에 따라 멈췄다.
> 이 문서의 판정은 **잠정**이며, 부분 데이터(flatten T1 한 과제)만으로는 효과 유무를 판정할 수 없다.
> 이 브랜치(`docs/token-tools-bench-2026-09-25`)는 main 에 머지하지 않았다.

## 1. 0단계 — 코드 읽기 결과 (실행 전)

읽은 버전: **Serena v1.7.0** (`949a27e`, PyPI `serena-agent` 최신 릴리스, 2026-08-09; main HEAD 는 2.0.0.dev0 이라 릴리스를 택함),
**Ponytail v4.10.0** (`e3ba2aa`). 둘 다 `--depth 1` 얕은 클론으로 읽기만 했고 클론 안의 코드는 실행하지 않았다.

| 항목 | Serena v1.7.0 | Ponytail v4.10.0 |
|---|---|---|
| LLM 키 자동 사용 | **없음.** `GEMINI`/`OPENROUTER` 문자열 자체가 코드에 없다. `ANTHROPIC` 키를 읽는 경로는 `token_count_estimator: ANTHROPIC_CLAUDE_SONNET_4` 로 **직접 바꿀 때만**(기본 `CHAR_COUNT`). 그때 `load_dotenv()` 가 cwd 의 `.env` 를 읽는다 | 없음 |
| 외부 전송 | `agent.py:735` 시작 시 `GET oraios-software.de/serena_usage.php?os&dashboard&version&backend&context` (**기본 켜짐**, `SERENA_USAGE_REPORTING=false` 로 끔). 대시보드가 켜져 있으면 `serena_news.json` 조회 + PyPI 최신 버전 조회 | 없음 (네트워크·`eval`·`exec` 없음) |
| 사용자 스코프 쓰기 | `~/.serena`(config, 언어서버, 메모리). `SERENA_HOME` 으로 옮길 수 있음 | 훅이 `$CLAUDE_CONFIG_DIR/.ponytail-active`(기본 `~/.claude`)와 `.ponytail-statusline-nudged` 를 씀. `/ponytail default` 를 쓰면 `%APPDATA%\ponytail\config.json` 도 씀 |
| 첫 실행 다운로드 | uv 가 PyPI 75개 패키지(캐시 약 160MB), `pyright==1.1.403`(PyPI) + pyright 의 npm 패키지, TypeScript 를 켜면 npm `typescript`·`typescript-language-server` + 백그라운드 `@types/*` | 없음 (node 스크립트 복사만) |
| 지시문 개입 | `claude-code` 컨텍스트가 "Read 는 발견용으로 **FORBIDDEN**, Edit **FORBIDDEN**, 자기 선호를 극복하라" 를 주입하고 기본 도구를 `excluded_tools` 로 뺀다. 별도 `serena-hooks` 는 grep/read 연속 사용 시 PreToolUse **deny** 를 낸다(설정해야 동작) | "ACTIVE EVERY RESPONSE", "Never stall", "코드 먼저 + 최대 3줄 설명". 다른 도구를 막는 문구는 없음 |
| 본문과 코드 일치 | 일치 (위 사용량 보고는 문서에도 있음) | 일치 |

이슈 검증 (GitHub API 로 원문 확인):
- **#200** (2026-06-19, 닫힘): 상태줄 안내 명령에 경로를 이스케이프 없이 넣는 명령 주입. 읽은 v4.10.0 에서는 `isShellSafe(scriptPath)` 검사가 들어가 있어 **수정된 상태**.
- **#685** (2026-08-04, 열림, 작성자 RoxsLee 1명, 댓글 0): 주입이 세션당 1회지만 매 API 호출이 다시 읽어 턴당 기울기가 남는다. 한 문장 지시 대비 +6.9%. **단일 출처 · 재현자 없음**이라 확정 근거로 쓰지 않는다. 다만 "주입은 1회, 재읽기가 비용" 이라는 메커니즘은 코드와 맞는다.
- 사전 조사의 "약 2.8k 토큰" 은 #685 의 수치다. **v4.10.0 실측은 훅 출력 5,252자**(≈1.3~1.5k 토큰). 첫 호출 컨텍스트 증가(§3)는 스킬 6개 설명 등이 더해져 더 크게 나오지만 노이즈가 커서 단정하지 않는다.
- JetBrains 80쌍 −10.3% 는 이번에 확인하지 못했다(미검증).

## 2. 측정 설계 (실행된 부분)

- 격리: `%TEMP%\tokbench` 아래 `git clone --local` 두 벌(`flatten`, `ish`=invest-strategy-hub), 원격 `origin` 제거, 작은 버그 1개를 주입한 `bench-base` 커밋에서 매 런 리셋. 원본 저장소는 수정하지 않았다.
- 사용자 범위 격리: `SERENA_HOME`/`UV_CACHE_DIR`/`UV_PYTHON_INSTALL_DIR`/`PYRIGHT_PYTHON_CACHE_DIR` 전부 temp. Serena 는 클론의 `.mcp.json`(프로젝트 범위)에, Ponytail 훅은 클론의 `.claude/settings.local.json` + `.claude/skills/ponytail*`(프로젝트 범위)에 뒀다. 훅의 `CLAUDE_CONFIG_DIR` 을 temp 로 돌려 `~/.claude` 에 플래그를 쓰지 않게 했다.
- 조건: A 현행 / B +Serena(`--context claude-code`, 모드 `interactive editing no-memories no-onboarding`, 대시보드·사용량 보고 끔, 언어 python 만) / C +Ponytail 훅 3종+스킬 6개 / D 클론 `CLAUDE.md` 에 한 문장(`bench.py` 의 `SENTENCE`).
- 실행: `claude -p --model claude-sonnet-5`, 직렬, 런 전 RAM 게이트(85% 초과 대기 / 90% 초과 중단). 헤드리스에서는 `claude-mem` 플러그인만 `--settings` 로 껐다(측정 세션이 사용자의 메모리 DB 에 쌓이는 것을 막으려고. superpowers·codex 는 그대로).
- 과제(고정 문구는 `2026-09-25-bench.py` 의 `TASKS`): flatten — T1 `capture_behavior` 호출부 설명 / T2 `capture_side_effects` 가 stderr 를 돌려주는 주입 버그(기존 테스트 274개는 통과) / T3 `_cli_orchestration.py` 분할 계획. ish — T1 `load_config()` 호출 모듈 표 / T2 `_num("NaN")` 이 0.0 이 되는 버그 / T3 `minute_bars.py` 분할 계획.
- 참고: 두 저장소 모두 "큰 저장소"가 아니다 (flatten 355파일·src 4.7k줄, ish 293파일). Serena 의 이점이 나오는 조건이 아닐 수 있다.
- 발견 사실: 헤드리스 A 조건의 첫 호출 컨텍스트가 이미 **약 66k 토큰**(도구 71개, 스킬·플러그인·MCP 포함)이다. 그래서 1~3k 를 더하는 도구의 상대 효과는 작게 나온다.

## 3. 부분 결과 (flatten T1, 7런)

| 런 | 첫 컨텍스트 | API호출 | ctx 합계 | out | 초 | USD | Serena 호출 | 정답 |
|---|---|---|---|---|---|---|---|---|
| A r1 | 66,637 | 3 | 211,916 | 2,551 | 34 | 0.199 | – | 6/6 |
| B r1 | 66,350 | 5 | 360,735 | 4,083 | 46 | 0.245 | **0** | 6/6 |
| B r2 | 65,720 | 3 | 212,127 | 2,261 | 34 | 0.199 | **0** | 6/6 |
| C r1 | 69,837 | 4 | 294,939 | 2,566 | 44 | 0.222 | – | 6/6 |
| C r2 | 69,284 | 3 | 220,246 | 1,903 | 27 | 0.205 | – | 6/6 |
| D r1 | 68,475 | 4 | 291,105 | 2,879 | 48 | 0.221 | – | 6/6 |
| D r2 | 68,723 | 5 | 367,486 | 3,740 | 52 | 0.251 | – | 6/6 |

(ctx 합계 = 호출별 input+cache_read+cache_creation 의 합. A r2 는 RAM 91.2% 로 실행되지 못했다.)

읽을 수 있는 것과 없는 것:
- A 가 1회뿐이라 **"2회 모두 같은 방향 ≥5%" 판정 자체를 적용할 수 없다.** 어떤 조건의 효과도 인정하지 않는다.
- 같은 조건 안에서도 API 호출이 3~5회로 흔들려 ctx 합계가 212k↔361k(B)로 뛴다. 이 과제는 너무 짧아(3~5호출) 조건 차이보다 **런 간 변동이 크다.** 5% 판정 규칙을 통과하려면 과제가 더 길거나 반복이 더 많아야 한다.
- **Serena 는 B 의 세 런(파일럿 포함) 모두 0회 호출됐다.** 도구 14개(`find_symbol`, `find_referencing_symbols`, `get_symbols_overview` 등)는 지연 로드 목록에 보였지만 모델이 기본 Grep/Read 를 골랐다 — 사전 조사의 "Claude 가 기본 도구를 선호해 잘 안 쓴다"와 일치한다. 쓰이지 않으면 토큰 효과도 없다.
- C·D 의 첫 컨텍스트가 A 보다 +2.6~3.2k / +1.8~2.1k. D 는 문장이 약 70토큰인데도 +2k 라 이 지표의 **노이즈 폭이 ±2k** 임을 뜻한다. C 의 증가분을 훅 크기로 단정하지 않는다.
- 부작용 점검: 7런 모두 파일 수정 0건, 고아 프로세스 0개.

## 4. Ponytail vs 현재 세팅 (규칙 대조)

사용자 전역·프로젝트 `CLAUDE.md`, 설치된 `superpowers`/`codex` 와 Ponytail v4.10.0 `SKILL.md` 를 대조했다.

| Ponytail 규칙 | 현재 세팅 | 관계 |
|---|---|---|
| 사다리: 재사용·stdlib·기존 의존성 우선, 미요청 추상화 금지 | 전역 "작게, 자주", flatten "크리티컬 경계"(`contracts.py` 만 공유) | **겹침** (충돌 없음) |
| 버그는 호출부 전체 grep 후 공유 함수에서 한 번에 | 게이트 B 가 diff·검증 출력을 요구 | **겹침** (오히려 도움) |
| 중요 로직은 실행 가능한 검사 1개를 남겨라 | 게이트 C(테스트 실행 필수), flatten 체크리스트(전체 pytest) | **겹침**, 사용자 기준이 더 엄격 |
| "복잡한 요청은 게으른 버전을 **바로 내고** 멈추지 마라" | 전역 "비자명한 변경은 계획 먼저 제시·승인 후 실행" | **충돌** |
| 출력은 "코드 먼저 + 설명 최대 3줄" | 전역 "한국어 답변", 게이트 합의 시 "확정 설계 + 해소된 쟁점 목록을 사용자에게 보여줄 것", 결과 보고 형식 | **긴장** (요청된 설명은 예외라고 스킬이 명시 → 부분 충돌) |
| "파일 수 최소, 삭제 우선" | 변경마다 `project_summary`→`architecture`→`decision_log`→`current_tasks` 갱신 | **긴장** (문서 갱신은 파일을 늘린다) |
| 테스트 프레임워크·픽스처·함수별 스위트 금지 | `superpowers:test-driven-development`(설치됨) 는 테스트 우선 | **충돌** |
| SubagentStart 로 서브에이전트마다 규칙 전문 재주입 | audit-worker·Explore 등을 자주 띄우는 흐름 | **비용 증폭** (스폰마다 약 1.3k+) |
| 세션 시작 1회 주입, 모드 지속 | (없음) | **신규 상주 비용** — 매 API 호출이 다시 읽음 |

## 5. 잠정 판정

| 도구 | 판정 | 근거 |
|---|---|---|
| **Serena** | **보류** | 코드는 통과(키 사용 경로 없음, 전송은 끌 수 있음). 그러나 (a) 실측 3런 모두 0회 사용, (b) 이 저장소 규모에서는 이점 조건이 아님, (c) `claude-code` 컨텍스트가 기본 도구를 금지하는 지시문이라 skill-scout 4단계 기준의 주의 대상, (d) 다운로드가 크다. 효과 근거 없음 → 들이지 않는다. 판정 재개 조건: 더 큰 저장소에서 Serena 호출이 실제로 일어나는 런을 확보 |
| **Ponytail** | **안 들임 (잠정)** | 상주 비용 실재(주입 1.3k+토큰, 매 호출 재읽기, 서브에이전트마다 재주입), 계획 우선·TDD 와 충돌. 얻는 이점(코드 축소)은 사용자가 겪은 문제 목록에 없음. 원하는 게 "핵심 원칙"이면 D 방식(한 문장)이 상주 비용이 훨씬 작다 — 다만 D 의 실효도 이번엔 미측정 |

## 6. 남은 것 / 재개 방법

- 완료 7 / 48. 남은 41런. 사용자 Claude 사용량 소모: 지금까지 파일럿 2 + 본 7 = 9런, ctx 합계 약 2.5M 토큰(대부분 캐시 읽기), out 약 27k.
- 중단 원인: 측정과 무관하게 이 PC 의 RAM 이 87~89% (Defender 1.6GB, Claude 프로세스 23개 등). 내 런은 약 0.5~1GB 를 더한다.
- 재개: 다른 Claude 세션을 정리해 RAM 을 85% 아래로 만든 뒤
  `cd %TEMP%\tokbench && python harness\bench.py matrix` (완료된 런은 `.done` 파일로 건너뜀; `STOP` 파일은 지운다).
- 원자료: `%TEMP%\tokbench\raw\` (`runs.jsonl`, 런별 `.stream.jsonl`/`.session.jsonl`/`.answer.txt`/`.diff.patch`). 이 저장소에는 요약 `docs/bench-data/2026-09-25-runs-partial.jsonl`, 드라이버 `2026-09-25-bench.py`, 분석기 `2026-09-25-analyze.py` 를 넣었다.
- 조건당 n=2 이므로, 재개해서 끝나도 말할 수 있는 것은 "5% 규칙 통과 여부"까지다(통계적 유의성은 아님).
