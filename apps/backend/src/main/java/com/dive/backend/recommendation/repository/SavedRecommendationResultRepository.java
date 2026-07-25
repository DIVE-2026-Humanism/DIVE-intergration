package com.dive.backend.recommendation.repository;

import com.dive.backend.recommendation.domain.SavedRecommendationResult;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SavedRecommendationResultRepository extends JpaRepository<SavedRecommendationResult, Long> {
    Optional<SavedRecommendationResult> findByMember_IdAndDiagnosis_Id(Long memberId, Long diagnosisId);
    Optional<SavedRecommendationResult> findByIdAndMember_Id(Long id, Long memberId);
    List<SavedRecommendationResult> findByMember_IdOrderBySavedAtDesc(Long memberId);
}
