package com.dive.backend.gonggu.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.gonggu.dto.KakaoPayReadyResult;
import com.dive.backend.gonggu.service.GongguPaymentService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/gonggu/payment")
@RequiredArgsConstructor
public class GongguPaymentController {

    private final GongguPaymentService gongguPaymentService;

    @PostMapping("/{gongguId}/ready")
    public ApiResponse<KakaoPayReadyResult> ready(
            @PathVariable Long gongguId,
            @AuthenticationPrincipal PrincipalDetails principalDetails
    ) {
        return ApiResponse.success("결제 준비 완료", gongguPaymentService.ready(gongguId, principalDetails.getMemberId()));
    }

    /** 카카오페이 결제 승인 후 사용자 브라우저가 리다이렉트되어 오는 콜백 (인증 헤더 없이 호출됨) */
    @GetMapping("/approve")
    public ApiResponse<Void> approve(
            @RequestParam Long paymentId,
            @RequestParam("pg_token") String pgToken
    ) {
        gongguPaymentService.approve(paymentId, pgToken);
        return ApiResponse.success("결제가 완료되었습니다.");
    }

    @GetMapping("/cancel")
    public ApiResponse<Void> cancel(@RequestParam Long paymentId) {
        gongguPaymentService.cancel(paymentId);
        return ApiResponse.success("결제가 취소되었습니다.");
    }

    @GetMapping("/fail")
    public ApiResponse<Void> fail(@RequestParam Long paymentId) {
        gongguPaymentService.fail(paymentId);
        return ApiResponse.success("결제에 실패했습니다.");
    }
}
