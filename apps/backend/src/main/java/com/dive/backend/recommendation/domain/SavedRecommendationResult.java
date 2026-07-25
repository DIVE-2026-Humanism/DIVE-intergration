package com.dive.backend.recommendation.domain;

import com.dive.backend.member.domain.Member;
import jakarta.persistence.*;
import lombok.Getter;

import java.time.LocalDateTime;

/** 추천 결과 화면 전체를 저장 시점 JSON으로 보관하는 스냅샷. */
@Entity
@Getter
@Table(name = "saved_recommendation_result", uniqueConstraints = @UniqueConstraint(name = "uk_saved_result_member_diagnosis", columnNames = {"member_id", "diagnosis_id"}))
public class SavedRecommendationResult {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "member_id", nullable = false) private Member member;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "diagnosis_id", nullable = false) private Diagnosis diagnosis;
    @Column(length = 150) private String title;
    @Column(name = "result_json", nullable = false, columnDefinition = "TEXT") private String resultJson;
    @Column(name = "saved_at", nullable = false, updatable = false) private LocalDateTime savedAt;

    protected SavedRecommendationResult() { }
    public SavedRecommendationResult(Member member, Diagnosis diagnosis, String title, String resultJson) {
        this.member = member;
        this.diagnosis = diagnosis;
        this.title = title;
        this.resultJson = resultJson;
        this.savedAt = LocalDateTime.now();
    }
}
