package com.dive.backend.recommendation.repository;

import com.dive.backend.recommendation.domain.SavedPolicyRecommendation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SavedPolicyRecommendationRepository extends JpaRepository<SavedPolicyRecommendation, Long> {
    boolean existsByMember_IdAndPolicy_Id(Long memberId, Long policyId);
    List<SavedPolicyRecommendation> findByMember_IdOrderBySavedAtDesc(Long memberId);
}
