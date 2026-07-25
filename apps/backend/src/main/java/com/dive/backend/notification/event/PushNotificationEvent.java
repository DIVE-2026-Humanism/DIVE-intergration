package com.dive.backend.notification.event;

import java.util.Map;

/**
 * 범용 푸시 알림 이벤트. 특정 도메인 이벤트로 표현하기 애매한 임의 알림에 사용한다.
 * data는 클라이언트가 탭했을 때 라우팅에 쓸 부가정보(예: {"type":"gonggu","id":"12"}).
 */
public record PushNotificationEvent(
        Long memberId,
        String title,
        String body,
        Map<String, String> data
) {
}
