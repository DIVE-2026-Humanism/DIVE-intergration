package com.dive.backend.recommendation.repository;

import com.dive.backend.recommendation.domain.PolicyLike;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Collection;
import java.util.List;

public interface PolicyLikeRepository extends JpaRepository<PolicyLike, Long> {
    List<PolicyLike> findByMemberIdAndPolicyIdIn(Long memberId, Collection<Long> policyIds);
}
