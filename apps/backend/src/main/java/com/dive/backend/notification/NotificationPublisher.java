package com.dive.backend.notification;

import java.util.Map;

/**
 * 알림 발송 진입점. 비즈니스 코드는 이 인터페이스만 의존하고, 실제 발송(FCM)은 몰라도 된다.
 * 구현체는 이벤트를 발행할 뿐이며, 실제 전송은 리스너가 비동기로 처리한다.
 *
 * 사용 예:
 *   notificationPublisher.gongguNewParticipant(ownerId, "무선 사무의자");
 *   notificationPublisher.policyDeadlineApproaching(memberId, "청년 월세지원", 3);
 *   notificationPublisher.push(memberId, "제목", "내용", Map.of("type", "custom"));
 */
public interface NotificationPublisher {

    /** 범용 푸시 */
    void push(Long memberId, String title, String body, Map<String, String> data);

    /** 공구 신규 참여 → 등록자에게 "추가 구매 알림" */
    void gongguNewParticipant(Long ownerMemberId, String gongguName);

    /** 관심 정책 마감 임박 → "정책 마감 알림" */
    void policyDeadlineApproaching(Long memberId, String policyTitle, int daysLeft);
}
