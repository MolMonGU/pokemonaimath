"""SVD/PCA 임베딩 로드 및 조회"""

import json
import numpy as np
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent.parent / "data"


class Embeddings:
    def __init__(self):
        self._loaded = False
        self.U: np.ndarray | None = None       # (n_poke × k) 포켓몬 임베딩
        self.S: np.ndarray | None = None       # (k,) 특이값
        self.Vt: np.ndarray | None = None      # (k × n_moves) 기술 임베딩
        self.pca: np.ndarray | None = None     # (n_poke × 10) PCA 임베딩
        self.poke_names: list[str] = []
        self.move_names: list[str] = []
        self.poke_idx: dict[str, int] = {}
        self.move_idx: dict[str, int] = {}

    def load(self):
        if self._loaded:
            return
        meta_path = DATA_DIR / "embeddings_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError("임베딩 없음 — scripts/train_models.py 먼저 실행하세요")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.poke_names = meta["poke_names"]
        self.move_names = meta["move_names"]
        self.poke_idx = {p: i for i, p in enumerate(self.poke_names)}
        self.move_idx = {m: i for i, m in enumerate(self.move_names)}
        self.U   = np.load(DATA_DIR / "svd_U.npy")
        self.S   = np.load(DATA_DIR / "svd_S.npy")
        self.Vt  = np.load(DATA_DIR / "svd_Vt.npy")
        self.pca = np.load(DATA_DIR / "pca_embeddings.npy")
        self._loaded = True

    def poke_vector(self, name: str) -> np.ndarray | None:
        """SVD 포켓몬 임베딩 벡터 (k차원)"""
        self.load()
        idx = self.poke_idx.get(name)
        if idx is None:
            return None
        return self.U[idx] * self.S

    def move_vector(self, move: str) -> np.ndarray | None:
        """SVD 기술 임베딩 벡터 (k차원)"""
        self.load()
        idx = self.move_idx.get(move)
        if idx is None:
            return None
        return self.Vt[:, idx]

    def predict_moves(self, poke_name: str, observed_moves: list[str],
                      top_n: int = 5) -> list[tuple[str, float]]:
        """
        관찰된 기술을 기반으로 나머지 기술 슬롯 후보 예측.
        SVD 행 복원: A_hat[i] = U[i] @ diag(S) @ Vt
        """
        self.load()
        idx = self.poke_idx.get(poke_name)
        if idx is None:
            return []
        row = self.U[idx] @ np.diag(self.S) @ self.Vt   # (n_moves,)
        observed_set = set(observed_moves)
        candidates = [
            (self.move_names[i], float(row[i]))
            for i in range(len(self.move_names))
            if self.move_names[i] not in observed_set and row[i] > 0
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_n]

    def similar_pokemon(self, poke_name: str, top_n: int = 5) -> list[tuple[str, float]]:
        """PCA 임베딩 기준 유사한 포켓몬"""
        self.load()
        idx = self.poke_idx.get(poke_name)
        if idx is None:
            return []
        vec = self.pca[idx]
        dists = np.linalg.norm(self.pca - vec, axis=1)
        order = np.argsort(dists)[1:top_n + 1]
        return [(self.poke_names[i], float(dists[i])) for i in order]


# 싱글톤
_emb = Embeddings()
get_embeddings = lambda: _emb
