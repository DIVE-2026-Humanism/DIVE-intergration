package com.dive.backend.recommendation.repository;

import com.dive.backend.recommendation.domain.Diagnosis;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface DiagnosisRepository extends JpaRepository<Diagnosis, Long> {
    Optional<Diagnosis> findTopByMemberIdOrderByCreatedAtDesc(Long memberId);
}
