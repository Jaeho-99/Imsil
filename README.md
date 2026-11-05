# 임실군 주요 관광지 온라인 리뷰 빅데이터 분석

구글 지도와 네이버 플레이스에 올라온 임실군 관광지 리뷰를 수집해 키워드, 감성, 연관관계, 만족·불만 요인, 시계열을 분석한 코드와 데이터입니다.

| 항목 | 내용 |
|---|---|
| 수집 리뷰 | 5,267건 (구글 3,233 · 네이버 2,034) |
| 수집 기간 | 2022-01-01 ~ 2026-08-10 |
| 본문이 있는 리뷰 | 3,208건 (감성분석 문장 5,793개) |
| 시계열 분석 기간 | 2022~2025년 |
| 추가 분석 | 성수산 · 오수의견국민여가캠핑장 2개소의 네이버 리뷰 (2026-11 추가 요청, [docs/new_sites.md](docs/new_sites.md)) |

## 폴더 구성

```
src/      코드. 분석 단계마다 하위 폴더가 하나씩 있습니다
input/    코드가 만들지 않는 파일: 통합 리뷰 데이터, 사람이 판정한 표, LLM 응답을 붙여 넣은 파일
output/   코드가 만든 파일. 단계마다 하위 폴더가 있고, 앞 단계의 output 을 다음 단계가 읽습니다
docs/     방법 기록, 라벨링 지침서, 제출 당시 문서
```

| 단계 | 보고서 | 코드 | 주요 입력 | 출력 |
|---|---|---|---|---|
| 데이터 수집 | 수집 | `src/collect/` | 네이버 플레이스, 구글 지도 | `output/collect/` |
| 키워드 | 2장 | `src/keyword/` | `input/임실군_관광지_리뷰데이터_1차전처리.csv` | `output/keyword/` |
| 감성 | 3장 | `src/sentiment/` | 1차전처리 CSV, `input/sentiment/` | `output/sentiment/` (최종본은 `final/`) |
| 연관관계 | 4장 | `src/association/` | `output/keyword/리뷰데이터_키워드전처리완료.csv` | `output/association/` |
| 만족·불만 요인 | 5장 | `src/satisfaction/` | 1차전처리 CSV, `input/satisfaction/` | `output/satisfaction/` |
| 시계열 | 6장 | `src/timeseries/` | `input/임실군_관광지_리뷰데이터.csv`, `output/sentiment/final/` | `output/timeseries/` |
| 추가 관광지 2개소 | 추가 분석 | `src/new_sites/` | `output/collect/naver/`, `input/new_sites/` | `output/new_sites/` |

- 모든 명령은 **레포 최상위에서** `python src/<단계>/<스크립트>.py` 형태로 실행합니다. 경로는 [`src/paths.py`](src/paths.py) 한 곳에서 정하므로 다른 폴더에서 실행해도 같은 파일을 읽고 씁니다.
- 스크립트는 `output/`에만 쓰고 `input/`은 읽기만 합니다. 예외는 판정 입력 도구인 `src/satisfaction/annotation/add.py` 하나로, 새 판정을 `input/satisfaction/annotations.jsonl`에 덧붙입니다.
- 보고서에 쓴 결과는 `output/`에 커밋되어 있습니다. 스크립트를 다시 실행하면 같은 이름의 파일을 덮어쓰므로, `git diff`로 달라진 곳을 확인하고 `git restore output/`으로 되돌릴 수 있습니다.
- 옛 폴더(`1_데이터수집/` … `7_추가관광지분석/`)의 파일이 어디로 옮겨졌는지는 [docs/폴더_대응표.md](docs/폴더_대응표.md)에 있습니다.

## 준비

```bash
python -m venv .venv
.venv\Scripts\activate              # macOS·Linux: source .venv/bin/activate
pip install -r requirements.txt
```

- Python 3.11 이상이 필요합니다. 2026-11-05 재현 확인에 쓴 패키지 버전은 [`requirements.txt`](requirements.txt) 머리말에 있습니다.
- `kiwipiepy`는 0.23.2로 고정했습니다. 버전이 다르면 형태소 분석 결과가 달라져 키워드 결과도 달라집니다.
- 그래프의 한글은 Windows의 맑은 고딕으로 그립니다. 이 글꼴이 없으면 PNG의 한글이 깨질 수 있지만 CSV 수치는 같습니다.
- 감성분석 방법 ②(사전학습 모델)를 다시 채점할 때만 `pip install torch transformers`를 추가합니다. 최종 결과 재현에는 필요 없습니다.
- 구글 지도 수집기는 따로 설치합니다. [docs/collect_google.md](docs/collect_google.md)를 보세요.

### API 키는 결과 재현에 필요 없습니다

보고서 결과는 API 없이 만들었습니다. 감성분석의 LLM 판정은 ChatGPT 웹 UI에 붙여 넣어 받은 응답을, 만족·불만 요인 판정은 Claude Code 대화에서 만든 결과를 `input/`에 저장해 두었고, 연관관계는 원본 키워드로 계산했습니다(`--no-llm`). 아래 명령은 모두 이 파일들을 읽습니다.

Anthropic API를 직접 부르는 기능(연관관계 키워드 정규화, 만족·불만 요인 자동 추출, 추가 관광지의 번역·감성·요인)을 쓸 때만 [`.env.example`](.env.example)을 `.env`로 복사해 `ANTHROPIC_API_KEY`를 넣습니다. `.env`는 git에 올라가지 않습니다.

### 옛 폴더 구조에서 옮겨 오기

옛 구조로 작업하던 PC라면 `git pull` 뒤에도 git이 관리하지 않는 파일(수집 원본, `.env`, 구글 로그인 프로필, 추가 관광지 중간 산출물)이 옛 폴더에 남아 있습니다. 아래 명령으로 새 위치에 옮깁니다.

```bash
python src/migrate_old_layout.py            # 무엇을 어디로 옮길지 보여 주기만 합니다
python src/migrate_old_layout.py --apply    # 실제로 옮깁니다
```

새 위치에 같은 이름의 파일이 있으면 덮어쓰지 않고 알려 주고, 옮긴 뒤 비어 버린 옛 폴더만 지웁니다. 옛 폴더 안의 가상환경(`.venv`)은 옮기지 않으므로 위 방법으로 레포 최상위에 새로 만듭니다.

## 실행 순서

수집에서 시작해 각 분석으로 이어집니다. 단계 사이에 순서가 있는 곳은 **키워드 → 연관관계**와 **감성 → 시계열** 두 군데이고, 나머지 분석은 `input/`의 리뷰 데이터에서 바로 시작합니다. 앞 단계의 결과가 이미 `output/`에 있으므로 어느 단계든 따로 다시 실행할 수 있습니다.

### 1. 데이터 수집 — `src/collect/`

| 명령 | 하는 일 | 출력 |
|---|---|---|
| `python src/collect/naver_reviews.py` | 네이버 플레이스 방문자 리뷰 수집. 장소 ID를 인자로 주면 그 장소만 수집 | `output/collect/naver/{ID}_raw.json`, `{관광지명}_naver_reviews.csv` |
| `python src/collect/naver_review_counts.py` | 관광지별 네이버 리뷰 수 막대그래프 | `output/collect/naver_review_counts.png` |
| [docs/collect_google.md](docs/collect_google.md) | 구글 지도 리뷰 수집 (로그인 준비 → 수집 → 파서 점검) | `output/collect/google/` |

- 수집 원본에는 작성자 닉네임과 ID가 들어 있어 `output/collect/naver/`와 `output/collect/google/`은 git에서 제외됩니다.
- 네이버 수집기가 405 응답으로 멈추면 받은 데까지 `{ID}_raw.json`에 저장됩니다. 시간을 두고 다시 실행하면 이어 받습니다.

34개소 수집 원본을 통합 데이터(8개 열, 가명 리뷰 ID)와 1차전처리본으로 만든 코드는 남아 있지 않습니다. 그 결과인 두 파일을 `input/`에 두었고 모든 분석은 여기서 시작합니다. 추가 관광지 분석에서는 이 과정을 코드로 다시 만들었습니다(`src/new_sites/build_dataset.py`, `preprocess.py`).

| 파일 | 내용 | 읽는 단계 |
|---|---|---|
| `input/임실군_관광지_리뷰데이터.csv` | 통합 리뷰 5,267건 (비식별 처리) | 시계열 |
| `input/임실군_관광지_리뷰데이터_1차전처리.csv` | 1차전처리본 | 키워드, 감성, 만족·불만 요인 |

### 2. 키워드 분석 (보고서 2장) — `src/keyword/`

```bash
python src/keyword/keyword_analysis.py
```

- 입력은 1차전처리 CSV이고, 출력은 `output/keyword/`의 6개 파일입니다. `리뷰데이터_키워드전처리완료.csv`(리뷰별 토큰)는 연관관계 분석과 추가 관광지 분석이 읽습니다. 나머지는 관광지별 빈도·TF-IDF·Bigram·Trigram Top 20과 빈도·TF-IDF 비교표입니다.
- Colab 노트북([docs/archive/임실_리뷰데이터분석_키워드.ipynb](docs/archive/임실_리뷰데이터분석_키워드.ipynb))을 같은 순서와 같은 값으로 옮긴 스크립트입니다. `--out-dir 폴더`를 주면 기존 결과를 두고 다른 폴더에 저장합니다.

### 3. 감성 분석 (보고서 3장) — `src/sentiment/`

최종 결과는 `output/sentiment/final/`에 있습니다. 문장 라벨(`전수_문장라벨_최종.csv`, 5,793문장), 리뷰 라벨, 관광지별 문장·리뷰 감성, 변경 내역, 결과 요약(`전수_결과_최종.md`)입니다.

**빠른 재현.** API와 LLM 없이, 사람이 확정한 판정(`input/`)과 전수 라벨에서 최종본을 다시 만듭니다.

```bash
python src/sentiment/mixed_final_review/finalize_40.py    # 혼합 40건 판정 + 분할 조각 → 혼합40_최종.csv
python src/sentiment/mixed_final_review/merge_final.py    # 혼합 267건 확정 반영 → output/sentiment/final/
```

**전 과정.** 채택한 방법(③ LLM)에는 문장 묶음을 ChatGPT 웹 UI에 붙여 넣고 응답을 저장하는 수동 단계가 있어 명령 한 번으로 끝나지 않습니다. 사람과 LLM이 만든 결과는 오른쪽 열의 위치에 저장되어 있으므로, 그 뒤의 코드는 그대로 다시 실행할 수 있습니다. 명령은 모두 `python src/sentiment/…`입니다.

| 순서 | 스크립트 | 하는 일 | 사람·LLM 단계 → 결과 위치 |
|---|---|---|---|
| 1 | `pilot/pilot_eval.py`, `pilot/dict_fullscale.py` | 후보 방법 ①(사전 기반) 사전 검토 | |
| 2 | `labeling/build_labeling_set.py` | 검증셋 라벨링 파일 (본 300리뷰 + 부정 보강 70리뷰) | 사람 라벨링 → `input/sentiment/labeling/` |
| 3 | `calibration/build_split.py` | 보정셋(CAL)·채점셋(TEST) 배정 | |
| 4 | `labeling/finalize.py` | 확정 검증셋 → `output/sentiment/labeling/확정/` | |
| 5 | `labeling/build_relabel.py` → `labeling/kappa.py` | 50문장 재라벨, Cohen's κ | 사람 재라벨 → `input/sentiment/labeling/재라벨/` |
| 6 | `evaluation/rating_vs_label.py` | 별점 × 사람 라벨 교차표 | |
| 7 | `pilot/model2_smoke.py` → `calibration/decide_threshold.py` → `evaluation/run_model2.py` | 후보 방법 ②(사전학습 모델). torch 필요 | |
| 8 | `llm_labeling/build_chunks.py` → `llm_labeling/check_output.py` | 후보 방법 ③(LLM) 입력 묶음, 출력 형식 점검 | ChatGPT 2회 실행 → `input/sentiment/llm_labeling/llm_runs/run1`, `run2` |
| 9 | `evaluation/run_llm3.py`, `evaluation/재현성.py` | ③ 채점, ②③ 비교, 실행 간 재현성 | |
| 10 | `fullscale/build_fullscale.py` → `fullscale/check_fullscale.py` → `fullscale/merge_fullscale.py` | 나머지 4,987문장에 ③ 적용, 사람 라벨과 병합 | ChatGPT → `input/sentiment/fullscale/llm_runs/run1` |
| 11 | `mixed_audit/build_mixed_audit.py` | 모델이 `혼합`으로 답한 267건 중 40건 층화 표본 | 사람 판정 → `input/sentiment/mixed_audit/` |
| 12 | `mixed_final_review/build_40_split_boundaries.py` → `finalize_40.py` | 40건 중 분할 건의 자를 지점 초벌, 확정본 정리 | 사람 확정 → `input/sentiment/mixed_final_review/혼합40_분할경계_확정용.xlsx` |
| 13 | `mixed_final_review/build_final_review.py` → `apply_gpt_draft.py` → `relayout_review.py` → `fix_split_fragments.py` → `check_review.py` | 남은 227건 검토표 작업본에 GPT 초벌 반영, 진행 점검 | GPT 초벌 → `input/sentiment/mixed_final_review/gpt_초벌_판정.csv`, 사람 검토 → `혼합227_최종검토용.xlsx` |
| 14 | `mixed_final_review/merge_final.py` | 267건 확정 반영 → `output/sentiment/final/` | |

- 묶음 크기 150문장 조건 실험은 `llm_labeling/build_chunks.py 150 chunks_150`, `llm_labeling/check_output.py run_150`, `evaluation/재현성.py run1 run_150`입니다.
- 문장 분리는 파이프라인 전체가 `src/sentiment/textsplit.py` 하나만 씁니다.
- 단계마다 무엇을 왜 그렇게 했는지는 각 스크립트 첫머리 설명에 있습니다. 방법 선정의 근거 문서(라벨링 지침서, 임계값 사전 등록, 채점 규칙, LLM 실행 기록, 방법 조사)는 [docs/sentiment/](docs/sentiment/)에 있습니다.

#### 절차의 기록으로 남긴 스크립트

아래 스크립트는 사람이 채울 양식이나 작업본을 만든 **절차의 기록**입니다. 결과 재현을 위해 실행할 필요는 없습니다. 옛 구조에서는 다시 실행하면 사람이 채운 확정본을 덮어썼지만, 지금은 `output/`에 새 양식을 만들 뿐 `input/`의 확정본은 건드리지 않습니다.

| 스크립트 (`src/sentiment/…`) | 새로 만드는 것 (`output/sentiment/…`) | 사람이 채운 확정본 (`input/sentiment/…`) |
|---|---|---|
| `labeling/build_labeling_set.py` | `labeling/` 라벨링 양식 | `labeling/` |
| `labeling/build_relabel.py` | `labeling/재라벨/` | `labeling/재라벨/` |
| `mixed_audit/build_mixed_audit.py` | `mixed_audit/` | `mixed_audit/` |
| `mixed_final_review/build_40_split_boundaries.py` | `mixed_final_review/혼합40_분할경계_확정용.xlsx` | `mixed_final_review/혼합40_분할경계_확정용.xlsx` |
| `mixed_final_review/build_final_review.py`, `apply_gpt_draft.py`, `relayout_review.py`, `fix_split_fragments.py` | `mixed_final_review/혼합227_최종검토용.xlsx` 작업본 | `mixed_final_review/혼합227_최종검토용.xlsx` |

- `build_labeling_set.py`를 지금 실행하면 본 검증셋이 539문장이 아니라 533문장이 됩니다. 검증셋을 만든 뒤 문장 분리 규칙이 바뀌어 문장부호만 남은 조각 6개가 앞 문장에 붙기 때문입니다. 사람이 판정한 확정 라벨은 539문장 체계의 `unit_id`를 쓰므로 `input/`의 보존본을 그대로 씁니다.
- 검토표 작업본을 만드는 스크립트는 덮어쓰기 전에 지금 파일을 `output/sentiment/mixed_final_review/백업/{시각}/`에 복사해 둡니다(git 제외).

### 4. 연관관계 분석 (보고서 4장) — `src/association/`

```bash
python src/association/analyze_association.py --no-llm --by-place --min-place-transactions 50
```

- 키워드 분석의 토큰 파일을 읽어 `output/association/연관관계_분석결과.csv`를 만듭니다. 보고서 결과는 위 설정으로 만들었습니다.
- `--no-llm`을 빼면 API로 동의어를 통합하고 키워드에 요인 카테고리를 붙인 뒤 계산합니다.

### 5. 만족·불만 요인 분석 (보고서 5장) — `src/satisfaction/`

```bash
python src/satisfaction/analyze_satisfaction.py --dry-run    # API 없이 결과 파일의 틀을 만든다
python src/satisfaction/annotation/merge.py                  # 판정(annotations.jsonl)을 검증해 채운다
python src/satisfaction/plot_seasonal_sentiment.py           # 계절별 긍정·중립·부정 리뷰 비율
python src/satisfaction/plot_seasonal_factors.py             # 주요 3개소 계절별 대표 요인
```

- 출력은 `output/satisfaction/`의 `리뷰별_만족불만요인_분석결과.csv`와 그림 4장입니다.
- 리뷰 3,208건의 판정은 Claude Code 대화에서 만들어 `input/satisfaction/annotations.jsonl`에 쌓았습니다. 판정 대상 리뷰는 `pending.jsonl`에 있습니다.
- 판정을 새로 더할 때는 `annotation/show.py <시작번호> <건수>`로 리뷰를 보고, 판정을 `input/satisfaction/batch.jsonl`에 적은 뒤 `annotation/add.py`로 덧붙이고 `annotation/merge.py --check`로 검증합니다.
- API로 판정하려면 `--dry-run` 없이 실행합니다. 중단되면 다시 실행하면 이어서 합니다.

### 6. 시계열 분석 (보고서 6장) — `src/timeseries/`

보고서 6.2~6.6의 수치와 그림은 아래 순서로 만듭니다. 각 스크립트는 저장하기 전에 자체 검사 결과를 `[PASS]`/`[FAIL]`로 출력하고, 실패하면 그 자리에서 멈춥니다.

```bash
python src/timeseries/tierA_seasonal_review_analysis.py          # T-2 Tier A 3곳 계절별 리뷰 수
python src/timeseries/tierA_seasonal_sentiment_analysis.py       # T-3 계절별 감성 분포
python src/timeseries/tierA_seasonal_sentiment_platform_check.py # T-3 보조: 구글·네이버 구성 점검
python src/timeseries/cheese_festival_review_analysis.py         # T-5 치즈축제 전·중·후 리뷰 수
python src/timeseries/cheese_festival_sentiment_analysis.py      # T-6 치즈축제 전·중·후 감성
python src/timeseries/timeseries_integration_check.py            # T-8 결과 통합 점검
```

| 스크립트 | 역할 | 언제 실행하나 |
|---|---|---|
| `t4_2_timeline_matching.py` → `cheese_festival_window_setup.py` | T4-2 축제·운영 일정(외부 공식자료 기록), T-4 축제 전·중·후 구간 | 분석 구간을 바꿀 때만. 결과 CSV가 이미 있습니다 |
| `annual_trend_decomposition.py` | 연도별 리뷰 추이 분해 | 결과 CSV를 T-2가 교차검증에 읽으므로 지우지 않습니다 |
| `timeseries_input_audit.py` | T-1 입력 점검 (행 수, `reviewId` 결합률, 날짜) | 점검용. 감성 중간본(`output/sentiment/fullscale/전수_문장라벨.csv`)도 읽습니다 |
| `monthly_seasonality_analysis.py`, `top3_monthly_trend.py` | 월별 계절성, 상위 3곳 월별 추이 | 보고서 본문에 쓰지 않은 참고 분석. `top3_monthly_trend.py`만 2026년을 포함합니다 |

T-8 점검 결과는 [docs/시계열_분석_통합점검.md](docs/시계열_분석_통합점검.md)에 있습니다.

### 7. 추가 관광지 2개소 — `src/new_sites/`

성수산과 오수의견국민여가캠핑장의 네이버 리뷰를 34개소와 같은 방법으로 분석합니다. 34개소 코드를 고치지 않고 불러 씁니다. 구글 지도에는 두 곳의 리뷰가 없어 네이버만 씁니다.

```bash
python src/new_sites/collect_naver.py       # 수집 → output/collect/naver/
python src/new_sites/run_all.py --no-api    # API 없이 할 수 있는 단계만
python src/new_sites/run_all.py             # 전 과정 (번역·감성·요인에 API 사용)
```

단계별 명령, 사람이 할 일(실명 확인, 감성 검토표 작성), 시험 실행 방법은 [docs/new_sites.md](docs/new_sites.md)에 있습니다.

## 재현 확인 (2026-11-05)

폴더 구조를 바꾼 뒤, 옛 구조와 새 구조에서 스크립트를 하나씩 따로 실행해 결과를 대조했습니다. 확인은 Linux에서 했으므로 줄바꿈(CRLF/LF)은 무시하고 비교했습니다.

| 단계 | 결과 |
|---|---|
| 시계열 | 모든 CSV가 커밋된 결과와 같습니다. `timeseries_input_inventory.csv`만 파일 경로 표기가 새 위치로 바뀌었습니다 |
| 감성 | 빠른 재현 두 명령으로 `final/`의 CSV 5개가 같게 나옵니다. md 파일은 실행 시각 줄만 다릅니다. 13번의 앞 네 스크립트를 이어서 실행하면 작업본의 GPT 초벌 열이 `input/`의 확정본과 같아지고, `분할조각_보정.csv`와 `gpt_초벌_양식.csv`도 커밋된 파일과 같습니다 |
| 연관관계 | 규칙과 수치는 같고 행 순서만 실행마다 다릅니다. 같은 점수인 규칙 사이의 순서가 파이썬 해시 시드에 따라 바뀌기 때문입니다 |
| 만족·불만 요인 | CSV가 같습니다 |
| 키워드 | 노트북으로 만든 기존 결과와 비교했습니다(Kiwi 0.23.2). 빈도·Trigram Top 20은 같습니다. 토큰 파일은 5,267행 중 3행이 다르고, Bigram은 160행 중 5행이 다릅니다. TF-IDF는 점수 차이가 0.001 미만이지만 20위에서 동점인 단어가 바뀌어 420개 중 30개가 다릅니다 |
| 추가 관광지 | 시험 실행(`--demo`)이 끝까지 돌아갑니다 |

- 그림(PNG)은 글꼴이 다른 환경에서 그려 바이트 비교는 하지 않았습니다. 그림에 쓰인 값은 위 CSV와 같습니다.
- `output/sentiment/pilot/dict_fullscale_result.txt`는 옛 구조에서도 다시 실행하면 커밋된 결과와 다릅니다(5,697문장 → 5,682문장). 이 결과를 만든 뒤 문장 분리 규칙이 바뀌었기 때문이며, 폴더 정리와는 관계없습니다.
- 커밋된 CSV는 Windows에서 만들어 줄바꿈이 CRLF입니다. macOS나 Linux에서 다시 만들면 줄바꿈만 달라 `git diff`에 모든 줄이 바뀐 것으로 보일 수 있습니다. 이때는 `git diff --ignore-cr-at-eol`로 비교합니다.

## 문서

| 문서 | 내용 |
|---|---|
| [docs/폴더_대응표.md](docs/폴더_대응표.md) | 옛 폴더의 파일이 옮겨 간 새 위치 |
| [docs/new_sites.md](docs/new_sites.md) | 추가 관광지 2개소 분석 |
| [docs/collect_google.md](docs/collect_google.md) | 구글 지도 리뷰 수집기 |
| [docs/sentiment/](docs/sentiment/) | 라벨링 지침서, 임계값 사전 등록, 채점 규칙, LLM 실행 기록, 방법 조사 |
| [docs/시계열_분석_통합점검.md](docs/시계열_분석_통합점검.md) | 시계열 T-8 교차검증 결과 |
| [docs/archive/](docs/archive/) | 제출 당시의 감성·시계열 README와 재현 안내, 키워드 Colab 노트북 |
| [docs/Branch.md](docs/Branch.md), [docs/Commit.md](docs/Commit.md) | 브랜치 규칙, 커밋 규칙 |

`docs/sentiment/`와 `docs/archive/`의 문서는 작성 당시 그대로 두었습니다(제출본 두 개에는 머리말만 덧붙임). 안에 적힌 경로는 옛 구조 기준이므로 새 위치는 폴더 대응표에서 찾습니다.

## 데이터 비식별 처리

공개 레포이므로 수집 데이터를 다음과 같이 가공했습니다. 분석 수치는 달라지지 않습니다.

- **리뷰 ID**: 플랫폼의 원본 `reviewId`를 모든 파일에서 동일한 가명(`RV00001` 형식)으로 바꿨습니다.
- **작성자 정보**: 닉네임, 계정 ID, 프로필 URL이 담긴 수집 원본은 포함하지 않습니다.
- **본문 속 개인 이름**: 현장 직원의 실명으로 확인된 표현을 `○○○`로 가렸습니다. 자유 텍스트를 패턴과 문맥으로 점검한 결과이므로 모든 개인정보의 제거를 보장하지는 않습니다.

수집 원본, API 키, 로그인 세션, 내부 보고서는 이 레포에 없습니다. 네이버 리뷰 수 그래프(`src/collect/naver_review_counts.py`)는 수집 원본이 필요하므로 수집기를 먼저 실행해야 합니다. 수집기를 실행하면 작성자 정보가 포함된 파일이 `output/collect/` 아래에 생기며, 이 파일들은 `.gitignore`로 제외됩니다.

## 라이선스와 리뷰 데이터

코드는 [MIT License](LICENSE)를 따릅니다. 리뷰 본문의 권리는 각 작성자와 플랫폼에 있으며 MIT License의 대상이 아닙니다. 연구 재현 목적으로만 사용해 주세요. 삭제가 필요한 내용이 있으면 Issue로 알려 주세요.
