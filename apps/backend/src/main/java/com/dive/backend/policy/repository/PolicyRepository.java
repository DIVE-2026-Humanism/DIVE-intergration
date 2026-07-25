package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.Policy;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.Optional;

public interface PolicyRepository extends JpaRepository<Policy, Long>, JpaSpecificationExecutor<Policy> {

    Optional<Policy> findByPlcyNo(String plcyNo);
}
