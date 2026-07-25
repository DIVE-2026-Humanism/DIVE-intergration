package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.Policy;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface PolicyRepository extends JpaRepository<Policy, Long>, JpaSpecificationExecutor<Policy> {

    Optional<Policy> findByPlcyNo(String plcyNo);

    /** 좋아요 많은 순, 동점(좋아요 0 포함)이면 최신 등록순 */
    @Query("""
            SELECT p.id
            FROM Policy p
            LEFT JOIN PolicyLike pl ON pl.policy = p
            GROUP BY p.id, p.createdAt
            ORDER BY COUNT(pl) DESC, p.createdAt DESC
            """)
    List<Long> findByTopLike(Pageable pageable);
}
