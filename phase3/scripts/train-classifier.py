#!/usr/bin/env python3
"""
Phase 3c: ML-based classification of normal DoH vs DoH tunneling.

Trains three models on the features from Phase 3b:
    - Logistic Regression (linear baseline)
    - Random Forest
    - XGBoost

Evaluation:
    - 5-fold stratified cross-validation (for robust metrics on small data)
    - Final models also fitted on 80/20 split for confusion matrices / ROC

Outputs:
    - classification_report.txt  : cross-val and test-set metrics
    - confusion_matrices.png     : one matrix per model
    - roc_curves.png             : ROC curves overlaid
    - feature_importance.png     : RF + XGBoost feature importance bars

Usage:
    python3 train-classifier.py \\
        --csv /opt/phase3-results/features.csv \\
        --output-dir /opt/phase3-results/ml
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc, classification_report,
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

import xgboost as xgb

FEATURES_25 = [
    "num_packets", "num_bytes", "bytes_up", "bytes_down", "bytes_ratio",
    "packets_per_sec", "bytes_per_sec", "packets_per_sec_up", "packets_per_sec_down",
    "size_mean", "size_std", "size_median", "size_min", "size_max", "size_p90",
    "iat_mean", "iat_std", "iat_median", "iat_max", "iat_min",
    "direction_changes", "longest_up_run", "longest_down_run",
    "burst_count", "max_burst_size",
]

CLASS_NAMES = ["normal", "tunnel"]

RANDOM_STATE = 42


def build_models():
    """Return a dict of model name -> sklearn-style estimator.

    LR is wrapped in a StandardScaler because it's scale-sensitive. The tree-
    based models don't need scaling.
    """
    return {
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
        ]),
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "XGBoost": xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def cross_validate_models(models, X, y, n_splits=5):
    """Return DataFrame of mean +/- std for accuracy / precision / recall / f1."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    records = []
    for name, model in models.items():
        print(f"  [{name}] running {n_splits}-fold CV...", flush=True)
        acc  = cross_val_score(model, X, y, cv=skf, scoring="accuracy",  n_jobs=-1)
        prec = cross_val_score(model, X, y, cv=skf, scoring="precision", n_jobs=-1)
        rec  = cross_val_score(model, X, y, cv=skf, scoring="recall",    n_jobs=-1)
        f1   = cross_val_score(model, X, y, cv=skf, scoring="f1",        n_jobs=-1)
        records.append({
            "model": name,
            "accuracy":  f"{acc.mean():.3f} ± {acc.std():.3f}",
            "precision": f"{prec.mean():.3f} ± {prec.std():.3f}",
            "recall":    f"{rec.mean():.3f} ± {rec.std():.3f}",
            "f1":        f"{f1.mean():.3f} ± {f1.std():.3f}",
        })
    return pd.DataFrame(records)


def plot_confusion_matrices(results, out_path):
    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4.5))
    if n == 1:
        axes = [axes]
    for ax, (name, r) in zip(axes, results.items()):
        cm = r["confusion_matrix"]
        im = ax.imshow(cm, cmap="Blues")
        ax.set_title(f"{name}\naccuracy={r['accuracy']:.3f}", fontsize=11)
        ax.set_xticks([0, 1]); ax.set_xticklabels(CLASS_NAMES)
        ax.set_yticks([0, 1]); ax.set_yticklabels(CLASS_NAMES)
        ax.set_xlabel("predicted"); ax.set_ylabel("actual")
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black",
                        fontsize=13)
        fig.colorbar(im, ax=ax, shrink=0.7)
    fig.suptitle("Phase 3c: Confusion matrices (80/20 hold-out test)", fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def plot_roc_curves(results, out_path):
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, r in results.items():
        if r["y_score"] is None:
            continue
        fpr, tpr, _ = roc_curve(r["y_true"], r["y_score"])
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, linewidth=2, label=f"{name} (AUC = {roc_auc:.3f})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1)
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title("Phase 3c: ROC curves (80/20 hold-out test)")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def plot_feature_importance(results, feature_names, out_path, top_n=15):
    """Plot RF and XGBoost feature importances side by side."""
    importable = {
        name: r for name, r in results.items()
        if r.get("feature_importance") is not None
    }
    if not importable:
        return
    n = len(importable)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 7))
    if n == 1:
        axes = [axes]
    for ax, (name, r) in zip(axes, importable.items()):
        imp = r["feature_importance"]
        order = np.argsort(imp)[::-1][:top_n]
        sorted_imp = imp[order]
        sorted_names = [feature_names[i] for i in order]
        ax.barh(range(len(order)), sorted_imp[::-1], color="#2E86AB")
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels(sorted_names[::-1], fontsize=9)
        ax.set_title(f"{name}\ntop {top_n} features", fontsize=11)
        ax.set_xlabel("importance")
        ax.grid(True, axis="x", alpha=0.3)
    fig.suptitle("Phase 3c: Feature importance", fontsize=13, y=1.01)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def write_report(cv_df, holdout_results, out_path, n_samples_per_class):
    lines = []
    lines.append("=" * 72)
    lines.append(" Phase 3c: Classification report")
    lines.append("=" * 72)
    lines.append("")
    lines.append("Dataset:")
    lines.append(f"  normal (label=0) : {n_samples_per_class.get(0, 0)} samples")
    lines.append(f"  tunnel (label=1) : {n_samples_per_class.get(1, 0)} samples")
    lines.append("")
    lines.append("5-fold stratified cross-validation")
    lines.append("-" * 72)
    lines.append(cv_df.to_string(index=False))
    lines.append("")
    lines.append("")
    lines.append("80/20 hold-out test set — per-model details")
    lines.append("-" * 72)
    for name, r in holdout_results.items():
        lines.append(f"\n[{name}]")
        lines.append(f"  accuracy  = {r['accuracy']:.4f}")
        lines.append(f"  precision = {r['precision']:.4f}")
        lines.append(f"  recall    = {r['recall']:.4f}")
        lines.append(f"  f1        = {r['f1']:.4f}")
        lines.append("  classification_report:")
        lines.append("    " + r["sklearn_report"].replace("\n", "\n    "))
        lines.append("  confusion_matrix (rows=actual, cols=predicted):")
        lines.append("    " + str(r["confusion_matrix"]).replace("\n", "\n    "))
    Path(out_path).write_text("\n".join(lines) + "\n")
    print(f"  wrote {out_path}")


def train_and_evaluate_holdout(models, X, y, feature_names):
    """Fit on 80/20 split. Return per-model metrics + predictions needed for plots."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE,
    )
    results = {}
    for name, model in models.items():
        print(f"  [{name}] fit on 80% train ({len(X_train)} samples), test on 20% ({len(X_test)})", flush=True)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        # Probability score for ROC (all three classifiers expose predict_proba)
        y_score = model.predict_proba(X_test)[:, 1]

        # Feature importance (RF, XGBoost)
        if hasattr(model, "feature_importances_"):
            feature_importance = model.feature_importances_
        else:
            feature_importance = None

        results[name] = {
            "y_true": y_test,
            "y_pred": y_pred,
            "y_score": y_score,
            "accuracy":  accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall":    recall_score(y_test, y_pred, zero_division=0),
            "f1":        f1_score(y_test, y_pred, zero_division=0),
            "confusion_matrix": confusion_matrix(y_test, y_pred),
            "sklearn_report": classification_report(
                y_test, y_pred, target_names=CLASS_NAMES, zero_division=0,
            ),
            "feature_importance": feature_importance,
        }
    return results


def main():
    p = argparse.ArgumentParser(description="Phase 3c classifier training")
    p.add_argument("--csv", required=True, help="features CSV from extract-features.py")
    p.add_argument("--output-dir", required=True, help="directory for reports / plots")
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    print("============================================")
    print(" Phase 3c: ML classification")
    print("============================================")
    print(f"Loaded {len(df)} samples from {args.csv}")
    counts = df["label"].value_counts().to_dict()
    print(f"  {counts}")
    print()

    X = df[FEATURES_25].values
    y = df["label"].values

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/3] Cross-validation")
    models_cv = build_models()
    cv_df = cross_validate_models(models_cv, X, y)
    print()
    print(cv_df.to_string(index=False))
    print()

    print("[2/3] 80/20 hold-out training")
    models_hold = build_models()
    holdout = train_and_evaluate_holdout(models_hold, X, y, FEATURES_25)
    print()

    print("[3/3] Writing plots and report")
    plot_confusion_matrices(holdout, out_dir / "confusion_matrices.png")
    plot_roc_curves(holdout, out_dir / "roc_curves.png")
    plot_feature_importance(holdout, FEATURES_25, out_dir / "feature_importance.png")
    write_report(cv_df, holdout, out_dir / "classification_report.txt", counts)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
