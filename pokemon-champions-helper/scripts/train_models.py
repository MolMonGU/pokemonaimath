"""
SVD / PCA 학습 및 임베딩 저장 스크립트
실행: python scripts/train_models.py
(fetch_data.py 먼저 실행 필요)
"""

import json
import numpy as np
from pathlib import Path
from scipy.linalg import svd
from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize

DATA_DIR = Path(__file__).parent.parent / "data"

TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice",
    "Fighting","Poison","Ground","Flying","Psychic","Bug",
    "Rock","Ghost","Dragon","Dark","Steel","Fairy"
]
TYPE_IDX = {t: i for i, t in enumerate(TYPES)}

SVD_K = 50   # 포켓몬×기술 잠재 차원
PCA_K = 10   # 포켓몬 특성 압축 차원


def load_json(name):
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음 — fetch_data.py 먼저 실행하세요")
    return json.loads(path.read_text(encoding="utf-8"))


# ── 행렬 A 구성: 포켓몬 × 기술 (채용률) ─────────────────────────────────────

def build_move_matrix(smogon_sets: dict, pokedex: dict):
    """
    행 = 포켓몬, 열 = 기술
    값 = 해당 기술 채용률 (0~1 사이 추정치)
    """
    # 공통 포켓몬 목록 (두 데이터에 모두 있는 것)
    poke_names = sorted(set(smogon_sets.keys()) & set(pokedex.keys()))
    # 전체 기술 집합
    all_moves = set()
    for pname in poke_names:
        for m in smogon_sets[pname]["top_moves"]:
            all_moves.add(m["move"])
    move_names = sorted(all_moves)

    move_idx = {m: i for i, m in enumerate(move_names)}
    poke_idx = {p: i for i, p in enumerate(poke_names)}

    A = np.zeros((len(poke_names), len(move_names)), dtype=np.float32)
    for pname in poke_names:
        pi = poke_idx[pname]
        for entry in smogon_sets[pname]["top_moves"]:
            mi = move_idx.get(entry["move"])
            if mi is not None:
                A[pi, mi] = entry["usage"]

    return A, poke_names, move_names


# ── 행렬 B 구성: 포켓몬 × 특성 (스탯+타입) ──────────────────────────────────

def build_feature_matrix(pokedex: dict, poke_names: list):
    """
    행 = 포켓몬, 열 = [HP,ATK,DEF,SPA,SPD,SPE, 타입 원핫 18차원] = 24차원
    """
    B = np.zeros((len(poke_names), 24), dtype=np.float32)
    stat_keys = ["hp", "atk", "def", "spa", "spd", "spe"]

    for i, pname in enumerate(poke_names):
        entry = pokedex.get(pname, {})
        bs = entry.get("base_stats", {})
        for j, k in enumerate(stat_keys):
            B[i, j] = bs.get(k, 0)
        for t in entry.get("types", []):
            if t in TYPE_IDX:
                B[i, 6 + TYPE_IDX[t]] = 1.0

    # 스탯 6개는 0~255 범위 → 정규화
    stat_max = B[:, :6].max(axis=0)
    stat_max[stat_max == 0] = 1
    B[:, :6] /= stat_max

    return B


# ── SVD ──────────────────────────────────────────────────────────────────────

def run_svd(A: np.ndarray, k: int):
    """
    A ≈ U Σ Vᵀ  (scipy.sparse.linalg.svds, k개 특이값)
    반환: U(n×k), S(k,), Vt(k×m)
    """
    n, m = A.shape
    actual_k = min(k, min(n, m) - 1)
    print(f"  SVD 실행: {n}×{m} 행렬, k={actual_k}")
    A_sparse = csr_matrix(A)
    U, S, Vt = svds(A_sparse, k=actual_k)
    # svds는 오름차순 반환 → 내림차순 정렬
    order = np.argsort(S)[::-1]
    return U[:, order], S[order], Vt[order, :]


# ── PCA ──────────────────────────────────────────────────────────────────────

def run_pca(B: np.ndarray, k: int):
    pca = PCA(n_components=k, random_state=42)
    B_reduced = pca.fit_transform(B)
    explained = pca.explained_variance_ratio_.cumsum()[-1]
    print(f"  PCA: {B.shape[1]}차원 → {k}차원, 설명 분산 {explained:.1%}")
    return B_reduced, pca


# ── 저장 ─────────────────────────────────────────────────────────────────────

def save_embeddings(U, S, Vt, B_reduced, poke_names, move_names, pca):
    out = {
        "poke_names": poke_names,
        "move_names": move_names,
        "svd_S": S.tolist(),
        "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
    }
    (DATA_DIR / "embeddings_meta.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    np.save(DATA_DIR / "svd_U.npy", U.astype(np.float32))
    np.save(DATA_DIR / "svd_S.npy", S.astype(np.float32))
    np.save(DATA_DIR / "svd_Vt.npy", Vt.astype(np.float32))
    np.save(DATA_DIR / "pca_embeddings.npy", B_reduced.astype(np.float32))
    np.save(DATA_DIR / "move_matrix.npy", None)  # placeholder, A는 크므로 생략
    print("  → data/ 에 SVD/PCA 파일 저장 완료")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("데이터 로드 중...")
    smogon_sets = load_json("smogon_sets.json")
    pokedex = load_json("pokemon.json")

    print("행렬 A (포켓몬×기술) 구성 중...")
    A, poke_names, move_names = build_move_matrix(smogon_sets, pokedex)
    print(f"  → {A.shape[0]}마리 × {A.shape[1]}기술")
    np.save(DATA_DIR / "move_matrix.npy", A)

    print("행렬 B (포켓몬×특성) 구성 중...")
    B = build_feature_matrix(pokedex, poke_names)

    print("SVD 분해 중...")
    U, S, Vt = run_svd(A, SVD_K)

    print("PCA 압축 중...")
    B_reduced, pca = run_pca(B, PCA_K)

    print("임베딩 저장 중...")
    save_embeddings(U, S, Vt, B_reduced, poke_names, move_names, pca)

    print(f"\n학습 완료. 포켓몬 {len(poke_names)}마리, 기술 {len(move_names)}개")


    # 5) 세트 분류기
    print("세트 분류기 학습 중...")
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ml.set_classifier import SetClassifier

    curated_path = DATA_DIR / "curated_sets.json"
    curated_sets = None
    if curated_path.exists():
        raw = json.loads(curated_path.read_text(encoding="utf-8"))
        curated_sets = {k: v for k, v in raw.items() if not k.startswith("_")}
        print(f"  curated_sets.json 로드: {len(curated_sets)}마리")

    clf = SetClassifier()
    clf.train(smogon_sets, curated_sets=curated_sets)
    clf.save()

    # 6) 승리 예측 모델 (replay_dataset.csv 필요)
    print("\n승리 예측 모델 학습 중...")
    replay_csv = DATA_DIR / "replay_dataset.csv"
    if not replay_csv.exists():
        print("  ! replay_dataset.csv 없음")
        print("  ! fetch_replays.py → parse_replays.py 순서로 먼저 실행하세요")
    else:
        from ml.win_predictor import WinPredictor
        wp = WinPredictor()
        X, y, groups = wp.build_dataset()
        X_train, y_train, X_val, y_val, X_test, y_test = wp.split(X, y, groups)
        wp.tune(X_train, y_train, n_trials=80)
        wp.train(X_train, y_train, X_val, y_val)
        wp.evaluate_all(X_train, y_train, X_val, y_val, X_test, y_test)
        wp.save()

    print("\n전체 학습 완료.")


if __name__ == "__main__":
    main()
