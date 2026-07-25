package com.dive.backend.notification.dto;

import com.dive.backend.notification.domain.NotificationSetting;

public record NotificationSettingResponse(
        boolean gonggu,
        boolean policy,
        boolean marketing
) {
    public static NotificationSettingResponse from(NotificationSetting s) {
        return new NotificationSettingResponse(s.isGonggu(), s.isPolicy(), s.isMarketing());
    }
}
