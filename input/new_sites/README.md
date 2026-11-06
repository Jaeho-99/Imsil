# input/new_sites — 추가 관광지 분석에서 사람과 Claude Code가 만든 입력

코드가 만들지 않는 파일만 둡니다. `src/new_sites/`의 코드는 이 폴더를 읽기만 합니다.
판정 파일은 결과 재현의 근거이므로 git에 올립니다. 같은 판정 파일로 코드를 돌리면 어느 PC에서나 같은 결과가 나옵니다.

| 파일 | 만드는 법 | 읽는 곳 | git |
|---|---|---|:-:|
| `claude_지시문/` | Claude Code에 주는 지시문 4개 (`감성_검증.md`, `감성_판정.md`, `요인.md`, `번역.md`). 판정 기준·읽을 파일·쓸 형식·점검 명령이 들어 있습니다 | Claude Code | ○ |
| `sentiment/검증_34개소/run1/`, `run2/` | Claude Code가 `감성_검증.md`대로 34개소 검증셋 12묶음을 판정해 씁니다. `실행기록.md` 포함 | `sentiment.py check`·`validate` | ○ |
| `sentiment/runs/run1/`, `run2/` | Claude Code가 `감성_판정.md`대로 추가 관광지 묶음을 판정해 씁니다. 두 run은 서로 다른 새 대화에서 합니다. `실행기록.md` 포함 | `sentiment.py check`·`review`·`merge` | ○ |
| `satisfaction/annotations.jsonl` | Claude Code가 `요인.md`대로 리뷰마다 한 줄씩 씁니다 | `satisfaction.py check`·`merge` | ○ |
| `번역결과.csv` | 외국어 리뷰가 있을 때만. Claude Code가 `번역.md`대로 씁니다 (열: `reviewId,원문,번역,방법`) | `preprocess.py` | ○ |
| `사람검토표.xlsx` | `sentiment.py review`가 만든 `output/new_sites/sentiment/사람검토표.xlsx`를 여기로 복사해 사람이 채웁니다 | `sentiment.py merge` | ○ |
| `비식별_치환목록.csv` | `preprocess.py`가 출력한 실명 후보 중 사람이 문맥을 보고 실명으로 확인한 표현을 적습니다. 열은 `find,replace`이고, `replace`를 비우면 `○○○`로 바꿉니다 | `build_dataset.py` | 제외 (실명이 그대로 들어 있음) |

실행 순서, Claude Code에 보낼 문장, 각 파일을 채우는 기준은 [docs/new_sites.md](../../docs/new_sites.md)에 있습니다.
