# {{PROJECT_NAME}} — 코딩 패턴 & 컨벤션
> 최종 갱신: YYYY-MM-DD | 이 파일이 진실원. ADR 변경 시 여기도 갱신.

## 공통 원칙

- **작게, 명확하게:** 함수 하나 = 책임 하나, 50줄 초과 시 분리 검토
- **Magic number 금지:** 상수로 명명 (예: `MAX_RETRY = 5`)
- **예외는 경계에서만:** 내부 로직은 오류 코드/Result 타입, 경계(I/O, API)에서 예외 처리
- **테스트 먼저:** 새 함수는 단위 테스트와 함께 작성

## Python 컨벤션

```python
# 타입 힌트 필수
def process(data: list[dict]) -> int: ...

# 컨텍스트 매니저로 리소스 관리
with open(path, encoding="utf-8") as f:
    ...

# f-string 우선 (% 또는 .format 금지)
msg = f"처리 완료: {count}건"

# dataclass 또는 TypedDict로 구조화
from dataclasses import dataclass
@dataclass
class Item:
    id: str
    value: float
```

## C++ 컨벤션 (해당 시)

```cpp
// RAII: raw new/delete 금지 → std::unique_ptr / std::shared_ptr
auto obj = std::make_unique<MyClass>();

// 복사 금지 클래스에 명시
class MyClass {
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MyClass)
};
```

## JavaScript/TypeScript 컨벤션 (해당 시)

```typescript
// any 금지 → 명시적 타입
const items: Item[] = [];

// async/await 우선 (callback 지양)
const data = await fetchData(url);

// const 우선, let 최소화, var 금지
```

## 브랜치 전략

- `main` — 안정 버전
- `develop` — 통합 브랜치
- `feature/TASK-NNN-<설명>` — 기능 개발
- `refactor/<설명>` — 리팩토링

## 커밋 메시지

```
<type>: <요약> (50자 이내)

[선택] 상세 설명

TASK-NNN 관련
```
type: feat / fix / refactor / test / docs / chore
