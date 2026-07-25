package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.PolicyType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface PolicyTypeRepository extends JpaRepository<PolicyType, Integer> {

    Optional<PolicyType> findByName(String name);
}
