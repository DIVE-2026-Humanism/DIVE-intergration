package com.dive.backend.recommendation.domain;

import com.dive.backend.member.domain.Member;
import jakarta.persistence.*;
import lombok.Getter;

@Entity
@Getter
@Table(name = "policy_recommendation")
public class PolicyRecommendation {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "diagnosis_id", nullable = false) private Diagnosis diagnosis;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "member_id", nullable = false) private Member member;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "policy_id", nullable = false) private Policy policy;
    @Column(name = "rank_order", nullable = false) private int rankOrder;
    @Column(nullable = false, length = 500) private String reason;
    @Column(nullable = false, length = 500) private String caution;

    protected PolicyRecommendation() { }

    public PolicyRecommendation(Diagnosis diagnosis, Member member, Policy policy, int rankOrder, String reason, String caution) {
        this.diagnosis = diagnosis;
        this.member = member;
        this.policy = policy;
        this.rankOrder = rankOrder;
        this.reason = reason;
        this.caution = caution;
    }
}
