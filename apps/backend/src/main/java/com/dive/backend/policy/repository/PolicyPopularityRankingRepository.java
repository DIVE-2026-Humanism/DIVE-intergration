package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.PolicyPopularityRanking;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PolicyPopularityRankingRepository extends JpaRepository<PolicyPopularityRanking, Long> {
    Optional<PolicyPopularityRanking> findByPolicy_Id(Long policyId);
    List<PolicyPopularityRanking> findTop10ByOrderByRankOrderAsc();
    void deleteByRankOrderGreaterThan(int rankOrder);
}
