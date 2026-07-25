package com.dive.backend.notification.dto;

/**
 * 부분 업데이트 요청. 변경할 항목만 보내면 되고, null인 항목은 유지된다.
 */
public record NotificationSettingRequest(
        Boolean gonggu,
        Boolean policy,
        Boolean marketing
) {
}
