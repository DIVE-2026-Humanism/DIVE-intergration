package com.dive.backend.recommendation.llm;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "recommendation")
public record RecommendationProperties(int candidateLimit, int resultCount, int stablePolicyTypeId, int vulnerablePolicyTypeId) { }
