# Equivalence Harness 스킬

## 언제 사용
- 변환 전후 코드의 동등성 검증 시
- 반환값 + 부수효과까지 포함한 정확한 비교 시

## 핵심 패턴

### 반환값 정규화 해시
```python
import hashlib, pickle

def hash_return(val) -> str:
    try:
        return hashlib.sha256(pickle.dumps(val)).hexdigest()
    except Exception:
        return hashlib.sha256(repr(val).encode()).hexdigest()
```

### 부수효과 캡처
```python
from unittest.mock import patch
from io import StringIO

def capture_side_effects(func, *args, **kwargs):
    stdout_buf = StringIO()
    with patch("sys.stdout", stdout_buf):
        result = func(*args, **kwargs)
    return result, stdout_buf.getvalue()
```

### 동등성 비교
```python
def assert_equivalent(original_func, flattened_func, test_inputs: list):
    for args, kwargs in test_inputs:
        orig_ret, orig_side = capture_side_effects(original_func, *args, **kwargs)
        flat_ret, flat_side = capture_side_effects(flattened_func, *args, **kwargs)
        assert hash_return(orig_ret) == hash_return(flat_ret)
        assert orig_side == flat_side
```

## 수용 기준 (A1~A6)
- A1: 5단계 다이아몬드 상속 — 닫힌 계층, 완전 펼침
- A2: 닫힌 계층 3종 이상 구현 — isinstance 디스패치 생성
- A3: 열린 계층 — stub 표시, 관측분만 펼침
- A4: OS1~OS5 각각 단위 테스트 통과
- A5: 변환 전후 동등성 해시 일치
- A6: 포매팅 보존 (공백/주석 변경 없음)
