# 릴리스 체크리스트 — flatten-polymorph

> 상태: **배포 대기 (승인 필요)**
> 준비는 끝났고 실제 업로드(`twine upload`)만 남았다. 업로드는 되돌리기 어려운
> 공개 행위이므로 사용자 승인 후 사람이 직접 실행한다.

---

## 준비 완료 항목

| 항목 | 상태 | 근거 |
|---|---|---|
| 패키지명 | `flatten-polymorph` | `pyproject.toml` |
| 버전 | `0.2.1` | `pyproject.toml` |
| 라이선스 | MIT | `LICENSE`, `pyproject.toml` |
| 빌드 백엔드 | hatchling | `pyproject.toml` |
| 산출물 | wheel + sdist | `python -m build` 클린 빌드 성공 |
| 메타데이터 검증 | **PASSED** | `twine check dist/*` — wheel·sdist 모두 |
| 테스트 | 270 passed | `python -m pytest -q` |
| 뮤테이션 테스트 | 구성됨 | `cosmic-ray.toml` |
| CHANGELOG | 0.2.1까지 기록 | 0.2.0/0.2.1 항목 보강 완료 |
| 문서 | README, USAGE_GUIDE, docs/ | |

---

## 업로드 전 남은 결정 (사용자)

### 1. PyPI 이름 선점 확인
`flatten-polymorph` 가 PyPI에 이미 있는지 확인한다. 있으면 이름을 바꿔야 한다.

```bash
pip index versions flatten-polymorph      # 또는 https://pypi.org/project/flatten-polymorph/
```

### 2. 계정·토큰
PyPI 및 TestPyPI 계정과 API 토큰이 필요하다. 토큰은 `~/.pypirc` 또는
환경변수 `TWINE_USERNAME=__token__`, `TWINE_PASSWORD=pypi-...` 로 준다.
**토큰을 저장소에 커밋하지 않는다.**

### 3. Python 3.13 분류자
현재 분류자는 3.8~3.12까지다. 3.13에서 검증했다면 분류자를 추가한다
(LibCST의 3.13 지원 여부 확인 필요 — 감사에서 다음 호환성 과제로 지목됨).

---

## 업로드 절차 (승인 후 사람이 실행)

```bash
# 0) 깨끗한 상태에서 재빌드
rm -rf dist/ build/
python -m build
python -m twine check dist/*

# 1) TestPyPI 먼저 — 실수를 되돌릴 수 있는 유일한 지점
python -m twine upload --repository testpypi dist/*

# 2) TestPyPI 에서 설치 검증 (새 가상환경에서)
python -m venv /tmp/verify && /tmp/verify/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flatten-polymorph==0.2.1
/tmp/verify/bin/python -c "import flatten_polymorph; print('ok')"

# 3) 문제 없으면 PyPI 본배포
python -m twine upload dist/*

# 4) 태그 + GitHub 릴리스
git tag -a v0.2.1 -m "flatten-polymorph 0.2.1"
git push origin v0.2.1
```

> **PyPI 는 같은 버전을 다시 올릴 수 없다.** 잘못 올리면 삭제해도 그 버전 번호는
> 영구히 사용 불가다. 반드시 TestPyPI 를 먼저 통과시킬 것.

---

## 자동화 상태

`.github/workflows/release.yml` 은 태그 푸시 시 **빌드와 `twine check` 까지만**
수행한다. 업로드 단계는 의도적으로 넣지 않았다 — 배포는 사람이 판단해서
실행하는 편이 안전하다고 보고, 승인 전까지는 자동 공개 경로를 만들지 않는다.
