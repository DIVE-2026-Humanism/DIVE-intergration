package com.dive.backend.recommendation.repository;

import com.dive.backend.recommendation.domain.PolicyRecommendation;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface PolicyRecommendationRepository extends JpaRepository<PolicyRecommendation, Long> {
    List<PolicyRecommendation> findByDiagnosisIdOrderByRankOrderAsc(Long diagnosisId);
}
