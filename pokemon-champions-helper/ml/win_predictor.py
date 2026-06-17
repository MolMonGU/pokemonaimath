"""
승리 예측 모델 — XGBoost + Optuna 베이지안 최적화

입력: 내 파티 6마리×24차원 + 상대 파티 6마리×24차원 + 차이 + 절댓값 차이 = 576차원
출력: 승리 확률 (0.0 ~ 1.0)
타깃: 실제 배틀 승패 (1=승, 0=패)

데이터 증강:
  리플레이 1개 → 2행 생성 (승자 관점 + 패자 관점)
  GroupKFold로 같은 리플레이가 다른 fold에 들어가지 않도록 처리

과적합 진단:
  Train AUC - Val AUC 격차 기준
  < 0.03  → 정상
  0.03~0.07 → 경미 (정규화 강화 권장)
  > 0.07  → 심각
"""

import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold, cross_val_score
from sklearn.metrics import (
    roc_auc_score, roc_curve, f1_score,
    accuracy_score, log_loss,
)
from sklearn.calibration import calibration_curve
import xgboost as xgb
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice",
    "Fighting","Poison","Ground","Flying","Psychic","Bug",
    "Rock","Ghost","Dragon","Dark","Steel","Fairy"
]
STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"]

POKE_FEATURE_NAMES = (
    [f"{slot}_{s}" for slot in ["my1","my2","my3","my4","my5","my6"] for s in STAT_KEYS] +
    [f"{slot}_type_{t}" for slot in ["my1","my2","my3","my4","my5","my6"] for t in TYPES]
)
OPP_FEATURE_NAMES = (
    [f"{slot}_{s}" for slot in ["opp1","opp2","opp3","opp4","opp5","opp6"] for s in STAT_KEYS] +
    [f"{slot}_type_{t}" for slot in ["opp1","opp2","opp3","opp4","opp5","opp6"] for t in TYPES]
)
DIFF_FEATURE_NAMES    = [f"diff_{i}"    for i in range(144)]
ABS_DIFF_FEATURE_NAMES = [f"absdiff_{i}" for i in range(144)]
FEATURE_NAMES = POKE_FEATURE_NAMES + OPP_FEATURE_NAMES + DIFF_FEATURE_NAMES + ABS_DIFF_FEATURE_NAMES
# 총 576개


class WinPredictor:

    def __init__(self):
        self.model: xgb.XGBClassifier | None = None
        self.best_params: dict = {}
        self.eval_results: dict = {}
        self._pokedex: dict = {}
        self._stat_max = np.ones(6, dtype=np.float32)
        self._poke_loaded = False
        self._last_train_groups = None

    # ── 포켓몬 데이터 로드 ────────────────────────────────────────────────────

    def _load_pokedex(self):
        if self._poke_loaded:
            return
        path = DATA_DIR / "pokemon.json"
        if path.exists():
            self._pokedex = json.loads(path.read_text(encoding="utf-8"))
        stats = []
        for entry in self._pokedex.values():
            bs = entry.get("base_stats", {})
            stats.append([bs.get(k, 0) for k in STAT_KEYS])
        if stats:
            arr = np.array(stats, dtype=np.float32)
            mx = arr.max(axis=0)
            self._stat_max = np.where(mx > 0, mx, 1.0)
        self._poke_loaded = True

    @staticmethod
    def _norm_name(name: str) -> str:
        return name.lower().replace("-","").replace(" ","").replace("'","")

    def _poke_vector(self, name: str) -> np.ndarray:
        """포켓몬 이름 → 24차원 [스탯6 정규화 | 타입 원핫18]"""
        key   = self._norm_name(name)
        entry = self._pokedex.get(key, {})
        if not entry:
            base  = self._norm_name(name.split("-")[0])
            entry = self._pokedex.get(base, {})

        vec = np.zeros(24, dtype=np.float32)
        bs  = entry.get("base_stats", {})
        for i, k in enumerate(STAT_KEYS):
            vec[i] = bs.get(k, 0) / self._stat_max[i]

        tidx = {t: i for i, t in enumerate(TYPES)}
        for t in entry.get("types", []):
            if t in tidx:
                vec[6 + tidx[t]] = 1.0
        return vec

    def _team_vector(self, team: list[str]) -> np.ndarray:
        """팀 6마리 → 각 포켓몬 24차원 concat → 144차원"""
        clean = [p for p in team if isinstance(p, str) and p.strip()][:6]
        vecs  = [self._poke_vector(p) for p in clean]
        while len(vecs) < 6:
            vecs.append(np.zeros(24, dtype=np.float32))
        return np.concatenate(vecs).astype(np.float32)

    # ── 데이터셋 구성 ────────────────────────────────────────────────────────

    def build_dataset(self, csv_path: Path | None = None):
        """replay_dataset.csv → X(n×576), y(n,), groups(n,)"""
        self._load_pokedex()
        path = csv_path or (DATA_DIR / "replay_dataset.csv")
        if not path.exists():
            raise FileNotFoundError(f"{path} 없음 — parse_replays.py 먼저 실행")

        df = pd.read_csv(path)
        print(f"  리플레이 {len(df)}개 로드")

        p1_cols = [f"p1_t{i}" for i in range(1, 7)]
        p2_cols = [f"p2_t{i}" for i in range(1, 7)]
        X_rows, y_list, groups = [], [], []

        for gid, row in enumerate(df.itertuples(index=False)):
            p1_team = [getattr(row, c) for c in p1_cols]
            p2_team = [getattr(row, c) for c in p2_cols]
            winner  = row.winner

            v1 = self._team_vector(p1_team)
            v2 = self._team_vector(p2_team)

            X_rows.append(np.concatenate([v1, v2, v1 - v2, np.abs(v1 - v2)]))
            y_list.append(1 if winner == "p1" else 0)
            groups.append(gid)

            X_rows.append(np.concatenate([v2, v1, v2 - v1, np.abs(v2 - v1)]))
            y_list.append(1 if winner == "p2" else 0)
            groups.append(gid)

        X      = np.array(X_rows, dtype=np.float32)
        y      = np.array(y_list, dtype=np.int32)
        groups = np.array(groups, dtype=np.int32)
        print(f"  특성 행렬: {X.shape}  승={y.sum()}  패={len(y)-y.sum()}")
        return X, y, groups

    # ── Train / Val / Test 분리 ───────────────────────────────────────────────

    def split(self, X, y, groups):
        """70 / 15 / 15 — Group 단위 분리"""
        unique_g = np.unique(groups)
        rng = np.random.default_rng(42)
        rng.shuffle(unique_g)

        n     = len(unique_g)
        n_tr  = int(n * 0.70)
        n_val = int(n * 0.15)

        train_g = set(unique_g[:n_tr])
        val_g   = set(unique_g[n_tr:n_tr + n_val])
        test_g  = set(unique_g[n_tr + n_val:])

        def mask(g_set):
            return np.array([g in g_set for g in groups])

        train_mask = mask(train_g)
        val_mask   = mask(val_g)
        test_mask  = mask(test_g)

        self._last_train_groups = groups[train_mask]

        Xtr, ytr = X[train_mask], y[train_mask]
        Xv,  yv  = X[val_mask],   y[val_mask]
        Xte, yte = X[test_mask],  y[test_mask]

        print(f"  Train {len(ytr)} / Val {len(yv)} / Test {len(yte)}")
        return Xtr, ytr, Xv, yv, Xte, yte

    # ── Optuna 베이지안 최적화 ────────────────────────────────────────────────

    def tune(self, X_train, y_train, n_trials: int = 80) -> dict:
        print(f"  Optuna 탐색: {n_trials} trials, 5-fold GroupCV ...")
        cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
        cv_groups = self._last_train_groups
        if cv_groups is None:
            raise RuntimeError("split()을 먼저 호출해야 합니다.")

        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators":     trial.suggest_int("n_estimators", 80, 250),
                "max_depth":        trial.suggest_int("max_depth", 2, 5),
                "learning_rate":    trial.suggest_float("learning_rate", 0.03, 0.15, log=True),
                "subsample":        trial.suggest_float("subsample", 0.60, 0.95),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.50, 0.95),
                "reg_alpha":        trial.suggest_float("reg_alpha", 1e-4, 3.0, log=True),
                "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 10.0, log=True),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 8),
                "gamma":            trial.suggest_float("gamma", 0.0, 2.0),
                "eval_metric": "auc", "verbosity": 0, "random_state": 42,
            }
            train_aucs, val_aucs, val_lls = [], [], []

            for fold_idx, (tr_idx, va_idx) in enumerate(
                    cv.split(X_train, y_train, groups=cv_groups)):
                model = xgb.XGBClassifier(**params)
                model.fit(X_train[tr_idx], y_train[tr_idx])
                tr_p = model.predict_proba(X_train[tr_idx])[:, 1]
                va_p = model.predict_proba(X_train[va_idx])[:, 1]
                train_aucs.append(roc_auc_score(y_train[tr_idx], tr_p))
                val_aucs.append(roc_auc_score(y_train[va_idx], va_p))
                val_lls.append(log_loss(y_train[va_idx], va_p))

                gap   = max(0.0, float(np.mean(train_aucs)) - float(np.mean(val_aucs)))
                score = float(np.mean(val_aucs)) - 0.6 * gap - 0.03 * float(np.mean(val_lls))
                trial.report(score, step=fold_idx)
                if trial.should_prune():
                    raise optuna.exceptions.TrialPruned()

            gap   = max(0.0, float(np.mean(train_aucs)) - float(np.mean(val_aucs)))
            score = float(np.mean(val_aucs)) - 0.6 * gap - 0.03 * float(np.mean(val_lls))
            if gap > 0.08:
                score -= 0.12
            elif gap > 0.05:
                score -= 0.05

            trial.set_user_attr("mean_train_auc", float(np.mean(train_aucs)))
            trial.set_user_attr("mean_val_auc",   float(np.mean(val_aucs)))
            trial.set_user_attr("gap", gap)
            return float(score)

        study = optuna.create_study(
            direction="maximize",
            pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1),
        )
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        self.best_params = study.best_params
        pruned = sum(1 for t in study.trials if t.state == optuna.trial.TrialState.PRUNED)
        print(f"  최적 CV AUC : {study.best_value:.4f}")
        print(f"  pruned trials: {pruned}/{n_trials}")
        print(f"  최적 파라미터: {self.best_params}")
        return self.best_params

    # ── 최종 학습 ────────────────────────────────────────────────────────────

    def train(self, X_train, y_train, X_val, y_val, params: dict | None = None):
        p = {**(params or self.best_params),
             "verbosity": 0, "random_state": 42, "eval_metric": "auc"}
        p.pop("n_estimators", None)

        self.model = xgb.XGBClassifier(**p, n_estimators=1000,
                                        early_stopping_rounds=50)
        self.model.fit(X_train, y_train,
                       eval_set=[(X_val, y_val)], verbose=False)
        print(f"  학습 완료 (best_iteration={self.model.best_iteration})")

    # ── 성능 평가 ────────────────────────────────────────────────────────────

    def evaluate_all(self, X_train, y_train,
                     X_val, y_val, X_test, y_test) -> dict:
        def _calc(X, y, label):
            proba = self.model.predict_proba(X)[:, 1]
            pred  = (proba >= 0.5).astype(int)
            fpr, tpr, _ = roc_curve(y, proba)
            return {
                f"{label}_auc":     round(roc_auc_score(y, proba), 4),
                f"{label}_f1":      round(f1_score(y, pred),        4),
                f"{label}_acc":     round(accuracy_score(y, pred),  4),
                f"{label}_logloss": round(log_loss(y, proba),       4),
                f"{label}_proba":   proba.tolist(),
                f"{label}_y":       y.tolist(),
                f"{label}_fpr":     fpr.tolist(),
                f"{label}_tpr":     tpr.tolist(),
            }

        res: dict = {}
        res.update(_calc(X_train, y_train, "train"))
        res.update(_calc(X_val,   y_val,   "val"))
        res.update(_calc(X_test,  y_test,  "test"))

        gap = res["train_auc"] - res["val_auc"]
        if gap < 0.03:
            status = f"정상 (gap={gap:.3f})"
        elif gap < 0.07:
            status = f"경미한 과적합 (gap={gap:.3f})"
        else:
            status = f"심각한 과적합 (gap={gap:.3f})"

        frac_pos, mean_pred = calibration_curve(
            y_test, res["test_proba"], n_bins=10, strategy="uniform"
        )
        res["calib_frac_pos"]   = frac_pos.tolist()
        res["calib_mean_pred"]  = mean_pred.tolist()
        res["feature_names"]    = FEATURE_NAMES
        res["feature_importance"] = self.model.feature_importances_.tolist()
        res["overfit_gap"]      = round(gap, 4)
        res["overfit_status"]   = status
        res["best_params"]      = self.best_params
        self.eval_results = res

        print(f"\n  ── 성능 평가 결과 ──")
        for split in ["train", "val", "test"]:
            print(f"  {split:5s}  AUC={res[f'{split}_auc']:.4f}  "
                  f"F1={res[f'{split}_f1']:.4f}  "
                  f"Acc={res[f'{split}_acc']:.4f}  "
                  f"LogLoss={res[f'{split}_logloss']:.4f}")
        print(f"  과적합: {status}")
        return res

    # ── 추론 ────────────────────────────────────────────────────────────────

    def predict_win_prob(self, my_team: list[str],
                         opp_team: list[str]) -> float:
        """내 팀 + 상대 팀 → 승리 확률 (팀이 6마리 미만이면 0벡터로 패딩)"""
        self._load_pokedex()
        my_team  = list(my_team)  + [''] * max(0, 6 - len(my_team))
        opp_team = list(opp_team) + [''] * max(0, 6 - len(opp_team))

        v1 = self._team_vector(my_team)
        v2 = self._team_vector(opp_team)
        x  = np.concatenate([v1, v2, v1 - v2, np.abs(v1 - v2)]).reshape(1, -1)

        # pkl과 현재 코드의 feature 수 불일치 자동 보정
        expected = self.model.n_features_in_
        if x.shape[1] > expected:
            x = x[:, :expected]
        elif x.shape[1] < expected:
            x = np.hstack([x, np.zeros((1, expected - x.shape[1]))])

        return float(self.model.predict_proba(x)[0, 1])

    # ── 저장 / 로드 ──────────────────────────────────────────────────────────

    def save(self):
        with open(DATA_DIR / "win_predictor.pkl", "wb") as f:
            pickle.dump(self, f)
        print(f"  → data/win_predictor.pkl 저장 완료")

    @classmethod
    def load(cls) -> "WinPredictor":
        p = DATA_DIR / "win_predictor.pkl"
        if not p.exists():
            raise FileNotFoundError("win_predictor.pkl 없음 — train_models.py 실행 필요")
        with open(p, "rb") as f:
            return pickle.load(f)
