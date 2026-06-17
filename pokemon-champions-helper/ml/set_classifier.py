"""
세트 분류기 — Multinomial Naive Bayes

학습 데이터 2가지를 병합해서 사용:
  A) data/smogon_sets.json  : Smogon 전체 채용률 (아이템별 조건부 아님 → 근사치)
  B) data/curated_sets.json : 직접 작성한 세트별 기술 패턴 (없으면 A만 사용)

curated_sets.json 포맷 (손수 작성):
{
  "Garchomp": [
    {"label": "Choice Scarf",  "moves": ["Earthquake", "Dragon Claw", "Stone Edge", "Outrage"]},
    {"label": "Rocky Helmet",  "moves": ["Earthquake", "Dragon Claw", "Stealth Rock", "Toxic"]},
    {"label": "Life Orb",      "moves": ["Earthquake", "Dragon Claw", "Fire Blast", "Swords Dance"]}
  ]
}

배틀 사용:
  입력: ["Earthquake", "Dragon Claw"]  (관찰한 기술, 1~4개)
  출력: [{"item": "Choice Scarf", "prob": 63.2}, ...]
"""

import json
import numpy as np
from pathlib import Path
from sklearn.naive_bayes import MultinomialNB
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import cross_val_score
import pickle

DATA_DIR = Path(__file__).parent.parent / "data"


class SetClassifier:

    def __init__(self):
        self.move_idx: dict[str, int] = {}
        self.poke_classifiers: dict[str, dict] = {}
        self._trained = False

    # ── 학습 ─────────────────────────────────────────────────────────────────

    def train(self, smogon_sets: dict, curated_sets: dict | None = None):
        """
        smogon_sets : fetch_data.py 결과 (전체 채용률)
        curated_sets: data/curated_sets.json (직접 작성한 세트, 있으면 우선 사용)
        """
        # 전체 기술 목록 구축
        all_moves: set[str] = set()
        for pdata in smogon_sets.values():
            for m in pdata.get("top_moves", []):
                all_moves.add(m["move"])
        if curated_sets:
            for sets in curated_sets.values():
                for s in sets:
                    all_moves.update(s.get("moves", []))
        self.move_idx = {m: i for i, m in enumerate(sorted(all_moves))}
        n_moves = len(self.move_idx)

        trained_count = 0

        # curated_sets 우선 처리 (정확한 레이블 데이터)
        curated_names: set[str] = set()
        if curated_sets:
            for poke_name, sets in curated_sets.items():
                if len(sets) < 2:
                    continue
                X, y = self._build_curated_XY(sets, n_moves)
                clf_data = self._fit(X, y)
                if clf_data:
                    self.poke_classifiers[poke_name] = clf_data
                    curated_names.add(poke_name)
                    trained_count += 1

        # smogon_sets로 나머지 포켓몬 처리 (근사치)
        for poke_name, pdata in smogon_sets.items():
            if poke_name in curated_names:
                continue  # 이미 curated로 처리
            top_moves = pdata.get("top_moves", [])
            top_items = pdata.get("top_items", [])
            if len(top_moves) < 3 or len(top_items) < 2:
                continue

            X, y = self._build_smogon_XY(top_moves, top_items, n_moves)
            clf_data = self._fit(X, y)
            if clf_data:
                self.poke_classifiers[poke_name] = clf_data
                trained_count += 1

        self._trained = True
        curated_count = len(curated_names)
        smogon_count  = trained_count - curated_count
        print(f"  학습 완료: 총 {trained_count}마리 "
              f"(curated={curated_count}, smogon근사={smogon_count})")

    def _build_curated_XY(self, sets: list[dict], n_moves: int):
        """
        curated_sets 포맷 → 학습 행렬.
        각 세트의 기술 조합이 서로 달라 분류기가 의미 있게 학습됨.
        """
        X, y = [], []
        for s in sets:
            vec = np.zeros(n_moves, dtype=np.float32)
            for move in s.get("moves", []):
                mi = self.move_idx.get(move)
                if mi is not None:
                    vec[mi] = 1.0
            X.append(vec)
            y.append(s["label"])
        return np.array(X), y

    def _build_smogon_XY(self, top_moves: list, top_items: list, n_moves: int):
        """
        Smogon 근사치 방식.
        아이템마다 약간씩 다른 기술 채용률을 노이즈로 섞어 구분.
        (아이템별 조건부 데이터가 없는 한계를 최소화)
        """
        # 기본 채용률 벡터
        base_vec = np.zeros(n_moves, dtype=np.float32)
        for m in top_moves:
            mi = self.move_idx.get(m["move"])
            if mi is not None:
                base_vec[mi] = m["usage"]

        # 아이템 우선도(usage)를 가중치로 사용해 약간씩 다른 벡터 생성
        X, y = [], []
        total_usage = sum(it["usage"] for it in top_items[:4])
        if total_usage == 0:
            return np.array(X), y

        for rank, item_entry in enumerate(top_items[:4]):
            item = item_entry["item"]
            weight = item_entry["usage"] / total_usage
            # 상위 아이템일수록 상위 기술 채용률에 가중치 부여
            vec = base_vec.copy()
            nonzero = np.where(vec > 0)[0]
            if len(nonzero) > 0:
                # 순위가 높은 기술에 아이템 가중치 반영
                sorted_idx = nonzero[np.argsort(vec[nonzero])[::-1]]
                for i, mi in enumerate(sorted_idx):
                    boost = weight * (1.0 / (i + 1)) * 0.3
                    vec[mi] = min(1.0, vec[mi] + boost * (1 - rank * 0.1))
            X.append(vec)
            y.append(item)

        return np.array(X), y

    def _fit(self, X: np.ndarray, y: list) -> dict | None:
        if len(X) < 2 or len(set(y)) < 2:
            return None
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = np.clip(X_scaled, 0, None)
        model = MultinomialNB(alpha=1.0)
        model.fit(X_scaled, y)
        return {"model": model, "scaler": scaler, "classes": list(model.classes_)}

    # ── 평가 ─────────────────────────────────────────────────────────────────

    def evaluate(self, curated_sets: dict) -> dict:
        """
        curated_sets가 있는 포켓몬에 대해 Leave-One-Out 정확도 계산.
        반환: {"poke_name": {"accuracy": float, "n_sets": int}, ...}
        """
        results = {}
        n_moves = len(self.move_idx)

        for poke_name, sets in curated_sets.items():
            if len(sets) < 2:
                continue
            X, y = self._build_curated_XY(sets, n_moves)
            scaler = MinMaxScaler()
            X_s = np.clip(scaler.fit_transform(X), 0, None)

            model = MultinomialNB(alpha=1.0)
            # LOO CV (세트 수가 적어 3-fold 대신)
            n = len(y)
            if n < 3:
                results[poke_name] = {"accuracy": None, "n_sets": n, "note": "샘플 부족"}
                continue
            cv = min(n, 5)
            scores = cross_val_score(model, X_s, y, cv=cv, scoring="accuracy")
            results[poke_name] = {
                "accuracy": round(float(scores.mean()), 4),
                "std": round(float(scores.std()), 4),
                "n_sets": n,
            }
        return results

    # ── 추론 ─────────────────────────────────────────────────────────────────

    def predict(self, poke_name: str, observed_moves: list[str]) -> list[dict]:
        """
        관찰 기술 1~4개 → 세트(아이템) 확률 반환.
        반환: [{"item": str, "prob": float}, ...]  확률 내림차순
        """
        if not self._trained:
            return []
        clf_data = self.poke_classifiers.get(poke_name)
        if clf_data is None:
            return []

        n_moves = len(self.move_idx)
        x = np.zeros(n_moves, dtype=np.float32)
        for m in observed_moves:
            mi = self.move_idx.get(m)
            if mi is not None:
                x[mi] = 1.0

        x_scaled = clf_data["scaler"].transform(x.reshape(1, -1))
        x_scaled = np.clip(x_scaled, 0, None)
        probs = clf_data["model"].predict_proba(x_scaled)[0]

        result = [
            {"item": cls, "prob": round(float(p) * 100, 1)}
            for cls, p in zip(clf_data["classes"], probs)
        ]
        result.sort(key=lambda d: d["prob"], reverse=True)
        return result

    # ── 저장/로드 ─────────────────────────────────────────────────────────────

    def save(self, path: Path | None = None):
        save_path = path or (DATA_DIR / "set_classifier.pkl")
        with open(save_path, "wb") as f:
            pickle.dump(self, f)
        print(f"  → {save_path} 저장 완료")

    @classmethod
    def load(cls, path: Path | None = None) -> "SetClassifier":
        load_path = path or (DATA_DIR / "set_classifier.pkl")
        if not load_path.exists():
            raise FileNotFoundError(f"{load_path} 없음 — train_models.py 먼저 실행")
        with open(load_path, "rb") as f:
            return pickle.load(f)
