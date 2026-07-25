package com.dive.backend.policy.domain;

import jakarta.persistence.*;
import lombok.Getter;

import java.time.LocalDateTime;

/** 최근 30일 인기도를 10분 단위로 물리화한 조회 전용 랭킹. */
@Entity
@Getter
@Table(name = "policy_popularity_ranking", uniqueConstraints = @UniqueConstraint(name = "uk_policy_popularity_policy", columnNames = "policy_id"))
public class PolicyPopularityRanking {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @OneToOne(fetch = FetchType.LAZY) @JoinColumn(name = "policy_id", nullable = false) private Policy policy;
    @Column(name = "rank_order", nullable = false) private int rankOrder;
    @Column(nullable = false) private long score;
    @Column(name = "view_count_30d", nullable = false) private long viewCount30d;
    @Column(name = "like_count_30d", nullable = false) private long likeCount30d;
    @Column(name = "window_started_at", nullable = false) private LocalDateTime windowStartedAt;
    @Column(name = "calculated_at", nullable = false) private LocalDateTime calculatedAt;

    protected PolicyPopularityRanking() { }

    public PolicyPopularityRanking(Policy policy, int rankOrder, long score, long viewCount30d, long likeCount30d,
                                   LocalDateTime windowStartedAt, LocalDateTime calculatedAt) {
        this.policy = policy;
        update(rankOrder, score, viewCount30d, likeCount30d, windowStartedAt, calculatedAt);
    }

    public void update(int rankOrder, long score, long viewCount30d, long likeCount30d,
                       LocalDateTime windowStartedAt, LocalDateTime calculatedAt) {
        this.rankOrder = rankOrder;
        this.score = score;
        this.viewCount30d = viewCount30d;
        this.likeCount30d = likeCount30d;
        this.windowStartedAt = windowStartedAt;
        this.calculatedAt = calculatedAt;
    }
}
