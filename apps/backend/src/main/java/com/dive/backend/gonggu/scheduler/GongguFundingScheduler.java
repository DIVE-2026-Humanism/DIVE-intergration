package com.dive.backend.gonggu.scheduler;

import com.dive.backend.gonggu.service.GongguPaymentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class GongguFundingScheduler {

    private final GongguPaymentService gongguPaymentService;

    /** 매시 정각, 마감 지났는데 목표 인원 미달인 공구를 펀딩 실패 처리하고 결제 건 환불 */
    @Scheduled(cron = "0 0 * * * *")
    public void checkExpiredFundings() {
        log.info("공구 마감 체크 스케줄러 시작");
        try {
            gongguPaymentService.processExpiredFundings();
        } catch (Exception e) {
            log.error("공구 마감 처리 실패", e);
        }
    }
}
