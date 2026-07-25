package com.dive.backend.recommendation.repository;

import com.dive.backend.policy.domain.Policy;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository("recommendationPolicyRepository")
public interface PolicyRepository extends JpaRepository<Policy, Long> {
    @Query("select p from Policy p where p.policyType.id = :typeId and p.plcyAprvSttsCd = '0044002' order by p.id")
    List<Policy> findApprovedCandidates(@Param("typeId") int typeId);
    List<Policy> findByPlcyNoIn(Collection<String> plcyNos);
}
