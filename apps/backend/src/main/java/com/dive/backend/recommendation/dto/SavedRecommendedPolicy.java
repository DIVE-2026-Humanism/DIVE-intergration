package com.dive.backend.recommendation.dto;

import java.time.LocalDateTime;

public record SavedRecommendedPolicy(
        Long policyId,
        String title,
        String category,
        String benefit,
        String reason,
        String caution,
        LocalDateTime savedAt
) { }
