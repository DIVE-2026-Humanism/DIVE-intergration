package com.dive.backend.recommendation.domain;

import com.dive.backend.member.domain.Member;
import jakarta.persistence.*;
import lombok.Getter;

import java.time.LocalDateTime;

@Entity
@Getter
@Table(name = "member_diagnosis")
public class Diagnosis {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "member_id", nullable = false)
    private Member member;
    @Column(name = "policy_type_id", nullable = false) private Integer policyTypeId;
    @Column(name = "total_score", nullable = false) private Integer creditScore;
    @Enumerated(EnumType.STRING) @Column(name = "user_type", nullable = false, length = 12)
    private PolicyType userType;
    @Column(name = "created_at", nullable = false) private LocalDateTime createdAt;

    protected Diagnosis() { }

    public Diagnosis(Member member, int policyTypeId, int creditScore, PolicyType userType) {
        this.member = member;
        this.policyTypeId = policyTypeId;
        this.creditScore = creditScore;
        this.userType = userType;
        this.createdAt = LocalDateTime.now();
    }
}
