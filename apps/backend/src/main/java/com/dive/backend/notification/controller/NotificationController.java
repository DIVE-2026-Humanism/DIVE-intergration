package com.dive.backend.notification.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.notification.NotificationService;
import com.dive.backend.notification.dto.NotificationResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 인앱 알림함 조회/읽음 처리. 모두 로그인 필요(Bearer).
 */
@RestController
@RequestMapping("/api/v1/members/me/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;

    /** 최신순 알림 목록 (최대 50건) */
    @GetMapping
    public ApiResponse<List<NotificationResponse>> list(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("조회 성공", notificationService.list(principal.getMemberId()));
    }

    /** 안 읽은 알림 개수 (배지용) */
    @GetMapping("/unread-count")
    public ApiResponse<Map<String, Long>> unreadCount(@AuthenticationPrincipal PrincipalDetails principal) {
        long count = notificationService.unreadCount(principal.getMemberId());
        return ApiResponse.success("조회 성공", Map.of("count", count));
    }

    /** 단건 읽음 처리 */
    @PatchMapping("/{id}/read")
    public ApiResponse<Void> read(@AuthenticationPrincipal PrincipalDetails principal, @PathVariable Long id) {
        notificationService.markRead(principal.getMemberId(), id);
        return ApiResponse.success("읽음 처리 완료");
    }

    /** 전체 읽음 처리 */
    @PatchMapping("/read-all")
    public ApiResponse<Void> readAll(@AuthenticationPrincipal PrincipalDetails principal) {
        notificationService.markAllRead(principal.getMemberId());
        return ApiResponse.success("전체 읽음 처리 완료");
    }
}
