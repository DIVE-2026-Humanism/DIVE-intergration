package com.dive.backend.notification.event;

/**
 * 내가 등록한 공구에 새로운 참여자가 생겼을 때 발행. 공구 등록자에게 "추가 구매 알림"을 보낸다.
 */
public record GongguParticipantJoinedEvent(
        Long ownerMemberId,
        String gongguName
) {
}
