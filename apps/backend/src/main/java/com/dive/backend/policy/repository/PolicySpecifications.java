package com.dive.backend.policy.repository;

import com.dive.backend.policy.domain.Policy;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.jpa.domain.Specification;

import java.util.List;

public final class PolicySpecifications {

    private PolicySpecifications() {
    }

    /** candidates 중 하나라도 lclsfNm에 부분포함되면 매치(OR) — 신/구 분류명 별칭 처리용 */
    public static Specification<Policy> lclsfNmIn(List<String> candidates) {
        return (root, query, cb) -> {
            Predicate[] predicates = candidates.stream()
                    .map(candidate -> cb.like(root.get("lclsfNm"), "%" + candidate + "%"))
                    .toArray(Predicate[]::new);
            return cb.or(predicates);
        };
    }

    /** candidates 중 하나라도 mclsfNm에 부분포함되면 매치(OR) — 별칭 처리용 */
    public static Specification<Policy> mclsfNmIn(List<String> candidates) {
        return (root, query, cb) -> {
            Predicate[] predicates = candidates.stream()
                    .map(candidate -> cb.like(root.get("mclsfNm"), "%" + candidate + "%"))
                    .toArray(Predicate[]::new);
            return cb.or(predicates);
        };
    }
}
