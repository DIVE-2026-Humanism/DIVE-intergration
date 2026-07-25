package com.dive.backend.push.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.notification.NotificationPublisher;
import com.dive.backend.push.dto.PushTokenRequest;
import com.dive.backend.push.service.FcmService;
import com.dive.backend.push.service.PushTokenService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * FCM 디바이스 토큰 등록/해제 및 테스트 발송. 모두 로그인 필요(Bearer).
 */
@RestController
@RequestMapping("/api/v1/members/me/push-token")
@RequiredArgsConstructor
public class PushController {

    private final PushTokenService pushTokenService;
    private final FcmService fcmService;
    private final NotificationPublisher notificationPublisher;

    /** 앱 로그인 후 발급받은 FCM 토큰 등록/갱신 */
    @PostMapping
    public ApiResponse<Void> register(
            @AuthenticationPrincipal PrincipalDetails principal,
            @Valid @RequestBody PushTokenRequest request) {
        pushTokenService.register(principal.getMemberId(), request.token(), request.platform());
        return ApiResponse.success("푸시 토큰 등록 완료");
    }

    /** 로그아웃/알림 끄기 시 토큰 해제 */
    @DeleteMapping
    public ApiResponse<Void> unregister(@Valid @RequestBody PushTokenRequest request) {
        pushTokenService.unregister(request.token());
        return ApiResponse.success("푸시 토큰 해제 완료");
    }

    /** 연동 확인용(동기) — 내 모든 기기로 즉시 발송하고 성공 건수를 반환 */
    @PostMapping("/test")
    public ApiResponse<Integer> test(@AuthenticationPrincipal PrincipalDetails principal) {
        int sent = fcmService.sendToMember(
                principal.getMemberId(),
                "잡공구 테스트 알림",
                "FCM 연동에 성공했어요! 🎉",
                Map.of("type", "test"));
        return ApiResponse.success("테스트 발송 완료 (성공 " + sent + "건)", sent);
    }

    /** 이벤트 방식 확인용 — 이벤트만 발행하고 즉시 반환(실제 발송은 리스너가 비동기 처리) */
    @PostMapping("/test-event")
    public ApiResponse<Void> testEvent(@AuthenticationPrincipal PrincipalDetails principal) {
        notificationPublisher.gongguNewParticipant(principal.getMemberId(), "무선 사무의자");
        return ApiResponse.success("알림 이벤트 발행 완료 (발송은 비동기 처리)");
    }
}
