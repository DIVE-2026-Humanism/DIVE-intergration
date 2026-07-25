package com.dive.backend.notification.event;

/**
 * 관심 정책의 신청 마감이 임박했을 때 발행. 해당 회원에게 "정책 마감 알림"을 보낸다.
 */
public record PolicyDeadlineApproachingEvent(
        Long memberId,
        String policyTitle,
        int daysLeft
) {
}
