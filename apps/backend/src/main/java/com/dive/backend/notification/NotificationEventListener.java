package com.dive.backend.notification;

import com.dive.backend.notification.event.GongguParticipantJoinedEvent;
import com.dive.backend.notification.event.PolicyDeadlineApproachingEvent;
import com.dive.backend.notification.event.PushNotificationEvent;
import com.dive.backend.push.service.FcmService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.Map;

/**
 * 알림 이벤트 → FCM 발송. 트랜잭션이 있으면 커밋 이후에(AFTER_COMMIT), 없으면 즉시
 * (fallbackExecution=true) 실행되며, @Async로 별도 스레드에서 처리해 요청 스레드를 막지 않는다.
 *
 * 트랜잭션 롤백 시에는 알림이 나가지 않는다(원자성). 발송 실패는 로깅만 하고 삼킨다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class NotificationEventListener {

    private final FcmService fcmService;
    private final NotificationService notificationService;
    private final NotificationSettingService settingService;

    @Async("notificationExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    public void on(PushNotificationEvent e) {
        String type = e.data() != null ? e.data().getOrDefault("type", "general") : "general";
        dispatch(e.memberId(), e.title(), e.body(), type, e.data());
    }

    @Async("notificationExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    public void on(GongguParticipantJoinedEvent e) {
        dispatch(e.ownerMemberId(), "추가 구매 알림",
                "등록하신 " + e.gongguName() + " 공구에 새로운 참여자가 생겼어요",
                "gonggu", Map.of("type", "gonggu"));
    }

    @Async("notificationExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    public void on(PolicyDeadlineApproachingEvent e) {
        dispatch(e.memberId(), "정책 마감 알림",
                e.policyTitle() + " 신청 마감이 " + e.daysLeft() + "일 남았어요",
                "policy", Map.of("type", "policy"));
    }

    /** 알림함 저장 + FCM 발송. 각각 독립적으로 실패를 격리한다(저장은 성공, 푸시만 실패 가능). */
    private void dispatch(Long memberId, String title, String body, String type, Map<String, String> data) {
        // 회원의 알림 설정에서 해당 유형이 꺼져 있으면 발송하지 않는다.
        if (!settingService.isEnabled(memberId, type)) {
            log.info("[알림] memberId={} '{}' 유형 수신거부 → 건너뜀", memberId, type);
            return;
        }
        try {
            notificationService.record(memberId, title, body, type);
        } catch (Exception ex) {
            log.error("[알림] memberId={} 저장 중 오류", memberId, ex);
        }
        try {
            int sent = fcmService.sendToMember(memberId, title, body, data);
            log.info("[알림] memberId={} '{}' 저장 완료, 푸시 {}건", memberId, title, sent);
        } catch (Exception ex) {
            log.error("[알림] memberId={} 푸시 발송 중 오류", memberId, ex);
        }
    }
}
