package com.dive.backend.search.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 회원별 검색 이력. 최신순으로 최대 10개만 유지한다(초과분은 서비스에서 정리).
 * 같은 키워드를 다시 검색하면 기존 항목을 지우고 새로 넣어 맨 위로 올린다.
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "search_history", indexes = @Index(name = "idx_search_member", columnList = "member_id, created_at"))
public class SearchHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "search_history_id")
    private Long id;

    @Column(name = "member_id", nullable = false)
    private Long memberId;

    @Column(nullable = false, length = 100)
    private String keyword;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;
}
