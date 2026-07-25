package com.dive.backend.recommendation.repository;

import com.dive.backend.policy.domain.PolicyLike;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Collection;
import java.util.List;

@Repository("recommendationPolicyLikeRepository")
public interface PolicyLikeRepository extends JpaRepository<PolicyLike, Long> {
    List<PolicyLike> findByMember_IdAndPolicy_IdIn(Long memberId, Collection<Long> policyIds);
}
