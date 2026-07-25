package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.PolicyLike;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PolicyLikeRepository extends JpaRepository<PolicyLike, Long> {

    Optional<PolicyLike> findByMemberIdAndPolicyId(Long memberId, Long policyId);

    List<PolicyLike> findByMemberId(Long memberId);
}
