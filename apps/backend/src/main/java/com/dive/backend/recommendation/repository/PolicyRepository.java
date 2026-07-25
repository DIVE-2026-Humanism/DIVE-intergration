package com.dive.backend.recommendation.repository;

import com.dive.backend.policy.domain.Policy;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository("recommendationPolicyRepository")
public interface PolicyRepository extends JpaRepository<Policy, Long> {
    /** 사용자 진단 유형과 무관하게, 승인된 모든 정책을 후보로 가져온다. */
    @Query("select p from Policy p where p.plcyAprvSttsCd = '0044002' order by p.id")
    List<Policy> findAllApprovedCandidates();

    List<Policy> findByPlcyNoIn(Collection<String> plcyNos);
}
