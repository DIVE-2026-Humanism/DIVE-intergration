package com.dive.backend.recommendation.service;

import com.dive.backend.recommendation.domain.PolicyType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class PolicyTypeResolverTest {
    private final PolicyTypeResolver resolver = new PolicyTypeResolver();

    @Test
    void classifiesBoundaryScores() {
        assertEquals(PolicyType.VULNERABLE, resolver.resolve(0));
        assertEquals(PolicyType.VULNERABLE, resolver.resolve(50));
        assertEquals(PolicyType.STABLE, resolver.resolve(51));
        assertEquals(PolicyType.STABLE, resolver.resolve(100));
    }
}
