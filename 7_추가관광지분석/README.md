# 추가 관광지 2개소 온라인 리뷰 분석

전북연구원·임실군청 추가 요청(2026-10-30 안내) 중 **2. 추가 관광지 2개소 온라인 리뷰 데이터 분석**의 코드와 데이터입니다.

| 항목 | 내용 |
|---|---|
| 분석 대상 | 성수산, 오수의견국민여가캠핑장 |
| 플랫폼 | 네이버 플레이스, 구글 지도 |
| 수집 기간 | 2022-01-01 ~ 수집일 전날 (`config.py`의 `DATE_END`로 고정) |
| 분석 | 키워드(빈도·TF-IDF·n-gram) · 연관관계(연관규칙·동시출현 네트워크) · 문장 단위 감성 · 만족·불만 요인 |
| 최종 제출 | 2026-11-14 |

34개소 분석 코드를 **고치지 않고 불러 쓰는 것**을 원칙으로 했습니다. 두 분석의 결과를 같은 기준으로 나란히 놓기 위해서입니다.

## 34개소 코드 재사용 구조

| 단계 | 스크립트 | 34개소에서 가져온 것 | 새로 만든 것 |
|---|---|---|---|
| 0 수집 | `s0_collect_naver.py`, `1_데이터수집/구글/google_reviews.py` | 네이버 수집기 함수 그대로 호출, 구글 수집기에 대상 2곳만 추가 | 장소·저장 위치 설정 |
| 1 통합 | `s1_build_dataset.py` | 통합 데이터 8개 컬럼 형식, 가명 ID·작성자 정보 제거 원칙 | 수집 원본 → 통합 CSV 변환 (34개소 때는 코드가 레포에 없음) |
| 2 전처리 | `s2_preprocess.py` | 1차전처리 규칙 | 규칙을 코드로 역산 (아래 검증 참고), API 번역 |
| 3 키워드 | `s3_keywords.py` | 노트북의 정제·Kiwi·불용어·Top20 로직, TF-IDF 코퍼스 21개소 | Colab 노트북 → 스크립트 |
| 4 연관관계 | `s4_association.py` | `analyze_association.py` 그대로 실행 | 동시출현 네트워크 그림 |
| 5 감성 | `s5_sentiment.py` | `textsplit.py`, `프롬프트_v1.md`(무수정), `check_output.py`, 채점 규칙, 리뷰 집계 규칙 | API 실행, 34개소 검증셋 재채점, 사람 검토표 |
| 6 요인 | `s6_satisfaction.py` | `analyze_satisfaction.py` 그대로 실행 (같은 모델·프롬프트·카테고리) | 관광지별 요인 집계·대표 원문·그림 |
| 7 요약 | `s7_summary.py` | | 보고서용 표·문장 재료 |

설정은 모두 [`config.py`](config.py) 한 곳에 있습니다.

## 실행 순서

### 준비

```bash
cd 7_추가관광지분석
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt      # macOS/Linux: .venv/bin/python
copy .env.example .env                                        # ANTHROPIC_API_KEY 입력
```

`kiwipiepy==0.23.2`는 꼭 이 버전으로 설치합니다. 34개소 노트북과 버전이 다르면 형태소 분석 결과가 달라집니다.

### 0단계 — 수집 (네이버·구글에 접속되는 PC에서)

1. **네이버 장소 ID**: `config.py`의 `naver_place_id`에 넣어 두었습니다 (성수산 13491702, 오수의견국민여가캠핑장 2006533162). 네이버 수집기는 2026-11에 바뀐 API에 맞춰 고쳤습니다(`userIdno` 필드 삭제, 새 헤더 추가).
2. **구글 장소 확인**: `1_데이터수집/구글/`에서 `python google_reviews.py --resolve "임실 성수산" "오수의견 국민여가캠핑장"`으로 `feature_id`를 확인해 `google_reviews.py`의 `TARGETS`(추가 2곳 항목)에 넣습니다.
3. 수집:

```bash
python scripts/s0_collect_naver.py
cd ../1_데이터수집/구글
python google_reviews.py --target 성수산 --limit 3000
python google_reviews.py --target 오수의견국민여가캠핑장 --limit 3000
```

구글은 `--limit`만큼 최신순으로 가져오므로 2022년 리뷰까지 닿도록 넉넉히 줍니다. 결과(`output/{관광지}_google_reviews.csv`)는 1단계가 자동으로 찾습니다. 수집기 사용법과 주의 사항은 [구글 수집기 README](../1_데이터수집/구글/README.md)에 있습니다.

네이버 수집기가 캡차·405로 막히면 몇 시간 뒤 같은 명령을 다시 실행합니다. 받은 데까지 `data/raw/{ID}_raw.json`에 남아 있어 이어받습니다. 계속 막히면 브라우저에서 리뷰 탭을 직접 넘겨 본 뒤 개발자도구 Network 탭에서 HAR(sanitized)로 내보내고 `python scripts/s0_import_har.py {파일.har}`로 합칩니다.

4. 수집이 끝나면 `config.py`의 `DATE_END`를 수집일 전날로 고정합니다.

### 1~7단계 — 분석

```bash
python scripts/run_all.py            # 전 과정
python scripts/run_all.py --no-api   # API 없이 돌릴 수 있는 단계만
```

단계별로 돌릴 때는 아래 순서입니다. 각 스크립트는 저장 전에 `[PASS]/[WARN]/[FAIL]` 자체 검사를 출력하고, `FAIL`이면 그 자리에서 멈춥니다.

| 순서 | 명령 | API | 비고 |
|---|---|:-:|---|
| 1 | `python scripts/s1_build_dataset.py` | | |
| 2 | `python scripts/s2_preprocess.py --translate` | ○ | 외국어 리뷰만. 실명 후보 목록을 확인해 `data/비식별_치환목록.csv`에 적고 1단계부터 다시 실행 |
| 3 | `python scripts/s3_keywords.py` | | |
| 4 | `python scripts/s4_association.py` | ○ | 키워드 정규화. `--no-llm`이면 API 없이 |
| 5 | `python scripts/s5_sentiment.py build` | | |
| 6 | `python scripts/s5_sentiment.py validate --run run1` (run2도) | ○ | 34개소 사람 검증셋 548문장 재채점 |
| 7 | `python scripts/s5_sentiment.py run --run run1` (run2도) | ○ | 독립 2회 실행 |
| 8 | `python scripts/s5_sentiment.py review` | | `output/3_감성/사람검토표.xlsx` 생성 → **사람이 채움** |
| 9 | `python scripts/s5_sentiment.py merge` | | |
| 10 | `python scripts/s6_satisfaction.py` | ○ | 중단되면 다시 실행. 끝난 리뷰는 건너뜀 |
| 11 | `python scripts/s7_summary.py` | | `output/5_요약/분석결과_요약.md` |

**사람이 해야 하는 일은 두 가지**입니다. 실명 후보 확인(2단계)과 감성 검토표 작성(8단계)입니다. 검토표의 `1_혼합확정` 시트는 모델이 `혼합`이나 `?`로 낸 문장을 34개소 267건 확정과 같은 기준으로 판정하고, `2_블라인드검증` 시트는 모델 라벨을 가린 무작위 100문장에 사람 라벨을 적습니다. `review`는 이미 있는 검토표를 덮어쓰지 않습니다.

### 시험 실행

수집 전이라도 34개소 데이터의 다른 관광지 리뷰(사선대관광지, 임실치즈마을)를 가짜 수집 원본으로 만들어 전 과정을 돌려 볼 수 있습니다. 결과는 `_demo/`에만 쓰이고 git에 올라가지 않습니다.

```bash
IMSIL_DEMO=1 python scripts/run_all.py --no-api --demo        # Windows PowerShell: $env:IMSIL_DEMO=1
```

## 34개소 결과와 맞춰 본 기록 (2026-11-02)

새 코드가 34개소 때와 같은 계산을 하는지 34개소 데이터로 확인했습니다.

| 확인 | 결과 |
|---|---|
| 1차전처리 규칙 (`s2`) | 외국어를 뺀 5,206건에서 34개소 1차전처리본과 99.98% 일치 (공백 차이 제외, 1건 다름) |
| 키워드 토큰 (`s3 --check-base`) | Kiwi 0.23.2에서 5,267행 중 99.94% 일치 (3행 다름). 0.24.1은 86.7%, 0.22.2는 94.0% |
| 감성 채점 (`s5 validate --score-only`) | 34개소 ChatGPT 출력을 넣으면 macro-F1 0.906 · 부정 재현율 0.910 · 불일치 4.20% · κ 0.936으로 보고서 수치와 같음 |

## 34개소와 다른 점 (보고서 방법론에 밝힐 것)

- **감성 분류 실행 경로**: 34개소는 ChatGPT 웹 UI에 프롬프트 v1을 붙여넣었고, 이번에는 같은 프롬프트를 Anthropic API(`config.SENT_MODEL`)로 실행합니다. 묶음마다 새 요청을 보내므로 앞 묶음의 답이 뒤로 새지 않습니다. 모델이 달라진 만큼 `validate`로 34개소 사람 검증셋을 이 모델로 다시 채점해 34개소(0.906)와 나란히 보고합니다.
- **temperature**: 현재 모델은 temperature를 받지 않습니다. 34개소와 같이 독립 2회 실행의 불일치율로 변동성을 보고합니다. 모델명·실행 일시·응답 모델 ID·프롬프트 해시는 `output/3_감성/output/run*/실행기록.json`에 남습니다.
- **TF-IDF**: 2개소만으로는 IDF가 의미가 없어 34개소의 21개소 문서에 더해 23개 문서로 계산합니다.
- **연관규칙**: 관광지 단위 규칙을 내기 위해 `--min-place-transactions`를 100에서 20으로 낮췄습니다. 나머지 임계값은 같습니다.

## 확인이 필요한 사항

- **성수산의 범위**: 34개소에 이미 `성수산왕의숲자연휴양림`(리뷰 21건)이 있습니다. 이번 대상이 산 자체(등산로, 상이암 포함 여부)인지 휴양림과 같은 곳인지 교수님께 확인이 필요합니다. 지금은 네이버·구글의 '성수산' 장소를 새로 수집하고, 휴양림은 비교 대상으로만 둡니다 (`config.COMPARE_PLACES`).
- **네이버 날짜 필드**: 작성일(`created`)을 씁니다. 34개소 통합 데이터를 만들 때 어느 필드를 썼는지는 코드가 남아 있지 않아 확인하지 못했습니다.

## 산출물

| 위치 | 내용 | git |
|---|---|:-:|
| `data/raw/` | 수집 원본 (작성자 정보 포함), 리뷰ID 대응표 | 제외 |
| `data/추가관광지_리뷰데이터.csv` | 통합 원본 (비식별) | ○ |
| `data/추가관광지_리뷰데이터_1차전처리.csv` | 1차전처리본 | ○ |
| `data/추가관광지_리뷰데이터_키워드전처리완료.csv` | 토큰 포함 | ○ |
| `data/번역결과.csv` | 외국어 원문·번역문 | ○ |
| `output/1_키워드/` | 빈도·TF-IDF·n-gram Top20, 네이버 키워드 리뷰 집계, 그림 | ○ |
| `output/2_연관관계/` | 연관규칙, 동시출현 노드·엣지, 네트워크 그림 | ○ |
| `output/3_감성/` | 문장목록, LLM 출력, 검증 채점, 최종 문장·리뷰 라벨, 관광지별 집계, 그림 | ○ |
| `output/4_만족불만요인/` | 리뷰별 요인, 관광지별 집계(34개소·인접 관광지 비교 포함), 대표 원문, 그림 | ○ |
| `output/5_요약/` | 보고서용 요약, 데이터 개요, 연도별 리뷰 수 그림 | ○ |
| `output/산출물_목록.csv` | 모든 산출 파일과 행 수 | ○ |
