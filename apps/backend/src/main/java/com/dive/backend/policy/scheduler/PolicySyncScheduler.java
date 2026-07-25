package com.dive.backend.policy.scheduler;

import com.dive.backend.policy.service.PolicySyncService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class PolicySyncScheduler {

    private final PolicySyncService policySyncService;

    @Scheduled(cron = "0 10 * * * *")
    public void syncDaily() {
        log.info("정책 동기화 스케줄러 시작");
        try {
            policySyncService.syncAll();
        } catch (Exception e) {
            log.error("정책 동기화 실패", e);
        }
    }
}
