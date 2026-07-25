package com.dive.backend.policy.service;

import com.dive.backend.policy.domain.Policy;
import com.dive.backend.policy.domain.PolicyPopularityRanking;
import com.dive.backend.policy.repository.PolicyLikeRepository;
import com.dive.backend.policy.repository.PolicyPopularityRankingRepository;
import com.dive.backend.policy.repository.PolicyRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.*;

/**
 * 조회 이벤트는 Redis ZSET의 timestamp score로 보관해 정확한 최근 30일 슬라이딩 윈도우를 만든다.
 * 좋아요는 DB의 현재 유효 좋아요 중 30일 이내 생성분만 반영한다. 최종 결과는 DB 랭킹 테이블로 물리화한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PolicyPopularityService {
    private static final String VIEW_EVENTS_KEY = "policy:popularity:view-events";
    private static final Duration WINDOW = Duration.ofDays(30);
    private static final int LIKE_WEIGHT = 5;
    private static final int RANK_LIMIT = 10;

    private final StringRedisTemplate stringRedisTemplate;
    private final PolicyRepository policyRepository;
    private final PolicyLikeRepository policyLikeRepository;
    private final PolicyPopularityRankingRepository rankingRepository;

    /** 정책 상세 조회 시 호출한다. Redis 장애가 사용자 상세 조회를 막지 않도록 실패는 기록만 한다. */
    public void recordView(Long policyId) {
        try {
            long now = Instant.now().toEpochMilli();
            String event = policyId + ":" + UUID.randomUUID();
            stringRedisTemplate.opsForZSet().add(VIEW_EVENTS_KEY, event, now);
            stringRedisTemplate.expire(VIEW_EVENTS_KEY, WINDOW.plusDays(1));
        } catch (RuntimeException exception) {
            log.warn("정책 조회 이벤트 Redis 저장 실패 (policyId={})", policyId, exception);
        }
    }

    @Transactional
    public void refreshRankings() {
        Instant now = Instant.now();
        Instant from = now.minus(WINDOW);
        Map<Long, Long> views = viewsSince(from);
        Map<Long, Long> likes = likesSince(LocalDateTime.ofInstant(from, ZoneOffset.UTC));

        Set<Long> candidateIds = new HashSet<>(views.keySet());
        candidateIds.addAll(likes.keySet());
        if (candidateIds.isEmpty()) {
            rankingRepository.deleteAllInBatch();
            return;
        }

        List<Score> top = candidateIds.stream()
                .map(id -> new Score(id, views.getOrDefault(id, 0L), likes.getOrDefault(id, 0L)))
                .sorted(Comparator.comparingLong(Score::score).reversed().thenComparing(Score::policyId))
                .limit(RANK_LIMIT)
                .toList();

        LocalDateTime calculatedAt = LocalDateTime.now();
        LocalDateTime windowStartedAt = LocalDateTime.ofInstant(from, ZoneOffset.UTC);
        int rank = 1;
        for (Score score : top) {
            Policy policy = policyRepository.findById(score.policyId()).orElse(null);
            if (policy == null) continue;
            int currentRank = rank++;
            PolicyPopularityRanking ranking = rankingRepository.findByPolicy_Id(policy.getId())
                    .orElseGet(() -> new PolicyPopularityRanking(policy, currentRank, score.score(), score.views(), score.likes(), windowStartedAt, calculatedAt));
            ranking.update(currentRank, score.score(), score.views(), score.likes(), windowStartedAt, calculatedAt);
            rankingRepository.save(ranking);
        }
        rankingRepository.deleteByRankOrderGreaterThan(top.size());
        log.info("정책 인기 랭킹 갱신 완료: {}건, 기간={}~{}", top.size(), windowStartedAt, calculatedAt);
    }

    @Transactional(readOnly = true)
    public List<Long> topPolicyIds() {
        return rankingRepository.findTop10ByOrderByRankOrderAsc().stream().map(ranking -> ranking.getPolicy().getId()).toList();
    }

    private Map<Long, Long> viewsSince(Instant from) {
        try {
            long cutoff = from.toEpochMilli();
            stringRedisTemplate.opsForZSet().removeRangeByScore(VIEW_EVENTS_KEY, 0, cutoff - 1);
            Set<ZSetOperations.TypedTuple<String>> events = stringRedisTemplate.opsForZSet()
                    .rangeByScoreWithScores(VIEW_EVENTS_KEY, cutoff, Double.MAX_VALUE);
            if (events == null) return Map.of();
            Map<Long, Long> result = new HashMap<>();
            for (ZSetOperations.TypedTuple<String> event : events) {
                if (event.getValue() == null) continue;
                int separator = event.getValue().indexOf(':');
                if (separator < 1) continue;
                try {
                    long policyId = Long.parseLong(event.getValue().substring(0, separator));
                    result.merge(policyId, 1L, Long::sum);
                } catch (NumberFormatException ignored) { }
            }
            return result;
        } catch (RuntimeException exception) {
            log.warn("정책 조회수 Redis 집계 실패. 좋아요 점수만으로 랭킹을 계산합니다.", exception);
            return Map.of();
        }
    }

    private Map<Long, Long> likesSince(LocalDateTime from) {
        Map<Long, Long> result = new HashMap<>();
        for (Object[] row : policyLikeRepository.countByPolicyCreatedAtSince(from)) {
            result.put((Long) row[0], ((Number) row[1]).longValue());
        }
        return result;
    }

    private record Score(Long policyId, long views, long likes) {
        long score() { return views + likes * LIKE_WEIGHT; }
    }
}
