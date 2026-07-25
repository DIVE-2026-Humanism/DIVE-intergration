package com.dive.backend.recommendation.dto;

public record RecommendedPolicy(
        Long policyId,
        String plcyNo,
        String plcyNm,
        String lclsfNm,
        String benefit,
        String reason,
        String caution,
        boolean liked
) {
}
