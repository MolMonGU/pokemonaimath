# 포켓몬 챔피언스 헬퍼 툴 — 설계 문서

## 프로젝트 개요

Nintendo Switch에서 포켓몬 챔피언스 싱글 배틀 중 실시간으로 분석 정보를 노트북 화면에 표시하는 도우미 툴.
선형대수 기반 행렬 연산과 ML 모델을 결합해 규칙 기반으로는 불가능한 확률적 추론을 제공한다.

- 스위치 → USB 캡쳐보드 → 노트북 (분석 화면 별도 표시)
- 플레이는 스위치로, 분석은 노트북으로 동시에 진행
- 캡쳐보드 없이도 스크린샷 이미지로 개발/테스트 가능

---

## 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| 화면 캡쳐 | `opencv-python` |
| 텍스트 인식 | `easyocr` |
| GUI | `PyQt6` |
| 행렬 연산 (SVD, PCA) | `numpy`, `scipy.linalg` |
| ML 모델 | `scikit-learn` |
| 딥러닝 fine-tuning | `torch` (Phase 2) |
| 데이터 처리 | `pandas` |
| 스크래핑 | `requests`, `beautifulsoup4` |
| 시각화 | `matplotlib` |

---

## 전체 아키텍처

```
[Nintendo Switch]
      │ HDMI
[USB 캡쳐보드]
      │ UVC
[vision/capture.py] ── OpenCV 프레임 읽기
      │
[vision/ocr.py] ─────── EasyOCR + fine-tuned 모델로 포켓몬 이름 인식
      │
[core/] ─────────────── 수식 기반 계산 (스피드, 대미지, 타입)
      │
[ml/] ───────────────── SVD/PCA 임베딩 + 분류기/추천 모델
      │
[gui/] ──────────────── PyQt6 실시간 분석 창
```

---

## 데이터 파이프라인 (ML 핵심)

ML 성능은 이 파이프라인의 품질에 달려 있다.

```
Smogon 월별 통계 + 리플레이 데이터
            ↓
  행렬 A 구성 (n포켓몬 × m기술, 값=채용률)
  행렬 B 구성 (n포켓몬 × 24특성, 값=스탯+타입벡터)
            ↓
     ┌──────┴──────┐
    SVD           PCA
     │              │
  포켓몬·기술    차원 축소된
  잠재 벡터     포켓몬 임베딩
     └──────┬──────┘
       통합 특성 벡터
            ↓
   ┌────────┴────────┐
세트 분류기       선출 추천 모델
(Naive Bayes)  (Matrix Factorization)
```

---

## 선형대수 적용

### SVD — 포켓몬×기술 행렬 분해

Smogon 채용률 데이터로 행렬 A를 구성하고 SVD 분해한다.

```
행렬 A  (n포켓몬 × m기술, 값=채용률 0~1)

        기합구슬  냉동빔  불꽃세례  지진  ...
뮤츠      0.72   0.65    0.41   0.02
한카리아스  0.05   0.12    0.02   0.89
리자몽     0.38   0.44    0.71   0.08

↓  A = U × Σ × Vᵀ  (scipy.linalg.svds, k=50)

U  (n × k): 포켓몬 잠재 벡터 — "역할 임베딩"
Σ  (k × k): 중요도 대각행렬
Vᵀ (k × m): 기술 잠재 벡터 — "기술 역할 임베딩"
```

**활용**
- 배틀 중 기술 1~2개 관찰 → 불완전 행 복원 → 나머지 기술 예측
- 기술 간 유사도: V의 열벡터 코사인 유사도
- 데이터 없는 신규 포켓몬: U 공간에서 최근접 이웃 참조

---

### PCA — 포켓몬 특성 차원 축소

각 포켓몬의 스탯 + 타입 특성 행렬을 저차원으로 압축한다.

```
행렬 B  (n포켓몬 × 24특성)
특성 구성: [HP, 공격, 방어, 특공, 특방, 스피드] (6차원)
         + [타입1 원핫 18차원]
         = 24차원

↓  PCA (sklearn.decomposition.PCA, n_components=10)

B_reduced = B @ P  (n × 10)
주성분 P: 분산을 최대로 설명하는 방향벡터들
```

**활용**
- 포켓몬 역할 클러스터링 (공격형/방어형/서포터 등)
- 선출 추천 모델의 입력 특성으로 사용
- 2D 투영으로 파티 구성 시각화

---

### 타입 상성 행렬 연산 (6×6 그리드 내부)

```python
# T: 18×18 타입 상성 행렬 (numpy)
# p_atk: 내 포켓몬 공격 타입 원핫 벡터 (18차원)
# p_def: 상대 포켓몬 방어 타입 원핫 벡터 (18차원)

# 내 포켓몬이 상대에게 줄 수 있는 최고 배율
coverage_score = max(T @ p_atk * p_def)

# 파티 전체 커버리지: 6마리 벡터의 element-wise max
party_coverage = np.max([T @ p for p in my_party_type_vecs], axis=0)
```

---

## ML 모델 상세 설계

### ① 세트 분류기 (배틀 로그 탭)

**목적**: 관찰된 기술 1~2개로 상대가 어떤 세트인지 확률 추론
**규칙 기반 대비 개선**: 단순 필터링 → 다변수 동시 고려 확률적 추론

**모델**: Multinomial Naive Bayes

```
학습 데이터: Smogon 채용 세트 (포켓몬당 상위 세트들)
입력 X: [SVD 포켓몬 임베딩(k차원)] + [관찰된 기술 원핫(m차원)]
출력 y: 세트 클래스 (세트1, 세트2, 세트3 ...)

P(세트S | 관찰기술) ∝ P(기술 | S) × P(S)
                      ↑ Smogon 채용률로 추정
```

**선형대수 연결**: 로그 확률 = feature_vector @ weight_matrix + bias

```
배틀 중 출력 예시:
  관찰: 화끈돼지, 오버히트 사용
  → 구애안경 특공형:  63%
  → 생명의구슬 혼합형: 27%
  → 구애스카프형:     10%
```

---

### ② 선출 추천 모델 (Phase 2)

**목적**: 내 파티 + 상대 파티 → 최적 선출 3마리 확률 추천
**규칙 기반 대비 개선**: 타입 점수 단순 합산 → 실제 고레이팅 플레이어 데이터 학습

**모델**: SVD 기반 Matrix Factorization

```
학습 데이터: Smogon 고레이팅 리플레이
행렬 R: (파티 상황 임베딩) × (선출한 포켓몬)
→ R ≈ U_situation × Σ × Vᵀ_pokemon

입력: 내 파티 PCA벡터 × 6 + 상대 파티 PCA벡터 × 6
출력: 포켓몬별 선출 확률 → 상위 3개 추천
```

**메타 반영**: 학습 데이터 자체에 현재 메타(채용률, 시너지)가 녹아 있어
단순 타입 계산으로는 포착 못하는 판단 가능

---

### ③ OCR 정확도 개선 (Phase 2)

**목적**: 별명 포켓몬, 작은 폰트, 압축 노이즈에서 인식 오류 감소
**모델**: EasyOCR 기반 → 게임 화면 특화 fine-tuning

```
기존: 범용 EasyOCR (다국어 학습)
개선: 포켓몬 이름 데이터셋으로 마지막 레이어 fine-tune
      학습 데이터: 게임 화면 스크린샷 + 포켓몬 이름 라벨
```

**선형대수 연결**: CNN = 행렬 컨볼루션 연산의 연속

---

## 기능 목록

### Phase 1 — 수식 기반 (캡쳐보드 없이 개발 가능)

> 이 구간은 수식이 고정돼 있어 ML 불필요. 오차 없는 계산이 목표.

#### 1. 스피드 티어 계산기  `🤖 계산 자동 / 🖱 조건 수동`

- 포켓몬 + 노력치 + 성격 입력 → 실수치 계산
- 해당 스피드로 **선제 가능 목록** / **후제 목록** 표시
- 역방향: "이 포켓몬을 넘으려면 최소 몇 EV?" 계산

| 조건 | 배율 |
|------|------|
| 구애스카프 | × 1.5 |
| 쾌청/비/모래/눈 + 날씨특성 | × 2.0 |
| 랭크 +n | × (2+n)/2 |
| 랭크 -n | × 2/(2+n) |
| 마비 | × 0.5 |

#### 2. 타입 상성 계산기  `🤖 완전 자동 (numpy 행렬 연산)`

- 18×18 타입 상성 행렬 T로 내 파티/상대 파티 커버리지 계산
- 파티 전체 약점 분포, 타점 분석

#### 3. 대미지 계산기  `🤖 계산 자동 / 🖱 랭크·아이템 수동`

- 공식 데미지 수식 + 공격/방어 랭크 독립 적용
- 최소/최대/평균 범위, 1타 확률 표시

#### 4. HP 임계점 계산  `🤖 완전 자동`

- 상대 HP% 입력 → 기술별 처치 가능 확률 즉시 표시
- 역방향: "몇 % 이하면 확정 처치?" 계산

#### 5. 우선도 기술 시나리오  `🤖 완전 자동`

- 트릭룸 여부, 선제기 우선도 처리
- 후제 상황에서 선제기 사용 시나리오 자동 판단

#### 6. 상대 세트 조회  `🤖 인식 자동 / 🖱 확정 수동`

- Smogon 상위 채용 세트 표시 + 운영 방식 요약

### Phase 1.5 — ML 추론 레이어

> 규칙 기반으로 불가능한 확률적 판단. SVD/PCA 임베딩이 입력으로 사용됨.

#### 7. 세트 분류기  `🤖 ML 자동 추론`

- SVD 임베딩 + 관찰 기술 → Naive Bayes → 세트별 확률 %
- 기술 1개 관찰 후부터 점진적으로 확률 업데이트

#### 8. 6×6 유불리 그리드  `🤖 행렬 연산 자동`

- 타입 상성 행렬 × 파티 벡터 행렬로 전체 매칭 스코어 계산
- 색상 코딩: 🟢 유리 / 🔴 불리 / 🟡 중립
- 클릭 시 해당 매칭 대미지 계산으로 이동

```
예시:
         [뮤츠] [리자몽] [가이오스]
[내 A]    🟢      🔴       🟢
[내 B]    🟡      🟢       🔴
[내 C]    🔴      🟢       🟢
```

#### 9. 배틀 로그 + 구애 추론  `🤖 추론 자동 / 🖱 기술 체크 수동`

- 관찰 기술 체크 → 세트 분류기 실시간 업데이트
- 같은 기술 2회 → 구애 아이템 플래그
- SVD 기반 잔여 기술 슬롯 후보 확률 표시

### Phase 2 — 화면 인식 + 선출 추천 (캡쳐보드 필요)

#### 10. 실시간 OCR 인식  `🤖 자동 / 🖱 오인식 보정`

- EasyOCR + fine-tuned 모델로 포켓몬 이름 인식
- 오인식 시 드롭다운 수동 보정

#### 11. 선출 추천  `🤖 ML 추천`

- SVD Matrix Factorization 모델
- 실제 고레이팅 리플레이 학습 → 메타 반영
- 추천 근거(점수 분해) 함께 표시 (블랙박스 X)

---

## 데이터 구조

### `data/pokemon.json` — 기본 스탯/타입
출처: Pokémon Showdown GitHub

```json
{
  "Mewtwo": {
    "name_ko": "뮤츠",
    "types": ["Psychic"],
    "base_stats": {"hp": 106, "atk": 110, "def": 90, "spa": 154, "spd": 90, "spe": 130},
    "abilities": ["Pressure", "Unnerve"],
    "weight": 122.0
  }
}
```

### `data/smogon_sets.json` — Smogon 채용 세트
출처: Smogon 월별 chaos JSON

```json
{
  "Mewtwo": {
    "tier": "Uber",
    "top_sets": [
      {
        "usage_pct": 38.2,
        "item": "Life Orb",
        "nature": "Timid",
        "evs": {"spa": 252, "spe": 252, "hp": 4},
        "moves": ["Psystrike", "Ice Beam", "Fire Blast", "Aura Sphere"],
        "ability": "Pressure"
      }
    ]
  }
}
```

### `data/move_matrix.npy` — 포켓몬×기술 채용률 행렬
numpy 배열로 저장. SVD 학습에 사용.

### `data/pokemon_embeddings.npy` — SVD/PCA 임베딩 결과
학습 완료 후 저장. 세트 분류기/추천 모델 입력.

### `data/type_chart.json` — 18×18 타입 상성 테이블
### `data/priority_moves.json` — 우선도별 기술 목록
### `data/playstyles.json` — 운영 방식 요약 (수동 작성)
### `data/speed_tiers.json` — 스피드 티어 인덱스 (사전 계산)

---

## 자동화 vs 수동 판단 기준

| 항목 | 방식 | 이유 |
|------|------|------|
| 스피드/대미지/타입 계산 | **완전 자동** | 수식 고정, 오차 없음 |
| 6×6 그리드 | **완전 자동** | numpy 행렬 연산 |
| 세트 분류 | **ML 자동** | 다변수 확률 추론 |
| 선출 추천 | **ML 자동** | 메타 학습 필요 |
| 포켓몬 이름 OCR | **반자동** | 오인식 시 수동 보정 |
| 랭크 변화 | **수동** | 배틀 중 빠르게 바뀜, 오인식 위험 |
| HP% | **수동** | 직접 입력이 정확 |
| 상대 아이템 확정 | **수동** | 노출 전까지 미확정 |
| 운영 방식 텍스트 | **수동 작성** | 신뢰도 위해 사람이 검수 |

---

## UX 설계 원칙

- **항상 위(Always-on-top)**: 게임 창 위에 항상 떠 있는 모드 (토글)
- **컴팩트 모드**: 현재 교전 정보만 보여주는 축소 뷰
- **다크 테마**: 기본값
- **파티 저장/불러오기**: 내 파티 EVs·기술을 JSON으로 저장
- **배틀 시작 버튼**: 배틀 로그 초기화 + 랭크 전부 0 리셋

---

## 모듈 구조

```
pokemon-champions-helper/
│
├── data/
│   ├── pokemon.json           # 기본 스탯/타입 (영문키, 한글명 포함)
│   ├── smogon_sets.json       # Smogon 채용 세트
│   ├── playstyles.json        # 운영 방식 요약 (수동)
│   ├── type_chart.json        # 18×18 타입 상성
│   ├── priority_moves.json    # 우선도별 기술
│   ├── speed_tiers.json       # 스피드 티어 인덱스
│   ├── move_matrix.npy        # 포켓몬×기술 행렬 (SVD 입력)
│   └── pokemon_embeddings.npy # SVD/PCA 임베딩 결과
│
├── scripts/
│   ├── fetch_data.py          # Smogon/Showdown 데이터 수집
│   └── train_models.py        # SVD 분해 + PCA + 모델 학습/저장
│
├── core/                      # 수식 기반 계산 (numpy 활용)
│   ├── type_calc.py           # 타입 상성 (행렬 연산)
│   ├── speed.py               # 스피드 계산 + 우선도
│   ├── damage.py              # 대미지 계산 + HP 임계점
│   ├── party.py               # 파티 분석 + 6×6 그리드
│   └── battle_log.py          # 배틀 로그 + 구애 추론
│
├── ml/                        # ML 모델
│   ├── embeddings.py          # SVD/PCA 임베딩 생성 및 로드
│   ├── set_classifier.py      # 세트 분류기 (Naive Bayes)
│   └── lead_recommender.py    # 선출 추천 (Matrix Factorization)
│
├── vision/
│   ├── capture.py             # 캡쳐보드 프레임 읽기
│   └── ocr.py                 # EasyOCR + fine-tuned 인식
│
├── gui/
│   ├── main_window.py         # 메인 창 (always-on-top, 컴팩트)
│   ├── grid_tab.py            # 6×6 그리드
│   ├── speed_tab.py           # 스피드 계산기
│   ├── damage_tab.py          # 대미지 + HP 임계점
│   ├── type_tab.py            # 타입 분석
│   ├── sets_tab.py            # 세트 조회 + 운영 방식
│   └── log_tab.py             # 배틀 로그 + ML 세트 추론
│
├── saves/my_teams/            # 내 파티 저장
├── tests/
│   ├── test_speed.py
│   ├── test_damage.py
│   ├── test_type_calc.py
│   ├── test_set_classifier.py
│   └── sample_screens/
│
├── main.py
└── requirements.txt
```

---

## 수식 레퍼런스

### 스피드 실수치

```
base   = floor((2 × base_spe + iv + floor(ev/4)) × lv / 100) + 5
stat   = floor(base × nature_mod)        # 1.1 / 1.0 / 0.9
ranked = floor(stat × (2+max(0,r)) / (2+max(0,-r)))   # r = rank
final  = ranked × 1.5(스카프) × 2.0(날씨특성) × 0.5(마비)
```

### 대미지 계산

```
raw    = floor(floor(floor(2×Lv/5+2) × power × atk_eff / def_eff / 50) + 2)
damage = raw × weather × crit × rand × stab × type × burn × other
rand   = 0.85 ~ 1.00  →  최소/최대 범위 계산
급소   = 공격 랭크 무시 + 방어 랭크 무시 + × 1.5

atk_eff = floor(atk × (2+max(0,atk_rank)) / (2+max(0,-atk_rank)))
def_eff = floor(def × (2+max(0,def_rank)) / (2+max(0,-def_rank)))
```

---

## 개발 단계

| 단계 | 내용 | 캡쳐보드 |
|------|------|:---:|
| 1 | 데이터 수집 (`fetch_data.py`) | X |
| 2 | SVD/PCA 학습 (`train_models.py`) | X |
| 3 | `core/` 계산 모듈 + 테스트 | X |
| 4 | `ml/` 세트 분류기 구현 | X |
| 5 | PyQt6 GUI 전체 탭 | X |
| 6 | Always-on-top + 컴팩트 모드 | X |
| 7 | OCR + 캡쳐보드 연동 | O |
| 8 | OCR fine-tuning | O |
| 9 | 선출 추천 모델 (리플레이 학습) | O |

---

## 테스트 전략

- **계산 모듈**: pytest 단위 테스트 (공식 수치와 대조)
- **ML 모델**: 학습/검증 분리, 세트 분류 정확도 측정
- **OCR**: `tests/sample_screens/` 스크린샷으로 인식률 측정
- **최종 통합**: 스위치 연결 후 실전 배틀 end-to-end 검증
