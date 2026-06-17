# 포켓몬 챔피언스 헬퍼 — 실행 가이드

## 사전 요구사항

- Python 3.11 이상
- 인터넷 연결 (데이터 수집 단계)

---

## 1단계 — 패키지 설치

```
pip install -r requirements.txt
```

---

## 2단계 — Smogon 기본 데이터 수집

포켓몬 스탯/타입, 채용 세트, 타입 상성 데이터를 다운로드합니다.

```
python scripts/fetch_data.py
```

생성 파일:
- `data/pokemon.json` — 포켓몬 기본 스탯/타입
- `data/smogon_sets.json` — Smogon 채용 세트
- `data/type_chart.json` — 18×18 타입 상성 행렬
- `data/priority_moves.json` — 우선도 기술 목록

---

## 3단계 — 리플레이 수집

Smogon gen9ou 고레이팅 배틀 리플레이 3,000개를 다운로드합니다.  
시간이 오래 걸립니다 (약 30분~1시간). 중단 후 재실행하면 이어받습니다.

```
python scripts/fetch_replays.py
```

생성 파일:
- `data/replays/*.log` — 리플레이 로그 파일들

---

## 4단계 — 리플레이 파싱

다운로드한 로그에서 팀 구성과 승패를 추출해 CSV로 저장합니다.

```
python scripts/parse_replays.py
```

생성 파일:
- `data/replay_dataset.csv` — 팀 구성 + 승패 데이터

---

## 5단계 — 전체 모델 학습

SVD / PCA / Naive Bayes 세트 분류기 / XGBoost 승리 예측 모델을 순서대로 학습합니다.  
Optuna 베이지안 최적화 (80 trials) 포함, 약 10~30분 소요됩니다.

```
python scripts/train_models.py
```

생성 파일:
- `data/svd_U.npy`, `data/svd_S.npy`, `data/svd_Vt.npy` — SVD 임베딩
- `data/pca_embeddings.npy` — PCA 임베딩
- `data/embeddings_meta.json` — 임베딩 메타데이터
- `data/set_classifier.pkl` — Naive Bayes 세트 분류기
- `data/win_predictor.pkl` — XGBoost 승리 예측 모델

---

## 6단계 — 성능 평가 시각화

```
python scripts/evaluate.py
```

그래프 창 2개가 뜹니다:

**Figure 1 — ML 기반 모델**
- SVD 특이값 분포
- SVD k값별 복원 오차
- PCA Scree Plot
- 세트 분류기 현황

**Figure 2 — 승리 예측 모델**
- ROC Curve (Train / Val / Test)
- 지표 비교 (AUC / F1 / Accuracy) + 과적합 진단
- Feature Importance Top 15
- Calibration Curve

---

## 7단계 — 앱 실행

```
python main.py
```

> 스위치 캡쳐보드 없이도 탭 1~6 (스피드/대미지/타입/그리드/세트조회/배틀로그) 전부 사용 가능합니다.

---

## Phase 2 — 실시간 오버레이 (캡쳐보드 필요)

### 사전 준비

**캡쳐보드**: 애니포트 AP-HDC4K (MS2109 칩)  
- USB 연결 후 OpenCV 인덱스 0번으로 자동 인식
- 해상도: 640×480

**GPU 가속 설치** (RTX 시리즈 권장, 없으면 CPU로도 동작):

```
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

> 관리자 권한 오류 시 `--user` 옵션 추가

GPU 인식 확인:
```
python -c "import torch; print(torch.cuda.is_available())"
```

---

### 오버레이 실행

```
python overlay_main.py
```

**키 조작**

| 키 | 기능 |
|----|------|
| Q | 종료 |
| D | ROI 박스 시각화 토글 (좌표 확인용) |
| C | ROI 크롭 이미지 저장 (좌표 캘리브레이션용) |

---

### 오버레이 표시 정보

**배틀 화면**
- 내 포켓몬 / 상대 포켓몬 이름 + 타입 배지
- 타입 상성 배율 (최고 공격 타입)
- 스피드 비교 (내 SPE vs 상대 SPE)
- 내 현재 HP

**선출 화면**
- 내 팀 / 상대 팀 포켓몬 이름 + 타입

---

### 현재 완료 현황 (2026-06-16 기준)

| 항목 | 상태 |
|------|------|
| 데이터 수집 (PokeAPI 275마리) | ✅ 완료 |
| 리플레이 수집 3,970개 | ✅ 완료 |
| ML 모델 학습 (XGBoost + Optuna) | ✅ 완료 |
| GUI 전체 탭 (스피드/대미지/타입/그리드/세트/로그) | ✅ 완료 |
| 캡쳐보드 연결 (index=0, CAP_DSHOW) | ✅ 완료 |
| 실시간 오버레이 실행 | ✅ 완료 |
| OCR ROI 좌표 캘리브레이션 | 🔧 진행 중 |
| GPU EasyOCR | 🔧 진행 중 |

---

## 단계별 의존 관계

```
fetch_data.py
    └─→ train_models.py (SVD / PCA / 세트 분류기)
            └─→ evaluate.py (Figure 1)

fetch_replays.py
    └─→ parse_replays.py
            └─→ train_models.py (승리 예측 모델)
                    └─→ evaluate.py (Figure 2)

main.py  ←  모든 단계 완료 후 실행 권장
            (데이터 없어도 실행은 되지만 ML 기능 비활성)
```

---

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError` | 패키지 미설치 | `pip install -r requirements.txt` |
| `pokemon.json 없음` | 2단계 미실행 | `python scripts/fetch_data.py` |
| `replay_dataset.csv 없음` | 3~4단계 미실행 | `fetch_replays.py` → `parse_replays.py` |
| `win_predictor.pkl 없음` | 5단계 미실행 | `python scripts/train_models.py` |
| 그래프 한글 깨짐 | 폰트 없음 | 맑은 고딕(Malgun Gothic) 설치 필요 |
