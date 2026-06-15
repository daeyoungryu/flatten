# LibCST Transform 스킬

## 언제 사용
- CST 노드 방문/변환 코드 작성 시
- 소스 포매팅 보존이 필요한 변환 시

## 핵심 패턴

### Visitor (읽기 전용)
```python
import libcst as cst

class CallCollector(cst.CSTVisitor):
    def visit_Call(self, node: cst.Call) -> None:
        # node.func, node.args 접근
        pass
```

### Transformer (수정)
```python
class DispatchTransformer(cst.CSTTransformer):
    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        # updated를 반환하거나 새 노드로 교체
        return updated
```

### 메타데이터 사용
```python
from libcst.metadata import MetadataWrapper, QualifiedNameProvider

wrapper = MetadataWrapper(cst.parse_module(source))
# wrapper.resolve(QualifiedNameProvider) 로 정규화된 이름 접근
```

### 포매팅 보존
- `cst.parse_module(source).code` → 원본 포매팅 유지
- `cst.MaybeSentinel.DEFAULT` 활용
- whitespace, comment는 건드리지 말 것

## 주의
- `ast` 모듈 사용 금지 — 포매팅 손실 발생
- `leave_*` 메서드는 반드시 노드를 반환해야 함
