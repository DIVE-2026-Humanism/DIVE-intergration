package com.dive.backend.recommendation.dto;

import com.dive.backend.recommendation.domain.PolicyType;
import java.time.LocalDateTime;

public record SavedRecommendationResultSummary(Long id, String title, int creditScore, PolicyType userType, String typeLabel, int policyCount, LocalDateTime savedAt) { }
