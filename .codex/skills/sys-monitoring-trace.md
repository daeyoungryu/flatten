# sys.monitoring Trace 스킬

## 언제 사용
- 런타임 실행 경로 추적 시
- 어떤 다형 구현이 실제로 호출됐는지 확정 시

## 핵심 패턴

### 버전 분기 패턴
```python
if sys.version_info >= (3, 12):
    # sys.monitoring 사용 (3.12+)
    TOOL_ID = sys.monitoring.DEBUGGER_ID

    def start_trace():
        sys.monitoring.use_tool_id(TOOL_ID, "flatten-tracer")
        sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.PY_START)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, on_py_start)

    def on_py_start(code, instruction_offset):
        qualname = code.co_qualname  # "ClassName.method_name"
        # OracleRecord 생성
else:
    # sys.settrace fallback (3.8~3.11)
    def start_trace():
        sys.settrace(_settrace_handler)

    def _settrace_handler(frame, event, arg):
        if event == "call":
            qualname = frame.f_code.co_qualname if hasattr(frame.f_code, "co_qualname") else frame.f_code.co_name
            # OracleRecord 생성
        return _settrace_handler
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
- 버전 분기는 반드시 `sys.version_info >= (3, 12)` 체크로 — 다른 방법 사용 금지
- TOOL_ID는 전역 1개 유지 (3.12+ 경로에서만 사용)
- 추적 중 예외 발생 시 반드시 stop_trace() 호출 (finally 블록)
- monkey-patch 방식 사용 금지
