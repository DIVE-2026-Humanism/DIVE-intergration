package com.dive.backend.recommendation.llm;

import com.dive.backend.recommendation.domain.Policy;
import com.dive.backend.recommendation.domain.PolicyType;
import com.dive.backend.recommendation.dto.UserInputsOverride;

import java.util.List;

public interface PolicyReranker {
    List<LlmRecommendation> recommend(PolicyType type, int creditScore, UserInputsOverride profile, List<Policy> candidates);
}
