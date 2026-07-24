from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .features import build_base_features, finalize_features
from .io_load import ROOT
from .labeling import CLASS_ORDER, label_dataframe
from .quantiles import compute_age_quantiles, compute_quantiles
from .train import load_metrics, prepare_full


def _state(labels: pd.DataFrame) -> pd.Series:
    return labels["LABEL"].fillna("HOLDOUT")


def _movement(baseline: pd.Series, alternative: pd.Series) -> tuple[float, pd.DataFrame]:
    states = CLASS_ORDER + ["HOLDOUT"]
    changed = float((baseline != alternative).mean())
    matrix = pd.crosstab(baseline, alternative).reindex(index=states, columns=states, fill_value=0)
    return changed, matrix


def _matrix_markdown(matrix: pd.DataFrame) -> str:
    return matrix.to_markdown()


def _age_specific_labels(base: pd.DataFrame, config: dict[str, Any], global_q: dict[str, float]) -> pd.DataFrame:
    by_age = compute_age_quantiles(base, config)
    pieces: list[pd.DataFrame] = []
    for age, subset in base.groupby("연령대", dropna=False):
        q = by_age.get(int(age), global_q) if pd.notna(age) else global_q
        features = finalize_features(subset, q)
        pieces.append(label_dataframe(features, q, strict_overlap=False))
    return pd.concat(pieces).sort_index()


def _counter_example_results() -> pd.DataFrame:
    fixture_path = ROOT / "tests" / "fixtures" / "counter_examples.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(payload["cases"])
    q = payload["quantiles"]
    labels = label_dataframe(frame, q, strict_overlap=False)
    return pd.DataFrame(
        {
            "case": frame["case"],
            "description": frame["description"],
            "result": labels["LABEL"].fillna("유보:" + labels["HOLDOUT_REASON"]),
            "expected": frame["expected"],
        }
    )


def validate_pipeline(raw: pd.DataFrame, config: dict[str, Any]) -> Path:
    reports = ROOT / config["project"]["reports_dir"]
    reports.mkdir(parents=True, exist_ok=True)
    base, features, q, labels = prepare_full(raw, config)
    metrics = load_metrics(config)
    total = len(labels)
    label_counts = labels["LABEL"].value_counts().reindex(CLASS_ORDER, fill_value=0)
    reason_counts = labels["HOLDOUT_REASON"].value_counts()
    overlap_count = int(labels["RAW_MATCH_COUNT"].gt(1).sum())
    no_match_count = int(labels["RAW_MATCH_COUNT"].eq(0).sum())

    baseline = _state(labels)
    sensitivity: list[tuple[str, float, pd.DataFrame]] = []
    for shift in (-0.05, 0.05):
        shifted_q = compute_quantiles(base, config, percentile_shift=shift)
        shifted_labels = label_dataframe(finalize_features(base, shifted_q), shifted_q, strict_overlap=False)
        change, matrix = _movement(baseline, _state(shifted_labels))
        sensitivity.append((f"분위 percentile {shift:+.0%}p", change, matrix))
    for scale in (0.9, 1.1):
        scaled_base = build_base_features(raw, config, anchor_scale=scale)
        scaled_q = compute_quantiles(scaled_base, config)
        scaled_labels = label_dataframe(finalize_features(scaled_base, scaled_q), scaled_q, strict_overlap=False)
        change, matrix = _movement(baseline, _state(scaled_labels))
        sensitivity.append((f"외부 앵커 {scale - 1:+.0%}", change, matrix))
    age_labels = _age_specific_labels(base, config, q)
    age_change, age_matrix = _movement(baseline, _state(age_labels))
    sensitivity.append(("연령대별 분위(희소 셀은 글로벌 fallback)", age_change, age_matrix))

    age_table = pd.crosstab(features["연령대"], baseline, normalize="index").reindex(columns=CLASS_ORDER + ["HOLDOUT"], fill_value=0)
    counter = _counter_example_results()
    best = metrics["best"]
    confusion = np.asarray(best["confusion_matrix"])
    figure, axis = plt.subplots(figsize=(7.5, 6.2))
    image = axis.imshow(confusion, cmap="Blues")
    axis.set_xticks(range(len(CLASS_ORDER)), CLASS_ORDER)
    axis.set_yticks(range(len(CLASS_ORDER)), CLASS_ORDER)
    axis.set_xlabel("Predicted pseudo-label")
    axis.set_ylabel("Rule pseudo-label")
    axis.set_title("Out-of-fold confusion matrix")
    for i in range(len(CLASS_ORDER)):
        for j in range(len(CLASS_ORDER)):
            axis.text(j, i, str(confusion[i, j]), ha="center", va="center", color="white" if confusion[i, j] > confusion.max() / 2 else "black")
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(reports / "confusion.png", dpi=160)
    plt.close(figure)

    lines = [
        "# 검증 리포트",
        "",
        "> 이 성능과 확률은 실제 경제상태나 미래 연체를 예측하는 값이 아니라, 명시된 의사레이블 규칙을 재현하는 값이다.",
        "",
        "## 1. 유형별 표본과 전체 비율",
        "",
        "| 유형 | 표본 수 | 전체 대비 |",
        "|---|---:|---:|",
    ]
    for code in CLASS_ORDER:
        lines.append(f"| {code} | {label_counts[code]:,} | {label_counts[code] / total:.2%} |")
    lines.extend(["", "## 2. 판정 유보", "", f"- 전체 유보: {int(labels['LABEL'].isna().sum()):,} / {total:,} ({labels['LABEL'].isna().mean():.2%})", "", "| 사유 | 건수 | 전체 대비 |", "|---|---:|---:|"])
    for reason, count in reason_counts.items():
        lines.append(f"| {reason} | {count:,} | {count / total:.2%} |")
    lines.extend(
        [
            "",
            "## 3. 규칙 구조 검사",
            "",
            f"- 두 유형 이상 원시 조건 동시 해당: **{overlap_count:,}건**",
            f"- 어떤 유형 원시 조건에도 해당하지 않음: **{no_match_count:,}건**",
            "- 충돌 조정 로그: " + ("동시 해당가 0건이므로 조건 수정이 필요하지 않았다." if overlap_count == 0 else "동시 해당가 발견되어 조건 수정 전 실패 처리한다."),
            "",
            "## 4. 대표 반례 10개",
            "",
            counter.to_markdown(index=False),
            "",
            "## 5. 민감도",
            "",
        ]
    )
    for name, change, matrix in sensitivity:
        lines.extend([f"### {name}", "", f"- 기준 레이블 대비 변화율: **{change:.2%}**", "", _matrix_markdown(matrix), ""])
    lines.extend(["## 6. 연령대별 유형 집중도", "", age_table.map(lambda value: f"{value:.2%}").to_markdown(), "", "18·20세는 동일한 외부 개인소득/부채 앵커를 공유하며 표본 셀이 작을 수 있으므로 집중도를 별도 확인해야 한다.", "", "## 7. 모델 검증", "", f"- 분할 방식: `{metrics['split_strategy']}`", f"- CV 평균 Macro-F1: **{best['mean_fold_macro_f1']:.4f}**", f"- OOF Macro-F1: **{best['macro_f1']:.4f}**", "", "| 유형 | Recall |", "|---|---:|"])
    for code in CLASS_ORDER:
        lines.append(f"| {code} | {best['class_recall'][code]:.4f} |")
    calibration = metrics["calibration"]
    lines.extend(
        [
            "",
            "Confusion Matrix는 `reports/confusion.png`에 저장했다.",
            "",
            "## 8. OOF 확률 보정",
            "",
            f"- Temperature: `{calibration['temperature']:.6f}`",
            f"- Log Loss: `{calibration['before']['log_loss']:.6f}` → `{calibration['after']['log_loss']:.6f}`",
            f"- Brier Score: `{calibration['before']['brier']:.6f}` → `{calibration['after']['brier']:.6f}`",
            f"- ECE: `{calibration['before']['ece']:.6f}` → `{calibration['after']['ece']:.6f}`",
            "",
            "## 9. 전체 데이터 분위 파라미터",
            "",
            "```json",
            json.dumps(q, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    report_path = reports / "validation.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    if overlap_count:
        raise ValueError(f"Validation found {overlap_count} multi-match rows; revise labeling.py exclusions before accepting results")
    return report_path
