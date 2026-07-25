package com.dive.backend.notification;

import com.dive.backend.notification.event.GongguParticipantJoinedEvent;
import com.dive.backend.notification.event.PolicyDeadlineApproachingEvent;
import com.dive.backend.notification.event.PushNotificationEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Spring ApplicationEvent 기반 구현. 발송 요청을 이벤트로 던지기만 한다.
 * 실제 전송은 NotificationEventListener가 트랜잭션 커밋 이후 비동기로 수행하므로,
 * 알림 발송이 비즈니스 트랜잭션을 느리게 하거나 실패시키지 않는다.
 */
@Component
@RequiredArgsConstructor
public class SpringNotificationPublisher implements NotificationPublisher {

    private final ApplicationEventPublisher eventPublisher;

    @Override
    public void push(Long memberId, String title, String body, Map<String, String> data) {
        eventPublisher.publishEvent(new PushNotificationEvent(memberId, title, body, data));
    }

    @Override
    public void gongguNewParticipant(Long ownerMemberId, String gongguName) {
        eventPublisher.publishEvent(new GongguParticipantJoinedEvent(ownerMemberId, gongguName));
    }

    @Override
    public void policyDeadlineApproaching(Long memberId, String policyTitle, int daysLeft) {
        eventPublisher.publishEvent(new PolicyDeadlineApproachingEvent(memberId, policyTitle, daysLeft));
    }
}
