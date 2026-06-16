# flatten-polymorph 사용 가이드
# flatten-polymorph Usage Guide

> **대상 독자 / Audience:** Python 경력 1년 미만의 초급 개발자
> **버전 / Version:** 0.2.1 | **Python:** 3.8+

---

## 1. flatten이 뭔가요? / What is flatten?

**한 줄 요약:** `flatten-polymorph`는 Python 코드에서 "어떤 구현이 실행될지 모호한 메서드 호출"을 추적·분석해, 안전하게 명시적 직접 호출로 바꿔주는 도구입니다.

**One-liner:** `flatten-polymorph` is a tool that traces runtime method dispatch in Python code and safely rewrites ambiguous polymorphic calls into explicit direct calls.

### 쉽게 이해하기 / Conceptual Overview

```python
# 리팩터링 전 (Before) — obj.run()이 어떤 클래스의 run()인지 바로 알기 어렵습니다
obj.run(data)

# 리팩터링 후 (After) — flatten이 안전하다고 판단했을 때만 변환
Worker.run(obj, data)   # 직접 호출 / explicit direct call
```

flatten은 **"안전할 때만"** 변환합니다. 확신이 없으면 변환을 거부합니다.  
flatten only rewrites when it's **safe to do so**. When in doubt, it refuses.

---

## 2. 설치 방법 / Installation

### 방법 A: whl 파일로 설치 (오프라인) / From .whl file (offline)

```bash
pip install flatten_polymorph-0.2.1-py3-none-any.whl
```

> `pip`은 Python 패키지 설치 도구입니다.  
> `pip` is Python's package installer.

### 방법 B: PyPI에서 설치 / From PyPI

```bash
pip install flatten-polymorph
```

### 설치 확인 / Verify Installation

```bash
python -m flatten --help
```

정상 설치 시 사용법이 출력됩니다 / You should see usage instructions if installed correctly.

---

## 3. 빠른 시작 (5분) / Quick Start (5 minutes)

### 예제용 파일 준비 / Prepare an example file

아래 코드를 `my_code.py`로 저장하세요:

```python
# my_code.py
from flatten.finals import final   # final: "더 이상 상속하지 않는다"는 표시

@final
class Worker:
    def run(self, value: int) -> int:
        return value + 1

def main() -> int:
    worker = Worker()
    return worker.run(2)   # flatten이 분석할 호출 지점

if __name__ == "__main__":
    print(main())
```

> `@final`: 이 클래스를 상속하는 서브클래스가 없음을 선언합니다.  
> `@final`: Declares that no subclass will extend this class — a prerequisite for safe rewriting.

---

### 예제 1: 정적 분석 (Static Analysis)

코드를 실행하지 않고 호출 지점을 파악합니다.  
Identifies call sites without running the code.

```bash
flatten analyze my_code.py --json
```

**출력 예시 / Sample output:**
```json
{
  "call_sites": [
    {
      "call_site_id": "my_code.py:9:11-9:25",
      "method_name": "run",
      "receiver_expr": "worker"
    }
  ]
}
```

---

### 예제 2: 전체 파이프라인 실행 (End-to-end Pipeline)

아래 4단계를 순서대로 실행하면 됩니다.  
Run these 4 steps in order:

```bash
# 1단계: 실행하며 추적 / Step 1: Trace at runtime
flatten trace my_code.py --entry my_code:main --out obs.json

# 2단계: 리팩터링 계획 생성 / Step 2: Generate rewrite plan
flatten plan my_code.py --observations obs.json --out plan.json

# 3단계: 코드 변환 / Step 3: Rewrite the code
flatten rewrite my_code.py --plan plan.json --out rewritten.py --apply --skip-verify

# 4단계: 동작이 동일한지 검증 / Step 4: Verify equivalence
flatten verify my_code.py rewritten.py --entry my_code:main
```

> `--entry`는 "이 함수에서 시작해"라는 의미입니다.  
> `--entry` specifies the function where execution begins for tracing.
> 참고: `--apply`를 `--skip-verify` 없이 사용하려면 inline verification을 위해 `--entry`와 `--cases`가 필요합니다. 이 Quick Start는 4단계의 `flatten verify`에서 검증을 따로 수행하므로 3단계에서 `--skip-verify`를 사용합니다.  
> Note: `--apply` without `--skip-verify` requires `--entry` and `--cases` for inline verification. This Quick Start defers verification to the explicit `flatten verify` step, so step 3 uses `--skip-verify`.

---

### 예제 3: 흔한 실수 + 해결법 / Common Mistakes & Fixes

#### 실수 1: `--apply` 없이 `rewrite` 실행
```bash
# ❌ 잘못된 예 — 파일이 실제로 바뀌지 않습니다 (dry-run 기본값)
flatten rewrite my_code.py --plan plan.json --out rewritten.py

# ✅ 올바른 예 — --apply 를 붙여야 실제로 씁니다
flatten rewrite my_code.py --plan plan.json --out rewritten.py --apply
```

#### 실수 2: `@final` 없이 클래스 정의
```python
# ❌ flatten이 "열린 세계(OPEN)"로 판단 → 변환 거부
class Worker:
    def run(self, value): ...

# ✅ @final 선언 → 닫힌 세계(CLOSED)로 판단 가능
from flatten.finals import final

@final
class Worker:
    def run(self, value): ...
```

#### 실수 3: 모듈 경로 오류
```bash
# ❌ 잘못된 예 — 파일 경로(슬래시)와 모듈 경로(콜론+점)를 혼동
flatten trace my_code.py --entry my_code/main

# ✅ 올바른 예 — --entry는 "모듈명:함수명" 형식
flatten trace my_code.py --entry my_code:main
```

---

## 4. 주요 기능 설명 / Key Features

### 4-1. 분석 (`analyze`) — 호출 지점 탐색

소스 파일에서 다형성 메서드 호출 지점을 정적으로 찾습니다.

```bash
flatten analyze my_code.py --json          # JSON 출력
flatten analyze my_code.py --format html   # HTML 리포트 생성
```

### 4-2. 추적 (`trace`) — 런타임 관찰

코드를 실제로 실행하면서 "어떤 타입이 어떤 메서드를 호출했는지" 기록합니다.

```bash
flatten trace my_code.py --entry my_code:main --out obs.json
```

> 추적 데이터(`obs.json`)는 다음 단계(plan)의 입력이 됩니다.  
> The trace data (`obs.json`) feeds into the next step.

- `--capture-values`: 인자 값도 기록 (성능 비용 있음 / records argument values, at a performance cost)
- `--strict`: 위험한 패턴 발견 시 에러로 처리

### 4-3. 계획 (`plan`) — 리팩터링 판단

추적 결과를 바탕으로 각 호출 지점을 변환할지 말지 판단합니다.

```bash
flatten plan my_code.py --observations obs.json --out plan.json
```

**판단 결과 종류 / Decision types:**

| 결과 / Result | 의미 / Meaning |
|---|---|
| `CLOSED` | 안전하게 변환 가능 / Safe to rewrite |
| `OPEN` | 미관찰 서브클래스 가능성 있음 / Potential unobserved subclasses |
| `UNSAFE` | 원숭이 패치, 동적 디스패치 등 위험 요소 / Monkey-patching or dynamic dispatch detected |

### 4-4. 변환 (`rewrite`) — 코드 수정

계획에 따라 실제 코드를 변환합니다. 기본값은 dry-run(미리보기)입니다.

```bash
# 미리보기 / Preview (no file written)
flatten rewrite my_code.py --plan plan.json --out rewritten.py

# 실제 적용 / Actually write the output
flatten rewrite my_code.py --plan plan.json --out rewritten.py --apply
```

### 4-5. 검증 (`verify`) — 동작 동일성 확인

원본과 변환된 파일이 동일하게 동작하는지 확인합니다.

```bash
flatten verify my_code.py rewritten.py --entry my_code:main
```

### 4-6. 리포트 (`report`) — 사람이 읽기 쉬운 요약

```bash
flatten report plan.json
```

---

## 5. 자주 묻는 질문 (FAQ)

**Q: `OPEN`이라고 나오는데 변환이 안 됩니다.**  
A: flatten이 "다른 서브클래스가 있을 수 있다"고 판단한 것입니다. 클래스에 `@final`을 붙이거나, `--closed-world` 플래그를 사용해 패키지 전체를 단일 세계로 선언하세요.

```bash
flatten plan my_code.py --observations obs.json --out plan.json --closed-world
```

---

**Q: `UNSAFE`가 나왔어요. 뭔가 잘못된 건가요?**  
A: 잘못된 게 아닙니다. flatten이 안전하지 않은 패턴(원숭이 패치, `__getattr__` 오버라이드 등)을 감지한 것입니다. 해당 호출 지점은 변환하지 않는 것이 맞습니다.

---

**Q: `obs.json`이 비어 있거나 호출 기록이 없습니다.**  
A: `--entry`로 지정한 함수가 실제로 메서드를 호출하는지 확인하세요. 또는 테스트 케이스를 추가해 런타임에 더 많은 경로를 실행시키세요.

---

**Q: Python 3.12와 3.11에서 동작이 다른가요?**  
A: 내부적으로 다릅니다. Python 3.12 이상은 `sys.monitoring`을 사용하고, 3.11 이하는 `sys.settrace`를 사용합니다. 사용자 입장에서는 동일한 CLI를 쓰면 됩니다.

---

**Q: `flatten`을 가져오기(import)해서 Python 코드 안에서 쓸 수 있나요?**  
A: 네, 가능합니다.

```python
from flatten import trace_calls, Tracer

# 컨텍스트 매니저로 추적 / Use as a context manager
with trace_calls() as tracer:
    my_function()

records = tracer.records   # OracleRecord 리스트
```

---

**Q: `check-wheel-contents: W009` 경고가 나옵니다.**  
A: `pyproject.toml`에 `ignore = ["W009"]`가 이미 설정되어 있어 무시해도 됩니다.

---

## 6. 지원 Python 버전 / Supported Python Versions

| Python 버전 | 지원 여부 | 내부 구현 |
|---|---|---|
| 3.8 | ✅ | `sys.settrace` |
| 3.9 | ✅ | `sys.settrace` |
| 3.10 | ✅ | `sys.settrace` |
| 3.11 | ✅ | `sys.settrace` |
| 3.12+ | ✅ (권장) | `sys.monitoring` (더 빠름) |

---

## 7. 전체 CLI 명령어 요약 / CLI Command Summary

```bash
flatten analyze <path> [--json | --format html] [--strict]
flatten trace   <path> --entry <module:func> [--out <file>] [--capture-values]
flatten plan    <path> --observations <obs.json> [--out <file>] [--closed-world]
flatten rewrite <path> --plan <plan.json> --out <file> [--apply] [--dry-run]
flatten verify  <original> <rewritten> --entry <module:func> [--cases <file>]
flatten report  <plan.json>
flatten evaluate <path> [--plan <file>]
flatten benchmark --catalog <file>
```

---

## 8. 의존성 / Dependencies

| 패키지 | 용도 |
|---|---|
| `libcst >= 1.1.0` | 소스 코드 변환 (AST 수준 / source-level code transformation) |
| `typing_extensions >= 4.0.0` | 구버전 Python 타입 힌트 지원 |

---

*flatten-polymorph v0.2.1 · MIT License · Python 3.8+*

