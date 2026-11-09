# 추가 관광지 2개소 온라인 리뷰 분석

전북연구원·임실군청 추가 요청(2026-10-30 안내) 중 **2. 추가 관광지 2개소 온라인 리뷰 데이터 분석**의 코드와 데이터입니다.
코드는 `src/new_sites/`, 사람과 Claude Code가 만든 입력은 `input/new_sites/`, 결과는 `output/new_sites/`에 있습니다.

| 항목 | 내용 |
|---|---|
| 분석 대상 | 성수산, 오수의견국민여가캠핑장 |
| 플랫폼 | 네이버 플레이스만 (구글 지도에는 두 곳의 리뷰가 없어 수집하지 않음, 2026-11-05 결정) |
| 분석 기간 | 2022-01-01 ~ 2025-12-31 (34개소 보고서와 같은 2022~2025년, `config.py`의 `DATE_START`·`DATE_END`) |
| 분석 | 키워드(빈도·TF-IDF·n-gram) · 연관관계(연관규칙·동시출현 네트워크) · 문장 단위 감성 · 만족·불만 요인 |
| 최종 제출 | 2026-11-14 |

두 가지를 원칙으로 했습니다.

- **34개소 분석 코드를 고치지 않고 불러 씁니다.** 두 분석의 결과를 같은 기준으로 나란히 놓기 위해서입니다. 설정(대상·기간·불용어·경로)은 모두 [`src/new_sites/config.py`](../src/new_sites/config.py) 한 곳에 있습니다.
- **API를 쓰지 않습니다.** LLM이 판정하는 단계(문장 감성, 만족·불만 요인, 외국어가 있으면 번역)는 코드가 판정 대상을 `output/new_sites/`에 내보내고, Claude Code가 지시문대로 판정해 `input/new_sites/`에 저장하면, 코드가 그 파일을 읽어 결과를 만듭니다. 34개소도 같은 방식이었습니다(감성은 ChatGPT 웹 UI, 요인은 Claude Code 대화). 판정 파일을 git에 올리므로 다른 PC에서 돌려도 같은 결과가 나옵니다.

## 34개소 코드 재사용 구조

| 단계 | 스크립트 (`src/new_sites/`) | 34개소에서 가져온 것 | 새로 만든 것 |
|---|---|---|---|
| 수집 | `collect_naver.py` · `import_har.py` · `retry_naver.py` | 네이버 수집기(`src/collect/naver_reviews.py`) 함수 그대로 호출 | 장소 설정, 브라우저 기록(HAR)에서 꺼내기 |
| 통합 | `build_dataset.py` | 통합 데이터 8개 컬럼 형식, 가명 ID·작성자 정보 제거 원칙 | 수집 원본 → 통합 CSV 변환 (34개소 때는 코드가 레포에 없음) |
| 전처리 | `preprocess.py` | 1차전처리 규칙 | 규칙을 코드로 역산 (아래 검증 참고), 번역 결과 반영 |
| 키워드 | `keywords.py` | 노트북의 정제·Kiwi·불용어·Top20 로직, TF-IDF 코퍼스 21개소 | 동시에 2개소 처리 |
| 연관관계 | `association.py` | `src/association/analyze_association.py` 그대로 실행 (34개소 보고서와 같은 `--no-llm`) | 동시출현 네트워크 그림 |
| 감성 | `sentiment.py` | `textsplit.py`, `프롬프트_v1.md`(무수정), `check_output.py`, 채점 규칙, 리뷰 집계 규칙 | 판정 묶음 내보내기, 34개소 검증셋 재채점, 사람 검토표 |
| 요인 | `satisfaction.py` | `analyze_satisfaction.py`의 프롬프트·카테고리·결과 행 변환, `annotation/merge.py`의 원문 대조 규칙 | 판정 대상 내보내기, 관광지별 요인 집계·대표 원문·그림 |
| 요약 | `summary.py` | | 보고서용 표·문장 재료 |
| 합산 | `combined_report.py` | | 34개소 + 추가 2개소를 합친 보고서 리뷰 분석 절의 표·그림 (그림 2-7~2-10, 표 2-2) |

## 전체 흐름

```text
1. 수집            collect_naver.py (막히면 import_har.py)          → output/collect/naver/
2. 코드 단계        run_all.py                                       → output/new_sites/ (판정 대상 내보내기까지)
3. Claude Code 판정 지시문 4개 (input/new_sites/claude_지시문/)        → input/new_sites/ 의 판정 파일
4. 사람 검토        감성 검토표 채우기                                  → input/new_sites/사람검토표.xlsx
5. 코드 단계 다시   run_all.py                                       → output/new_sites/ 의 최종 결과·요약
```

명령은 모두 **레포 최상위에서** 실행합니다. 설치는 [README](../README.md#준비)를 따릅니다.
`kiwipiepy==0.23.2`는 꼭 이 버전으로 설치합니다. 34개소 노트북과 버전이 다르면 형태소 분석 결과가 달라집니다.

### 1. 수집 (네이버에 접속되는 PC에서)

장소 ID는 `config.py`의 `naver_place_id`에 넣어 두었습니다 (성수산 13491702, 오수의견국민여가캠핑장 2006533162).

```bash
python src/new_sites/collect_naver.py
```

결과는 34개소 수집과 같은 `output/collect/naver/`에 쌓입니다 (`{관광지명}_naver_reviews.csv`, `{ID}_raw.json`, `{관광지명}_수집정보.json`). 작성자 닉네임이 들어 있어 git에는 올라가지 않습니다.

네이버 수집기가 캡차·405로 막히면 몇 시간 뒤 같은 명령을 다시 실행합니다. 받은 데까지 `{ID}_raw.json`에 남아 있어 이어받습니다(`retry_naver.py`는 이것을 몇 시간 간격으로 대신 해 줍니다). 계속 막히면 브라우저에서 리뷰 탭을 직접 끝까지 넘겨 본 뒤, 개발자도구 Network 탭에서 HAR(sanitized)로 내보내고 합칩니다. HAR 파일은 레포에 넣지 않고 내 PC에 둡니다.

```bash
python src/new_sites/import_har.py 다운로드\m.place.naver.com.har
```

수집은 수집일까지의 리뷰를 모두 받고, 분석에는 `config.py`의 `DATE_START`~`DATE_END` 안의 리뷰만 씁니다. 34개소 보고서의 분석 기간에 맞춰 2022-01-01~2025-12-31로 정했습니다 (2026-11-07). 처음에는 첫 수집일 전날(2026-11-02)까지 썼습니다.

#### 분석 기간을 바꾸면

`build_dataset.py`가 기간 밖 리뷰를 빼고, 남은 리뷰의 가명 ID는 대응표로 그대로 유지합니다. 그 뒤 단계는 이렇게 됩니다.

- **감성**: 판정 묶음은 문장 전체를 섞어 150문장씩 나누므로, 리뷰가 하나만 빠져도 묶음 구성과 `unit_id`가 모두 바뀝니다. `sentiment.py build`가 이것을 알아채고 이전 결과를 `.local/`로 옮긴 뒤, 이전 판정 파일(`input/new_sites/sentiment/runs/`)과 채운 검토표(`input/new_sites/사람검토표.xlsx`)를 쓰지 않도록 멈춥니다. 이 파일들을 `.local/` 아래로 옮기고, 새 묶음으로 run1·run2를 다시 판정하고, 사람 검토표도 새로 채웁니다. 34개소 검증셋 판정(`검증_34개소/`)은 그대로 씁니다.
- **만족·불만 요인**: 리뷰 하나씩 따로 판정하므로 `annotations.jsonl`을 그대로 씁니다. 기간 밖 리뷰의 줄은 지우지 않아도 되고, `satisfaction.py check`가 "지금 판정 대상이 아닌 리뷰의 줄 N개는 읽지 않습니다"라고 알려 줍니다.
- **키워드·연관관계·요약**: 코드가 다시 계산합니다.

### 2. 코드 단계

```bash
python src/new_sites/run_all.py
```

판정 파일이 아직 없는 단계는 판정 대상만 내보내고 넘어갑니다. 마지막에 `남은 일`로 무엇을 채워야 하는지 알려 줍니다. 처음 실행하면 아래가 생깁니다.

| 판정 대상 (코드가 만듦) | 내용 |
|---|---|
| `output/new_sites/sentiment/chunks/추가_NN.txt` | 문장 감성 판정 묶음 (캠핑장 리뷰 235건 → 약 900문장, 150문장씩 7개 안팎) |
| `output/sentiment/llm_labeling/chunks/*.txt` | 34개소 검증셋 묶음 12개 (548문장, 34개소 때 만든 그대로) |
| `output/new_sites/satisfaction/판정대상.jsonl` · `판정프롬프트.txt` | 요인 판정 대상(본문 있는 리뷰)과 34개소 프롬프트 |
| `output/new_sites/번역대상.csv` | 외국어 리뷰가 있을 때만 (2026-11 수집분에는 없음) |

`preprocess.py`가 출력하는 **실명 후보 목록**도 이때 확인합니다. 문맥을 보고 실명이면 `input/new_sites/비식별_치환목록.csv`(`find,replace`)에 적고 다시 실행합니다. 이 파일은 실명이 그대로 들어 있어 git에 올리지 않습니다.

### 3. Claude Code 판정

레포 폴더를 Claude Code로 열고 아래 문장을 그대로 보냅니다. 지시문이 읽을 파일·쓸 파일·형식·점검 명령을 모두 담고 있습니다.
**대화 하나에 판정 하나만 합니다.** 다음 판정으로 넘어갈 때는 새 대화(`/clear` 또는 Claude Code를 새로 열기)를 시작합니다. 같은 대화에서 run2를 하면 run1의 답을 보고 답하게 되어 2회 판정이 무효가 됩니다.

| 순서 | Claude Code에 보낼 문장 | 판정 파일 (`input/new_sites/…`) | 점검 |
|---|---|---|---|
| ① | `input/new_sites/claude_지시문/감성_검증.md 를 읽고 그대로 해 줘. 이번은 run1 이야.` | `sentiment/검증_34개소/run1/` | `sentiment.py check` |
| ② | (새 대화) `… 감성_검증.md … 이번은 run2 야.` | `sentiment/검증_34개소/run2/` | `sentiment.py check` |
| ③ | (새 대화) `input/new_sites/claude_지시문/감성_판정.md 를 읽고 그대로 해 줘. 이번은 run1 이야.` | `sentiment/runs/run1/` | `sentiment.py check` |
| ④ | (새 대화) `… 감성_판정.md … 이번은 run2 야.` | `sentiment/runs/run2/` | `sentiment.py check` |
| ⑤ | (새 대화) `input/new_sites/claude_지시문/요인.md 를 읽고 그대로 해 줘.` | `satisfaction/annotations.jsonl` | `satisfaction.py check` |
| (번역) | 외국어 리뷰가 있을 때만: `input/new_sites/claude_지시문/번역.md 를 읽고 그대로 해 줘.` | `번역결과.csv` | `preprocess.py` |

- ①②를 먼저 하는 것을 권합니다. `python src/new_sites/sentiment.py validate --run run1`(run2도)로 34개소 사람 라벨과 채점해, Claude Code의 판정이 34개소 ChatGPT(macro-F1 0.906~0.908)와 같은 수준인지 먼저 확인합니다. 채점은 사람이 직접 실행합니다. 판정하는 대화가 채점 결과를 보지 않게 하기 위해서입니다.
- 각 run 폴더에는 Claude Code가 `실행기록.md`(도구·모델·날짜·프롬프트 버전)를 남깁니다. 모델 이름은 Claude Code의 `/model`로 확인해 고칩니다. 보고서의 방법 설명에 그대로 씁니다.
- 판정 파일은 묶음별로 나누든 한 파일로 합치든 상관없습니다. `unit_id`로 시작하는 줄만 읽고 나머지 줄(대화 문구 등)은 개수만 세고 건너뜁니다.
- 판정이 끝난 파일은 git에 커밋합니다. 이 파일이 결과 재현의 근거입니다.

### 4. 사람 검토

감성 run1이 끝난 뒤 `run_all.py`(또는 `sentiment.py review`)가 `output/new_sites/sentiment/사람검토표.xlsx` 양식을 만듭니다. 이 파일을 `input/new_sites/사람검토표.xlsx`로 복사해 채웁니다. 코드는 `input/`의 채운 검토표를 덮어쓰지 않습니다.

- `1_혼합확정`: 모델이 `혼합`이나 `?`로 낸 문장. `최종판정` 칸에 긍정·부정·중립을 적습니다 (34개소 267건 확정과 같은 기준).
- `2_블라인드검증`: 모델 라벨을 가린 무작위 100문장. `사람라벨` 칸에 긍정·부정·중립을 적습니다. 판정 기준은 `docs/sentiment/0001-라벨링-지침서.html`입니다.

### 5. 코드 단계 다시

```bash
python src/new_sites/run_all.py
```

판정이 다 갖춰진 단계는 결과까지 만듭니다. `남은 일`이 비면 모든 단계가 끝난 것입니다. 보고서 재료는 `output/new_sites/summary/분석결과_요약.md`에 모입니다.

### 단계별 명령

`run_all.py`가 순서대로 부르는 명령입니다. 각 스크립트는 저장 전에 `[PASS]/[WARN]/[FAIL]` 자체 검사를 출력하고, `FAIL`이면 그 자리에서 멈춥니다.

| 순서 | 명령 (`python src/new_sites/…`) | 읽는 판정 (`input/new_sites/…`) | 출력 (`output/new_sites/…`) · 비고 |
|---|---|---|---|
| 1 | `build_dataset.py` | `비식별_치환목록.csv` | `추가관광지_리뷰데이터.csv` |
| 2 | `preprocess.py` | `번역결과.csv` | `추가관광지_리뷰데이터_1차전처리.csv`, 번역이 빠진 외국어 리뷰가 있으면 `번역대상.csv` |
| 3 | `keywords.py` | | `keyword/` |
| 4 | `association.py` | | `association/` |
| 5 | `sentiment.py build` | | `sentiment/문장목록.csv`, `sentiment/chunks/` |
| 6 | `sentiment.py check` | `sentiment/runs/`, `sentiment/검증_34개소/` | 덜 된 묶음, 2회 불일치율 → `sentiment/재현성.json`. 사람 라벨은 읽지 않는다 |
| 7 | `sentiment.py validate --run run1` (run2도) | `sentiment/검증_34개소/` | `sentiment/검증_34개소/채점_run*.json` (34개소 사람 라벨로 채점) |
| 8 | `sentiment.py review` | `sentiment/runs/run1/` | `sentiment/사람검토표.xlsx` 양식 |
| 9 | `sentiment.py merge` | `sentiment/runs/run1/`, `사람검토표.xlsx` | 최종 문장·리뷰 라벨, 관광지별 집계, 그림 |
| 10 | `satisfaction.py export` | | `satisfaction/판정대상.jsonl`, `판정프롬프트.txt` |
| 11 | `satisfaction.py check` | `satisfaction/annotations.jsonl` | 형식·원문 대조·남은 리뷰 (출력 파일 없음) |
| 12 | `satisfaction.py merge` | `satisfaction/annotations.jsonl` | 리뷰별 요인(34개소와 같은 열), 관광지별 집계, 대표 원문, 그림 |
| 12-1 | `combined_report.py` | | `combined/` — 34개소와 합친 연도별·요인·관광지별·계절별 숫자와 그림 4개, `수치요약.md` (34개소 숫자 재현 검사 포함) |
| 13 | `summary.py` | | `summary/분석결과_요약.md`, `산출물_목록.csv` |

### 판정 파일이 지금 데이터와 어긋나지 않게 하는 장치

- **감성**: 리뷰가 바뀐 뒤 `build`를 다시 하면 묶음 구성과 `unit_id`가 달라집니다. 이때 이전 결과·검토표 양식·최종 라벨은 `.local/new_sites_감성_이전실행/{시각}/`으로 옮기고(지우지 않음), `input/`의 판정 파일과 채운 검토표는 건드리지 않되 이전 문장으로 만든 것으로 기록합니다. 그 파일을 옮기거나 새 판정으로 바꾸기 전까지 `check`·`review`·`merge`가 멈춥니다.
- **요인**: 판정 줄마다 리뷰 ID(`rid`)와 본문 확인값(`h`, 본문의 SHA-256 앞 8자리)을 적습니다. 다시 수집한 리뷰가 수정됐거나 실명을 가려 본문이 바뀌면 `h`가 달라져 `check`가 그 줄을 오류로 알려 줍니다. span·opinion이 본문에 그대로 있는지도 봅니다.
- **번역**: `번역결과.csv`의 `원문`이 지금 본문과 다르면 그 번역은 쓰지 않고 다시 번역 대상으로 내보냅니다.
- **결과**: `sentiment/`·`satisfaction/`의 `입력기록.json`에 결과를 만든 입력 파일과 해시가 남습니다. 결과를 만든 뒤 판정이 바뀌면 `summary.py`가 요약에 경고를 넣습니다.
- 가명 ID는 `output/collect/naver/추가관광지_리뷰ID_대응표.csv`에 남아 있어 다시 돌려도 바뀌지 않습니다.

### 시험 실행

수집 원본과 판정 파일이 없어도 전 과정을 돌려 볼 수 있습니다. 34개소 데이터의 다른 관광지 리뷰(사선대관광지, 임실치즈마을)로 가짜 수집 원본을 만들고, 34개소에서 이미 만든 판정(검증셋 ChatGPT 판정, 최종 문장 라벨, 요인 판정)을 옮겨 붙여 가짜 판정 파일을 만듭니다(`demo_judgments.py`). 결과는 `output/_demo/`에만 쓰이고 git에 올라가지 않습니다.

```bash
IMSIL_DEMO=1 python src/new_sites/run_all.py --demo        # Windows PowerShell: $env:IMSIL_DEMO=1
```

검증셋 채점이 34개소 보고 수치(run1 macro-F1 0.906 · 부정 재현율 0.910, run2 0.908 · 0.820, 2회 불일치 4.20% · κ 0.936)와 같게 나오면 채점 코드가 맞다는 뜻입니다.

## 재현성 — 다른 PC에서 같은 결과를 얻으려면

- 판정 파일(`input/new_sites/`)과 수집 뒤 통합 데이터(`output/new_sites/추가관광지_리뷰데이터.csv`)가 git에 있으므로, 같은 커밋에서 `run_all.py`를 돌리면 같은 결과가 나옵니다. 수집 원본은 git에 없으므로 다른 PC에서는 `build_dataset.py`를 건너뛰고 `preprocess.py`부터 돌립니다.
- `입력기록.json`의 해시가 같으면 같은 판정 파일로 만든 결과입니다.
- `kiwipiepy` 버전이 다르면 키워드 토큰이 달라집니다(`keywords.py`가 버전을 검사합니다).
- LLM 판정을 **다시 하면** 결과가 조금씩 달라집니다. temperature를 고정할 수 없기 때문입니다. 34개소와 같이 독립 2회 판정의 불일치율(`재현성.json`)로 이 변동을 보고하고, 판정 결과는 파일로 고정해 둡니다.

## 34개소 결과와 맞춰 본 기록 (2026-11-02, 2026-11-06)

새 코드가 34개소 때와 같은 계산을 하는지 34개소 데이터로 확인했습니다.

| 확인 | 결과 |
|---|---|
| 1차전처리 규칙 (`preprocess.py`) | 외국어를 뺀 5,206건에서 34개소 1차전처리본과 99.98% 일치 (공백 차이 제외, 1건 다름) |
| 키워드 토큰 (`keywords.py --check-base`) | Kiwi 0.23.2에서 5,267행 중 99.94% 일치 (3행 다름). 0.24.1은 86.7%, 0.22.2는 94.0% |
| 감성 채점 (`sentiment.py validate`) | 34개소 ChatGPT 판정을 검증셋 판정 자리에 넣으면 macro-F1 0.906 · 0.908, 부정 재현율 0.910 · 0.820, 불일치 4.20% · κ 0.936으로 보고서 수치와 같음 (시험 실행) |
| 요인 원문 대조 (`satisfaction.py check`) | 시험 실행에서 34개소 요인 판정 62개를 새 전처리 본문에 옮겼을 때 span·opinion이 모두 본문에 있음 |

## 수집 기록

| 관광지 | 플랫폼 | 수집 | 방법 |
|---|---|---|---|
| 성수산 | 네이버 | 2/2건 (2026-11-03) | 수집기 |
| 오수의견국민여가캠핑장 | 네이버 | 237/238건 (2026-11-03~04) | 수집기 100건 + 브라우저 기록(HAR) 188건, 겹친 51건 제외 |

- 네이버가 2026-11부터 자동 요청에 캡차(사람 확인)를 요구해, 캠핑장은 수집기로 100건을 받은 뒤 막혔습니다. 나머지는 사람이 브라우저에서 리뷰를 끝까지 넘겨 본 기록(HAR)에서 꺼냈습니다 (`import_har.py`). 응답 형식이 같아 CSV 컬럼과 값도 같습니다.
- 238건 중 빠진 1건은 두 수집 사이에 새로 올라온 리뷰로 보입니다. 합친 237건의 작성일이 모두 2026-11-02 이전이고, 수집기로 받을 때의 전체 수가 237건이었습니다. 분석 기간(2025-12-31까지) 밖이라 분석 대상에 들지 않습니다.
- 캠핑장 네이버 리뷰 237건의 작성일은 2025-07-21 ~ 2026-11-02입니다 (2025년 124건, 2026년 113건). 분석 기간(2022~2025년)에 드는 리뷰는 2025년의 124건입니다. 외국어 리뷰는 없습니다.
- 성수산 네이버 리뷰 2건 중 분석 기간에 드는 리뷰는 1건(2025-11-07)입니다.
- 구글 지도에는 두 곳의 리뷰가 없어 수집하지 않았습니다. `config.PLATFORMS`에 `"구글"`을 넣으면 `output/collect/google/`의 같은 이름 수집 파일도 읽도록 코드는 남겨 두었습니다.

## 34개소와 다른 점 (보고서 방법론에 밝힐 것)

- **플랫폼**: 34개소는 구글·네이버 두 플랫폼, 추가 2개소는 네이버만입니다. 플랫폼별 비교는 34개소의 네이버 리뷰와 놓아야 같은 조건입니다.
- **감성 판정 도구**: 34개소는 ChatGPT 웹 UI에 프롬프트 v1과 묶음을 붙여 넣었고, 추가 2개소는 같은 프롬프트와 같은 형식의 묶음을 Claude Code가 파일로 읽어 판정합니다. 도구가 바뀌었으므로 34개소 사람 검증셋 548문장을 같은 도구로 다시 판정·채점해 34개소(0.906)와 나란히 보고합니다. 모델 이름과 날짜는 각 run 폴더의 `실행기록.md`에 있습니다.
- **판정의 독립성**: 웹 UI는 다른 파일을 볼 수 없었지만 Claude Code는 레포의 다른 파일을 열 수 있습니다. 지시문이 읽을 파일을 정해 두고 사람 라벨·다른 run의 결과를 열지 못하게 했으며, 채점은 판정 대화 밖에서 사람이 실행합니다.
- **temperature**: Claude Code에서는 temperature를 고정할 수 없습니다. 34개소(웹 UI)와 같이 독립 2회 판정의 불일치율로 변동성을 보고합니다.
- **만족·불만 요인**: 프롬프트·카테고리·결과 형식은 34개소와 같고, 판정 줄을 번호 대신 리뷰 ID와 본문 확인값으로 잇습니다.
- **TF-IDF**: 2개소만으로는 IDF가 의미가 없어 34개소의 21개소 문서에 더해 23개 문서로 계산합니다.
- **연관규칙**: 관광지 단위 규칙을 내기 위해 `--min-place-transactions`를 20으로 낮췄습니다 (스크립트 기본 100, 34개소 보고서 결과는 50). 나머지 임계값과 `--no-llm`은 34개소 보고서와 같습니다. 성수산은 리뷰가 2건이라 관광지 단위 규칙이 나오지 않습니다.

## 확인이 필요한 사항

- **성수산의 범위**: 34개소에 이미 `성수산왕의숲자연휴양림`(리뷰 21건)이 있습니다. 이번 대상이 산 자체(등산로, 상이암 포함 여부)인지 휴양림과 같은 곳인지 교수님께 확인이 필요합니다. 지금은 네이버의 '성수산' 장소를 새로 수집했습니다. 보고서는 추가 2개소만 다루기로 해서(2026-11-09) 휴양림 등 인접 관광지는 비교 대상에서도 뺐습니다 (`config.COMPARE_PLACES` 비움).
- **네이버 날짜 필드**: 작성일(`created`)을 씁니다. 34개소 통합 데이터를 만들 때 어느 필드를 썼는지는 코드가 남아 있지 않아 확인하지 못했습니다.

## 파일 위치

| 위치 | 내용 | 만드는 것 | git |
|---|---|---|:-:|
| `output/collect/naver/` | 수집 원본 (작성자 정보 포함), `추가관광지_리뷰ID_대응표.csv` | 코드 | 제외 |
| `input/new_sites/claude_지시문/` | Claude Code에 주는 지시문 4개 (감성_검증·감성_판정·요인·번역) | 사람 | ○ |
| `input/new_sites/sentiment/검증_34개소/run1·run2/` | 34개소 검증셋 감성 판정과 `실행기록.md` | Claude Code | ○ |
| `input/new_sites/sentiment/runs/run1·run2/` | 추가 관광지 감성 판정과 `실행기록.md` | Claude Code | ○ |
| `input/new_sites/satisfaction/annotations.jsonl` | 만족·불만 요인 판정 | Claude Code | ○ |
| `input/new_sites/번역결과.csv` | 외국어 원문·번역문 (외국어 리뷰가 있을 때만) | Claude Code | ○ |
| `input/new_sites/사람검토표.xlsx` | 사람이 채운 감성 검토표 | 사람 | ○ |
| `input/new_sites/비식별_치환목록.csv` | 사람이 실명으로 확인한 표현 → `○○○` (실명이 그대로 들어 있어 내 PC에만 둔다) | 사람 | 제외 |
| `output/new_sites/추가관광지_리뷰데이터.csv` | 통합 원본 (비식별) | 코드 | ○ |
| `output/new_sites/추가관광지_리뷰데이터_1차전처리.csv` | 1차전처리본 | 코드 | ○ |
| `output/new_sites/번역대상.csv` | 번역이 빠진 외국어 리뷰 (원문을 담은 중간 파일) | 코드 | 제외 |
| `output/new_sites/keyword/` | 토큰 파일, 빈도·TF-IDF·n-gram Top20, 네이버 키워드 리뷰 집계, 그림 | 코드 | ○ |
| `output/new_sites/association/` | 연관규칙, 동시출현 노드·엣지, 네트워크 그림 | 코드 | ○ |
| `output/new_sites/sentiment/` | 문장목록, 판정 묶음(`chunks/`), 검증 채점, 재현성, 검토표 양식, 최종 라벨, 관광지별 집계, 그림, 입력기록 | 코드 | ○ |
| `output/new_sites/satisfaction/` | 판정 대상·프롬프트, 리뷰별 요인, 관광지별 집계(34개소 전체 비교 포함), 대표 원문, 그림, 입력기록 | 코드 | ○ |
| `output/new_sites/summary/` | 보고서용 요약, 데이터 개요, 연도별 리뷰 수 그림 | 코드 | ○ |
| `output/new_sites/산출물_목록.csv` | 모든 산출 파일과 행 수 | 코드 | ○ |
