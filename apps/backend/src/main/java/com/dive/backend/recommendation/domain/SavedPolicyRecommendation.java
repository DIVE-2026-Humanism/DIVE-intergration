package com.dive.backend.recommendation.domain;

import com.dive.backend.member.domain.Member;
import com.dive.backend.policy.domain.Policy;
import jakarta.persistence.*;
import lombok.Getter;

import java.time.LocalDateTime;

@Entity
@Getter
@Table(name = "saved_policy_recommendation", uniqueConstraints = @UniqueConstraint(name = "uk_saved_recommendation_member_policy", columnNames = {"member_id", "policy_id"}))
public class SavedPolicyRecommendation {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "member_id", nullable = false) private Member member;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "diagnosis_id", nullable = false) private Diagnosis diagnosis;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "policy_id", nullable = false) private Policy policy;
    @Column(nullable = false, length = 500) private String reason;
    @Column(nullable = false, length = 500) private String caution;
    @Column(name = "saved_at", nullable = false, updatable = false) private LocalDateTime savedAt;

    protected SavedPolicyRecommendation() { }

    public SavedPolicyRecommendation(Member member, Diagnosis diagnosis, Policy policy, String reason, String caution) {
        this.member = member;
        this.diagnosis = diagnosis;
        this.policy = policy;
        this.reason = reason;
        this.caution = caution;
        this.savedAt = LocalDateTime.now();
    }
}
