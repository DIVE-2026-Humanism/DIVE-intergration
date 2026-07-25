package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.PolicyLike;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.time.LocalDateTime;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface PolicyLikeRepository extends JpaRepository<PolicyLike, Long> {

    Optional<PolicyLike> findByMemberIdAndPolicyId(Long memberId, Long policyId);

    List<PolicyLike> findByMemberId(Long memberId);

    @Query("SELECT pl.policy.id, COUNT(pl) FROM PolicyLike pl WHERE pl.createdAt >= :from GROUP BY pl.policy.id")
    List<Object[]> countByPolicyCreatedAtSince(@Param("from") LocalDateTime from);
}
