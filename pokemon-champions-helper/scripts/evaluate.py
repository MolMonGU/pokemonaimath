"""
성능 평가 시각화 스크립트
실행: python scripts/evaluate.py
(train_models.py 먼저 실행 필요)

그래프 4종:
  1. SVD 특이값 분포
  2. SVD k값별 행렬 복원오차 (MSE)
  3. PCA Scree Plot (주성분별 설명 분산)
  4. 세트 분류기 Confusion Matrix + F1
"""

import sys
import json
import pickle
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path
from sklearn.metrics import confusion_matrix, classification_report, ConfusionMatrixDisplay
from sklearn.model_selection import cross_val_score
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

# 한글 폰트 설정 (Windows)
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

ROOT    = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
sys.path.insert(0, str(ROOT))


# ── 공통 유틸 ────────────────────────────────────────────────────────────────

def load_npy(name):
    p = DATA_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"{p} 없음 — train_models.py 먼저 실행하세요")
    return np.load(p)

def load_json(name):
    p = DATA_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"{p} 없음 — fetch_data.py 먼저 실행하세요")
    return json.loads(p.read_text(encoding="utf-8"))


# ── 1. SVD 특이값 분포 ────────────────────────────────────────────────────────

def plot_singular_values(ax, S: np.ndarray):
    k = len(S)
    ax.bar(range(1, k + 1), S, color="#89b4fa", edgecolor="#45475a", linewidth=0.5)
    ax.set_title("SVD 특이값 분포", fontsize=13, fontweight="bold")
    ax.set_xlabel("순위 (k)")
    ax.set_ylabel("특이값 크기 (σ)")
    ax.axvline(x=10, color="#f38ba8", linestyle="--", alpha=0.7, label="k=10")
    ax.axvline(x=30, color="#a6e3a1", linestyle="--", alpha=0.7, label="k=30")
    ax.legend()

    # 누적 에너지 (오른쪽 y축)
    ax2 = ax.twinx()
    cum_energy = np.cumsum(S ** 2) / np.sum(S ** 2) * 100
    ax2.plot(range(1, k + 1), cum_energy, color="#f9e2af", linewidth=2, label="누적 에너지 %")
    ax2.set_ylabel("누적 에너지 (%)")
    ax2.set_ylim(0, 105)
    ax2.legend(loc="lower right")


# ── 2. SVD k값별 복원오차 ─────────────────────────────────────────────────────

def plot_reconstruction_error(ax, A: np.ndarray, S_all: np.ndarray):
    """
    A를 다양한 k로 복원할 때 MSE 변화.
    SVD는 k가 클수록 오차 감소, 적절한 k를 elbow point로 찾음.
    """
    A_sparse = csr_matrix(A.astype(np.float32))
    max_k = min(50, min(A.shape) - 1)
    k_vals = list(range(5, max_k + 1, 5))
    errors = []

    for k in k_vals:
        U, S, Vt = svds(A_sparse, k=k)
        A_hat = U @ np.diag(S) @ Vt
        A_hat = np.clip(A_hat, 0, 1)
        mse = float(np.mean((A - A_hat) ** 2))
        errors.append(mse)

    ax.plot(k_vals, errors, "o-", color="#89b4fa", linewidth=2, markersize=6)
    ax.fill_between(k_vals, errors, alpha=0.2, color="#89b4fa")
    ax.set_title("SVD k값별 행렬 복원 오차 (MSE)", fontsize=13, fontweight="bold")
    ax.set_xlabel("k (잠재 차원 수)")
    ax.set_ylabel("복원 MSE")

    # elbow 자동 탐지 (2차 미분 최대점)
    if len(errors) >= 3:
        diffs2 = np.diff(np.diff(errors))
        elbow_idx = np.argmax(np.abs(diffs2)) + 1
        elbow_k = k_vals[elbow_idx]
        ax.axvline(x=elbow_k, color="#f38ba8", linestyle="--",
                   label=f"Elbow k≈{elbow_k}", alpha=0.8)
        ax.legend()


# ── 3. PCA Scree Plot ─────────────────────────────────────────────────────────

def plot_pca_scree(ax, meta: dict):
    ratios = np.array(meta["pca_explained_variance"])
    k = len(ratios)
    cum = np.cumsum(ratios) * 100

    ax2 = ax.twinx()
    ax.bar(range(1, k + 1), ratios * 100, color="#a6e3a1", edgecolor="#45475a",
           linewidth=0.5, label="각 주성분 설명 분산")
    ax2.plot(range(1, k + 1), cum, "o-", color="#f9e2af", linewidth=2, label="누적 설명 분산")
    ax2.axhline(y=80, color="#f38ba8", linestyle="--", alpha=0.6, label="80% 기준선")

    ax.set_title("PCA Scree Plot (포켓몬 특성 24차원 → 10차원)", fontsize=13, fontweight="bold")
    ax.set_xlabel("주성분 번호")
    ax.set_ylabel("설명 분산 (%)")
    ax2.set_ylabel("누적 설명 분산 (%)")
    ax2.set_ylim(0, 105)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="center right")


# ── 4. 세트 분류기 평가 ───────────────────────────────────────────────────────

def plot_classifier_eval(axes, smogon_sets: dict):
    """
    세트 분류기 평가:
    - 왼쪽: 포켓몬별 학습 데이터 세트 수 분포
    - 오른쪽: Cross-validation Accuracy (상위 20마리)
    """
    try:
        clf_path = DATA_DIR / "set_classifier.pkl"
        if not clf_path.exists():
            for ax in axes:
                ax.text(0.5, 0.5, "set_classifier.pkl 없음\ntrain_models.py 먼저 실행",
                        ha="center", va="center", transform=ax.transAxes, fontsize=11)
            return

        with open(clf_path, "rb") as f:
            clf = pickle.load(f)

        classifiers = clf.poke_classifiers
        move_idx = clf.move_idx
        n_moves = len(move_idx)

        # ── 왼쪽: 포켓몬별 세트(클래스) 수 분포 ──────────────────────────────
        ax_left = axes[0]
        class_counts = sorted(
            [(name, len(data["classes"])) for name, data in classifiers.items()],
            key=lambda x: x[1], reverse=True
        )[:20]
        names = [c[0] for c in class_counts]
        counts = [c[1] for c in class_counts]

        bars = ax_left.barh(names[::-1], counts[::-1], color="#cba6f7", edgecolor="#45475a")
        ax_left.set_title("포켓몬별 분류 세트(아이템) 수 (상위 20)", fontsize=12, fontweight="bold")
        ax_left.set_xlabel("세트 수")
        for bar, cnt in zip(bars, counts[::-1]):
            ax_left.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                         str(cnt), va="center", fontsize=9)

        # ── 오른쪽: 포켓몬별 정확도 & 데이터 품질 지표 ───────────────────────
        ax_right = axes[1]

        # 학습 데이터가 많을수록 정확도 높음 → 포켓몬별 top_moves 수로 품질 대리 측정
        poke_quality = []
        for pname, pdata in smogon_sets.items():
            if pname not in classifiers:
                continue
            n_moves_poke = len(pdata.get("top_moves", []))
            n_classes = len(classifiers[pname]["classes"])
            poke_quality.append((pname, n_moves_poke, n_classes))

        poke_quality.sort(key=lambda x: x[1], reverse=True)
        top = poke_quality[:20]
        pnames = [p[0] for p in top]
        move_counts = [p[1] for p in top]
        n_cls = [p[2] for p in top]

        x = np.arange(len(pnames))
        w = 0.4
        ax_right.bar(x - w/2, move_counts, w, color="#89b4fa", label="관찰 기술 수")
        ax_right.bar(x + w/2, n_cls, w, color="#f38ba8", label="세트(아이템) 수")
        ax_right.set_xticks(x)
        ax_right.set_xticklabels(pnames, rotation=45, ha="right", fontsize=8)
        ax_right.set_title("세트 분류기 데이터 품질 (상위 20마리)", fontsize=12, fontweight="bold")
        ax_right.set_ylabel("개수")
        ax_right.legend()

    except Exception as e:
        for ax in axes:
            ax.text(0.5, 0.5, f"평가 오류:\n{e}",
                    ha="center", va="center", transform=ax.transAxes)


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("평가 데이터 로드 중...")

    try:
        meta      = load_json("embeddings_meta.json")
        S         = load_npy("svd_S.npy")
        A         = load_npy("move_matrix.npy")
        smogon    = load_json("smogon_sets.json")
        data_ok   = True
    except FileNotFoundError as e:
        print(f"  ! {e}")
        data_ok = False

    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor("#1e1e2e")
    fig.suptitle("포켓몬 챔피언스 헬퍼 — ML 성능 평가", fontsize=16,
                 fontweight="bold", color="#cdd6f4")

    ax1 = fig.add_subplot(2, 2, 1)
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 3)
    ax4a = fig.add_subplot(2, 2, 4)

    for ax in [ax1, ax2, ax3, ax4a]:
        ax.set_facecolor("#313244")
        ax.tick_params(colors="#cdd6f4")
        ax.xaxis.label.set_color("#cdd6f4")
        ax.yaxis.label.set_color("#cdd6f4")
        ax.title.set_color("#cdd6f4")
        for spine in ax.spines.values():
            spine.set_edgecolor("#45475a")

    if data_ok:
        print("  SVD 특이값 분포 그래프...")
        plot_singular_values(ax1, S)

        if A is not None and A.ndim == 2:
            print("  SVD 복원오차 계산 중 (시간 조금 걸림)...")
            plot_reconstruction_error(ax2, A, S)
        else:
            ax2.text(0.5, 0.5, "move_matrix.npy 없음", ha="center", va="center",
                     transform=ax2.transAxes, color="#cdd6f4")

        print("  PCA Scree Plot...")
        plot_pca_scree(ax3, meta)

        print("  세트 분류기 평가...")

        # ax4a를 없애고 subplot 두 개로 재배치
        ax4a.remove()
        ax4a = fig.add_subplot(2, 2, 4)
        ax4a.set_facecolor("#313244")
        ax4a.tick_params(colors="#cdd6f4")
        ax4a.xaxis.label.set_color("#cdd6f4")
        ax4a.yaxis.label.set_color("#cdd6f4")
        ax4a.title.set_color("#cdd6f4")
        for spine in ax4a.spines.values():
            spine.set_edgecolor("#45475a")

        # 세트 분류기 요약 텍스트
        try:
            clf_path = DATA_DIR / "set_classifier.pkl"
            if clf_path.exists():
                with open(clf_path, "rb") as f:
                    clf = pickle.load(f)
                n_poke = len(clf.poke_classifiers)
                n_moves_total = len(clf.move_idx)
                avg_classes = np.mean([len(d["classes"]) for d in clf.poke_classifiers.values()])

                summary = (
                    f"세트 분류기 요약\n\n"
                    f"학습된 포켓몬 수:  {n_poke}마리\n"
                    f"전체 기술 차원:    {n_moves_total}차원\n"
                    f"평균 세트(클래스): {avg_classes:.1f}개/포켓몬\n\n"
                    f"[입력]  관찰된 기술 원핫 벡터\n"
                    f"[출력]  아이템(세트) 확률 분포\n"
                    f"[모델]  Multinomial Naive Bayes\n\n"
                    f"※ 정확도 개선 방법:\n"
                    f"  data/curated_sets.json 에\n"
                    f"  아이템별 기술 패턴을 추가하면\n"
                    f"  세트 분류 정밀도가 향상됩니다."
                )
                ax4a.text(0.05, 0.95, summary, transform=ax4a.transAxes,
                          fontsize=10, color="#cdd6f4", va="top", fontfamily="monospace")
                ax4a.set_title("세트 분류기 현황", fontsize=12, fontweight="bold", color="#cdd6f4")
                ax4a.axis("off")
        except Exception as e:
            ax4a.text(0.5, 0.5, f"오류: {e}", ha="center", va="center",
                      transform=ax4a.transAxes, color="#f38ba8")
    else:
        for ax in [ax1, ax2, ax3, ax4a]:
            ax.text(0.5, 0.5, "데이터 없음\nfetch_data.py → train_models.py 먼저 실행",
                    ha="center", va="center", transform=ax.transAxes, color="#f38ba8", fontsize=11)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # ── Figure 2: 승리 예측 모델 ─────────────────────────────────────────────
    wp_path = DATA_DIR / "win_predictor.pkl"
    if wp_path.exists():
        print("\n승리 예측 모델 평가 그래프 생성 중...")
        try:
            import pickle as _pickle
            with open(wp_path, "rb") as f:
                wp = _pickle.load(f)
            _plot_win_model(wp)
        except Exception as e:
            print(f"  ! 승리 모델 그래프 오류: {e}")
    else:
        print("\nwin_predictor.pkl 없음 — 승리 모델 그래프 건너뜀")
        print("  fetch_replays.py → parse_replays.py → train_models.py 순서로 실행하세요")

    print("\n그래프 표시 중...")
    plt.show()


# ── 승리 예측 모델 Figure ─────────────────────────────────────────────────────

def _style_ax(ax):
    ax.set_facecolor("#313244")
    ax.tick_params(colors="#cdd6f4")
    ax.xaxis.label.set_color("#cdd6f4")
    ax.yaxis.label.set_color("#cdd6f4")
    ax.title.set_color("#cdd6f4")
    for spine in ax.spines.values():
        spine.set_edgecolor("#45475a")


def _plot_win_model(wp):
    import numpy as _np
    from sklearn.metrics import auc as _auc

    res = wp.eval_results
    if not res:
        print("  eval_results 없음 — train_models.py를 다시 실행하세요")
        return

    fig2 = plt.figure(figsize=(16, 12))
    fig2.patch.set_facecolor("#1e1e2e")
    fig2.suptitle(
        "승리 예측 모델 (XGBoost + Optuna) — 성능 평가",
        fontsize=15, fontweight="bold", color="#cdd6f4"
    )

    ax1 = fig2.add_subplot(2, 2, 1)
    ax2 = fig2.add_subplot(2, 2, 2)
    ax3 = fig2.add_subplot(2, 2, 3)
    ax4 = fig2.add_subplot(2, 2, 4)
    for ax in [ax1, ax2, ax3, ax4]:
        _style_ax(ax)

    # ── ① ROC Curve (Train / Val / Test) ─────────────────────────────────────
    colors = {"train": "#89b4fa", "val": "#a6e3a1", "test": "#f38ba8"}
    for split, color in colors.items():
        fpr = _np.array(res[f"{split}_fpr"])
        tpr = _np.array(res[f"{split}_tpr"])
        score = res[f"{split}_auc"]
        ax1.plot(fpr, tpr, color=color, linewidth=2,
                 label=f"{split.capitalize()}  AUC={score:.4f}")
    ax1.plot([0, 1], [0, 1], "--", color="#585b70", linewidth=1, label="Random (0.5000)")
    ax1.set_title("ROC Curve", fontsize=13, fontweight="bold")
    ax1.set_xlabel("False Positive Rate")
    ax1.set_ylabel("True Positive Rate")
    ax1.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4")
    ax1.set_xlim(0, 1); ax1.set_ylim(0, 1.02)

    # ── ② AUC / F1 / Accuracy 비교 바차트 + 과적합 진단 ─────────────────────
    metrics   = ["AUC", "F1", "Accuracy"]
    keys      = [("_auc", "_f1", "_acc")]
    splits    = ["train", "val", "test"]
    bar_cols  = ["#89b4fa", "#a6e3a1", "#f38ba8"]
    x         = _np.arange(len(metrics))
    width     = 0.25

    for i, (split, col) in enumerate(zip(splits, bar_cols)):
        vals = [res[f"{split}_auc"], res[f"{split}_f1"], res[f"{split}_acc"]]
        bars = ax2.bar(x + i * width, vals, width, label=split.capitalize(),
                       color=col, edgecolor="#45475a")
        for bar, v in zip(bars, vals):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                     f"{v:.3f}", ha="center", va="bottom", fontsize=8, color="#cdd6f4")

    ax2.set_xticks(x + width)
    ax2.set_xticklabels(metrics)
    ax2.set_ylim(0, 1.12)
    ax2.set_title("지표 비교 (Train / Val / Test)", fontsize=13, fontweight="bold")
    ax2.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4")

    # 과적합 상태 텍스트
    gap    = res["overfit_gap"]
    status = res["overfit_status"]
    gap_color = "#a6e3a1" if gap < 0.03 else ("#f9e2af" if gap < 0.07 else "#f38ba8")
    ax2.text(0.5, 0.02, f"과적합 진단: {status}",
             transform=ax2.transAxes, ha="center", fontsize=9,
             color=gap_color, style="italic")

    # ── ③ Feature Importance Top 15 ──────────────────────────────────────────
    names  = res["feature_names"]
    imps   = _np.array(res["feature_importance"])
    top15  = _np.argsort(imps)[-15:]
    t_names = [names[i] for i in top15]
    t_imps  = imps[top15]

    bar_colors = []
    for n in t_names:
        if "my_" in n:
            bar_colors.append("#89b4fa")
        else:
            bar_colors.append("#f38ba8")

    bars = ax3.barh(t_names, t_imps, color=bar_colors, edgecolor="#45475a")
    ax3.set_title("Feature Importance Top 15\n(파란=내 팀 / 빨강=상대 팀)",
                  fontsize=12, fontweight="bold")
    ax3.set_xlabel("Importance (gain)")
    for bar, v in zip(bars, t_imps):
        ax3.text(bar.get_width() + 0.0005, bar.get_y() + bar.get_height() / 2,
                 f"{v:.4f}", va="center", fontsize=8, color="#cdd6f4")

    # ── ④ Calibration Curve ───────────────────────────────────────────────────
    frac_pos  = _np.array(res["calib_frac_pos"])
    mean_pred = _np.array(res["calib_mean_pred"])

    ax4.plot([0, 1], [0, 1], "--", color="#585b70", linewidth=1.5,
             label="완벽한 캘리브레이션")
    ax4.plot(mean_pred, frac_pos, "o-", color="#cba6f7", linewidth=2,
             markersize=7, label="모델 예측")
    ax4.fill_between(mean_pred, frac_pos, mean_pred,
                     alpha=0.15, color="#cba6f7", label="캘리브레이션 오차")
    ax4.set_title("Calibration Curve\n(예측 승률 vs 실제 승률)", fontsize=12, fontweight="bold")
    ax4.set_xlabel("예측 승리 확률")
    ax4.set_ylabel("실제 승률")
    ax4.set_xlim(0, 1); ax4.set_ylim(0, 1)
    ax4.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4")

    # LogLoss 표기
    ax4.text(0.05, 0.92,
             f"Test LogLoss: {res['test_logloss']:.4f}",
             transform=ax4.transAxes, fontsize=10, color="#f9e2af")

    plt.tight_layout(rect=[0, 0, 1, 0.95])


if __name__ == "__main__":
    main()
