package com.dive.backend.policy.scheduler;

import com.dive.backend.policy.service.PolicyPopularityService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class PolicyPopularityScheduler {
    private final PolicyPopularityService policyPopularityService;

    /** 첫 10분을 기다리지 않고 서버 기동 직후에도 랭킹 테이블을 채운다. */
    @EventListener(ApplicationReadyEvent.class)
    public void initialize() {
        refresh();
    }

    /** 매 10분 정각: 최근 30일 조회수(1점) + 좋아요(5점)를 DB 랭킹으로 반영한다. */
    @Scheduled(cron = "0 */10 * * * *")
    public void refresh() {
        try {
            policyPopularityService.refreshRankings();
        } catch (RuntimeException exception) {
            log.error("정책 인기 랭킹 갱신 실패", exception);
        }
    }
}
