# sys.monitoring Trace 스킬

## 언제 사용
- 런타임 실행 경로 추적 시
- 어떤 다형 구현이 실제로 호출됐는지 확정 시

## 핵심 패턴

### 기본 세팅 (Python 3.12+)
```python
import sys

TOOL_ID = sys.monitoring.DEBUGGER_ID

def start_trace():
    sys.monitoring.use_tool_id(TOOL_ID, "flatten-tracer")
    sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.PY_START)
    sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, on_py_start)

def on_py_start(code, instruction_offset):
    qualname = code.co_qualname  # "ClassName.method_name"
    # OracleRecord 생성
```

### __wrapped__ 체인 처리
```python
def unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func
```

### 정리
```python
def stop_trace():
    sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
    sys.monitoring.free_tool_id(TOOL_ID)
```

## 주의
- `sys.settrace` / `sys.setprofile` 사용 금지
- TOOL_ID는 전역 1개 유지
- 추적 중 예외 발생 시 반드시 stop_trace() 호출 (finally 블록)
