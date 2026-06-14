# Closure Check 스킬

## 언제 사용
- 다형 호출이 닫힌 계층인지 열린 계층인지 판정 시

## 닫힌 계층 (closed hierarchy)
올 수 있는 구현을 빠짐없이 셀 수 있음 → isinstance 디스패치로 완전 펼침

## 열린 계층 (open hierarchy)
미관측 구현 가능 → 관측분만 펼치고 stub 표시

## 열린 계층 신호 5종 (OS1~OS5)
- OS1: 모듈 경계 밖 상속 가능 (`__subclasses__()` 외부 모듈 포함)
- OS2: 동적 클래스 생성 (`type()` 호출, `types.new_class`)
- OS3: 덕타이핑 (ABC 없이 같은 이름 메서드만 존재)
- OS4: `__getattr__` / `__getattribute__` 오버라이드
- OS5: 조건부 클래스 정의 (`if` 블록 안에 `class` 정의)

## 판정 알고리즘
```python
def is_closed(method_qualname: str, observed_impls: list[type]) -> ClosureVerdict:
    base_class = find_base_defining_method(method_qualname)
    all_subclasses = collect_all_subclasses(base_class)  # recursive __subclasses__()

    open_signals = check_os_signals(base_class, all_subclasses)  # OS1~OS5

    is_closed = len(open_signals) == 0 and set(observed_impls) == set(all_subclasses)
    return ClosureVerdict(method_qualname, is_closed, observed_impls, open_signals)
```

## 주의
- OS 신호 하나라도 있으면 열린 계층으로 처리
- 열린 계층 stub 형식: `# OPEN_DISPATCH: {qualname} — unobserved impls possible`
