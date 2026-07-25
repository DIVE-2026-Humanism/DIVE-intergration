package com.dive.backend.recommendation.repository;

import com.dive.backend.recommendation.domain.Policy;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface PolicyRepository extends JpaRepository<Policy, Long> {
    @Query("select p from Policy p where p.policyTypeId = :typeId and p.plcyAprvSttsCd = '0044002' order by p.id")
    List<Policy> findApprovedCandidates(@Param("typeId") int typeId);
    List<Policy> findByPlcyNoIn(Collection<String> plcyNos);
}
