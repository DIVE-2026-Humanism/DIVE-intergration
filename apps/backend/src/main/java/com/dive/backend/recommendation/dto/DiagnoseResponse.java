package com.dive.backend.recommendation.dto;

import com.dive.backend.recommendation.domain.PolicyType;

import java.util.List;

public record DiagnoseResponse(
        int creditScore,
        PolicyType userType,
        String typeLabel,
        AiEconomicReport aiReport,
        List<RecommendedPolicy> recommendations
) {
}
