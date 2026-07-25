from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from .config import REQUIRED_COLUMNS, SENTINEL
from .features import build_features


# 신뢰할 수 있는 원본 및 파생변수만 사용한다. 논리 검증에서 제거된 열은 포함하지 않는다.
MODEL_FEATURES = [
    "추정 연소득", "2년전 추정 연소득 금액", "증빙연소득",
    "총자산평가금액(주택)", "현 거주지의 매매가(국토부 실거래가) 또는 공시가격",
    "신용평점", "총대출건수", "신용대출-총대출잔액",
    "주택담보대출-총대출잔액", "정책자금대출-총대출잔액",
    "총 대출 상환금액 (최근 12개월)", "최근 12개월 신용카드소비금액",
    "최근 12개월 체크카드소비금액", "최근 12개월 현금서비스이용금액",
    "대출연체건수", "카드연체건수", "대출연체금액", "카드연체금액",
    "Thin Filer 여부", "파산, 개인회생 신청 여부", "2년내 직장명이력건수",
    "income_trajectory", "jeonse_income_multiple", "pir", "commute_mismatch",
    "dsr", "total_loan_balance", "avg_loan_balance", "consumption_ratio",
    "credit_dependency", "total_delinq_cnt", "delinq_severity",
]

# 앵커는 정답 레이블이 아니다. 학습된 잠재축의 부호(안정/위험 방향)만 정한다.
STABILITY_ANCHOR = {
    "추정 연소득": 1, "증빙연소득": 1, "총자산평가금액(주택)": 1,
    "신용평점": 1, "income_trajectory": 1,
    "dsr": -1, "total_loan_balance": -1, "총대출건수": -1,
    "consumption_ratio": -1, "total_delinq_cnt": -1, "delinq_severity": -1,
    "최근 12개월 현금서비스이용금액": -1, "Thin Filer 여부": -1,
    "파산, 개인회생 신청 여부": -1, "2년내 직장명이력건수": -1,
}

TYPE_NAMES = {
    "E1": "안정형",
    "E2": "주택대출형",
    "E3": "저부채형",
    "E4": "금융이력부족형",
    "E5": "대출부담형",
    "E6": "위기형",
}

TYPE_DESCRIPTIONS = {
    "E1": "소득·신용이 높고 부채·상환·소비 부담이 낮은 안정 군집",
    "E2": "소득과 증빙소득이 높고 주택담보대출 비중이 큰 군집",
    "E3": "대출과 연체가 적고 신용상태가 양호한 저부채 군집",
    "E4": "대출·소비 활동이 적고 Thin Filer 비중이 높은 군집",
    "E5": "다중대출·현금서비스·상환부담이 상대적으로 높은 군집",
    "E6": "연체·DSR·대출건수가 높고 신용점수가 낮은 복합위기 군집",
}


def _percentile_params(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    probs = np.linspace(0, 1, 1001)
    return probs, np.quantile(values, probs)


def _percentile(values: np.ndarray, probs: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    unique, index = np.unique(quantiles, return_index=True)
    return np.interp(values, unique, probs[index] * 100, left=0, right=100)


@dataclass
class LatentEconomicModel:
    seed: int = 42
    n_types: int = 6

    def fit(self, frame: pd.DataFrame) -> "LatentEconomicModel":
        self.features_ = [c for c in MODEL_FEATURES if c in frame]
        x = frame[self.features_].replace([np.inf, -np.inf], np.nan)
        self.imputer_ = SimpleImputer(strategy="median", add_indicator=True)
        self.scaler_ = StandardScaler()
        scaled = self.scaler_.fit_transform(self.imputer_.fit_transform(x))
        self.pca_ = PCA(n_components=.90, svd_solver="full").fit(scaled)
        latent = self.pca_.transform(scaled)

        # 방향만 사전 지식으로 고정하고, 어떤 잠재축을 얼마나 쓸지는 상관구조에서 학습한다.
        anchor_parts = []
        for feature, direction in STABILITY_ANCHOR.items():
            if feature in self.features_:
                column = self.features_.index(feature)
                anchor_parts.append(scaled[:, column] * direction)
        anchor = np.mean(anchor_parts, axis=0)
        # 점수와 유형은 반드시 동일한 잠재공간을 사용한다.
        cluster_dims = min(8, latent.shape[1])
        correlations = np.array([
            np.corrcoef(latent[:, i], anchor)[0, 1] for i in range(cluster_dims)
        ])
        correlations = np.nan_to_num(correlations)
        selected = np.argsort(np.abs(correlations))[-min(5, len(correlations)):]
        weights = correlations[selected]
        weights = weights / np.abs(weights).sum()
        self.score_components_ = selected
        self.score_weights_ = weights
        raw_score = latent[:, selected] @ weights
        self.score_probs_, self.score_quantiles_ = _percentile_params(raw_score)

        self.cluster_scaler_ = StandardScaler().fit(latent[:, :cluster_dims])
        cluster_x = self.cluster_scaler_.transform(latent[:, :cluster_dims])
        self.gmm_ = GaussianMixture(
            n_components=self.n_types, covariance_type="diag", n_init=5,
            reg_covar=1e-5, random_state=self.seed,
        ).fit(cluster_x)
        clusters = self.gmm_.predict(cluster_x)
        alternate = GaussianMixture(
            n_components=self.n_types, covariance_type="diag", n_init=5,
            reg_covar=1e-5, random_state=self.seed + 1,
        ).fit(cluster_x)
        self.gmm_seed_stability_ari_ = float(adjusted_rand_score(clusters, alternate.predict(cluster_x)))
        scores = _percentile(raw_score, self.score_probs_, self.score_quantiles_)
        # E1=가장 안정, E6=가장 취약으로 일관되게 부여한다.
        order = pd.DataFrame({"cluster": clusters, "score": scores}).groupby("cluster").score.mean().sort_values(ascending=False).index
        self.cluster_to_type_ = {int(cluster): f"E{rank}" for rank, cluster in enumerate(order, 1)}
        self.n_cluster_dimensions_ = cluster_dims
        sample_size = min(10_000, len(cluster_x))
        rng = np.random.default_rng(self.seed)
        sample = rng.choice(len(cluster_x), sample_size, replace=False)
        self.train_silhouette_ = float(silhouette_score(cluster_x[sample], clusters[sample]))
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        x = frame[self.features_].replace([np.inf, -np.inf], np.nan)
        scaled = self.scaler_.transform(self.imputer_.transform(x))
        latent = self.pca_.transform(scaled)
        raw_score = latent[:, self.score_components_] @ self.score_weights_
        stability_score = _percentile(raw_score, self.score_probs_, self.score_quantiles_)
        cluster_x = self.cluster_scaler_.transform(latent[:, :self.n_cluster_dimensions_])
        cluster = self.gmm_.predict(cluster_x)
        confidence = self.gmm_.predict_proba(cluster_x).max(axis=1)
        economic_type = pd.Series(cluster).map(self.cluster_to_type_).to_numpy()
        return pd.DataFrame({
            "composite_stability_score": stability_score,
            "economic_type": economic_type,
            "economic_type_name": pd.Series(economic_type).map(TYPE_NAMES).to_numpy(),
            "type_confidence": confidence,
        }, index=frame.index)

    def diagnostics(self) -> dict:
        return {
            "input_feature_count": len(self.features_),
            "input_features": self.features_,
            "pca_components": int(self.pca_.n_components_),
            "pca_explained_variance": float(self.pca_.explained_variance_ratio_.sum()),
            "score_components": self.score_components_.tolist(),
            "score_weights": self.score_weights_.tolist(),
            "gmm_components": self.n_types,
            "train_silhouette": self.train_silhouette_,
            "gmm_seed_stability_ari": self.gmm_seed_stability_ari_,
            "cluster_to_type": self.cluster_to_type_,
        }


@dataclass
class RawLatentEconomicInference:
    """Deployable wrapper: original CSV schema in, score/type/confidence out."""

    latent_model: LatentEconomicModel
    jeonse_artifact: dict
    excluded_columns: list[str]

    def _prepare(self, raw: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in REQUIRED_COLUMNS if column not in raw]
        if missing:
            raise ValueError(f"Required columns missing: {missing}")
        frame = raw[REQUIRED_COLUMNS].copy()
        for column in REQUIRED_COLUMNS:
            numeric = pd.to_numeric(frame[column], errors="coerce")
            frame[column] = numeric.mask(numeric.eq(SENTINEL))
        frame = frame.drop(columns=self.excluded_columns, errors="ignore")
        target = "2년내 현거주지평균전세거래가"
        missing_target = frame[target].isna()
        frame["jeonse_imputed"] = missing_target.astype("int8")
        if missing_target.any():
            if self.jeonse_artifact["method"] == "random_forest":
                from .impute import CAT, NUM
                prediction = self.jeonse_artifact["model"].predict(frame.loc[missing_target, CAT + NUM])
                frame.loc[missing_target, target] = np.maximum(0, prediction)
            else:
                district = self.jeonse_artifact["district_median"]
                global_median = self.jeonse_artifact["global_median"]
                frame.loc[missing_target, target] = (
                    frame.loc[missing_target, "거주지 시군구 코드"].map(district).fillna(global_median)
                )
        return build_features(frame)

    def predict(self, raw: pd.DataFrame) -> pd.DataFrame:
        return self.latent_model.predict(self._prepare(raw))
