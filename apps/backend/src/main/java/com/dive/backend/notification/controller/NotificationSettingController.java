package com.dive.backend.notification.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.notification.NotificationSettingService;
import com.dive.backend.notification.dto.NotificationSettingRequest;
import com.dive.backend.notification.dto.NotificationSettingResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

/**
 * 알림 수신 설정 조회/변경. 로그인 필요(Bearer).
 */
@RestController
@RequestMapping("/api/v1/members/me/notification-settings")
@RequiredArgsConstructor
public class NotificationSettingController {

    private final NotificationSettingService settingService;

    @GetMapping
    public ApiResponse<NotificationSettingResponse> get(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("조회 성공", settingService.get(principal.getMemberId()));
    }

    /** 부분 업데이트 — 변경한 토글만 보내면 됨 */
    @PatchMapping
    public ApiResponse<NotificationSettingResponse> update(
            @AuthenticationPrincipal PrincipalDetails principal,
            @RequestBody NotificationSettingRequest request) {
        return ApiResponse.success("저장 완료", settingService.update(principal.getMemberId(), request));
    }
}
