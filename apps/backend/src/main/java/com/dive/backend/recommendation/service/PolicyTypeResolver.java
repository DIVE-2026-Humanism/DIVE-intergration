package com.dive.backend.recommendation.service;

import com.dive.backend.recommendation.domain.PolicyType;
import org.springframework.stereotype.Component;

@Component
public class PolicyTypeResolver {

    public PolicyType resolve(int creditScore) {
        return creditScore <= 50 ? PolicyType.VULNERABLE : PolicyType.STABLE;
    }
}
