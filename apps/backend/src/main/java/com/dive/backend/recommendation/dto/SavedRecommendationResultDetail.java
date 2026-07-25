package com.dive.backend.recommendation.dto;

import java.time.LocalDateTime;

public record SavedRecommendationResultDetail(Long id, String title, LocalDateTime savedAt, DiagnoseResponse result) { }
