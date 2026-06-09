# 전역 공통 규칙 — AI/global_rules.md
> 새 프로젝트 시작 시 이 파일을 프로젝트 CLAUDE.md에 포함하거나 복사한다.
> 최종 갱신: 2026-06-10

---

## 1. Cowork 마운트 파일시스템 제약

Cowork sandbox는 사용자 폴더를 Linux에 마운트해서 제공한다.
아래 제약들은 **모든 Cowork 세션에 공통 적용**된다.

### 1-1. Write / Edit 도구 — 파일 절단·미반영

**증상:**
- `Write` 도구: 약 200줄 이상 파일의 내용을 조용히 잘라냄
- `Edit` 도구: 수정 성공으로 보고하지만 실제 파일에 반영 안 됨

**해결: 파일 생성·수정은 Python 문자열 쓰기 또는 heredoc 사용**
```bash
python3 -c "
content = '''...내용...'''
open('경로', 'w').write(content)
print(len(content.splitlines()), 'lines written')
"
wc -l 경로 && tail -5 경로
```

**검증 의무:** 작성 후 반드시 `cat 경로 | wc -l`로 예상 줄 수 확인.

### 1-2. SQLite — 마운트 FS에서 disk I/O error

**증상:** `sqlite3.OperationalError: disk I/O error` (WAL 저널 미지원)

**해결: /tmp에 생성 후 cp로 복사**
```bash
python3 -c "
import sqlite3, shutil
con = sqlite3.connect('/tmp/target.db')
# ... 작업 ...
con.commit(); con.close()
"
cp /tmp/target.db /마운트/경로/target.db
```

### 1-3. git index.lock — unlink 권한 없음

**증상:** `fatal: Unable to create '.git/index.lock': File exists`

**원인:** 마운트 FS에서 git이 lock 파일을 삭제(`unlink`)하지 못해 남겨둠.
- `os.unlink` → Permission denied
- `os.rename` → 성공 (다른 syscall)

**해결: 매 git 명령 직전 rename으로 우회**
```bash
python3 -c "
import os
for suffix in ['', '.bak', '.bak2', '.bak3']:
    p = f'.git/index.lock{suffix}'
    if os.path.exists(p):
        os.rename(p, p + '.bak')
        break
"
git add ... && git commit ...
```

### 1-4. git push — sandbox에서 GitHub 인증 불가

**증상:** `fatal: could not read Username for 'https://github.com': No such device or address`

**해결:** commit은 sandbox에서 완료하고, push는 사용자에게 안내한다.
```
# 사용자 실행 명령
git push origin main
```

---

## 2. Python 파일 무결성

### 2-1. stale pyc 캐시가 절단 소스를 은폐

**증상:** 소스가 절단됐어도 pyc 타임스탬프가 최신이면 절단이 숨겨짐.
`python3`으로 임포트하면 완성된 것처럼 보임.

**해결:**
```bash
touch src/패키지/모듈.py          # pyc보다 최신으로 만들어 재컴파일 강제
python3 -c "from 패키지.모듈 import 클래스; print(list(클래스.__dataclass_fields__))"
```

**탐지:** `ls -la src/패키지/__pycache__/*.pyc src/패키지/모듈.py` 로 타임스탬프 비교.

### 2-2. pyc 바이트코드 역분석으로 절단 파일 복원

원본 파일이 없고 pyc만 있을 때:
```python
import dis, marshal, types

with open('__pycache__/파일.cpython-310.pyc', 'rb') as f:
    f.read(16)  # magic + flags + timestamp
    code = marshal.loads(f.read())

def find_func(c, name):
    for x in c.co_consts:
        if isinstance(x, types.CodeType):
            if x.co_name == name: return x
            r = find_func(x, name)
            if r: return r

fn = find_func(code, '복원할_함수명')
print('varnames:', fn.co_varnames)
print('consts:', [c for c in fn.co_consts if isinstance(c, str)])
dis.dis(fn)  # 바이트코드 → 원본 로직 추론
```

### 2-3. 파일 완전성 검증 (모든 .py 작성 후 의무)

```bash
python -c "import ast; ast.parse(open('경로').read()); print('AST OK')"
wc -l 경로
tail -5 경로
```

---

## 3. 검증 없이 완료 보고 금지

| 보고 내용 | 요구 증거 |
|-----------|-----------|
| 파일 작성 완료 | `wc -l` + `tail -5` 결과 직접 인용 |
| Python 파일 | `AST OK` 출력 인용 |
| 테스트 통과 | `pytest` 마지막 줄 그대로 인용 |
| git staged | `git diff --cached --stat` 에 파일 존재 확인 |
| 임포트 결과 | `python -c` 실행 결과 인용 (추측·기억 금지) |

**Read 도구 출력 ≠ 실제 파일 내용** — 의심 시 `cat` 또는 `xxd | tail` 로 검증.

---

## 4. AI 역할 체계 (공통)

```
사용자 → Claude(설계자/Wiki) → Codex(구현자) → Claude(리뷰어) → Git
```

각 프로젝트 `AI/agents/codex.md`에 아래 섹션을 추가한다:
- 파일 무결성 규칙 (위 2장 참조)
- 프로젝트별 크리티컬 경계

---

## 5. 커밋 컨벤션 (공통)

```
<type>: <요약 50자 이내>

[선택] 상세 설명
TASK-NNN 관련
```

`type`: feat / fix / refactor / test / docs / chore / lessons
