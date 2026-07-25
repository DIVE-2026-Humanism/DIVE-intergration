package com.dive.backend.kcb.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.kcb.domain.KcbConnection;
import com.dive.backend.kcb.service.KcbConnectionService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/kcb")
@RequiredArgsConstructor
public class KcbConnectionController {
    private final KcbConnectionService kcbConnectionService;

    @PostMapping("/connect")
    public ApiResponse<Response> connect(@AuthenticationPrincipal PrincipalDetails principal) {
        KcbConnection saved = kcbConnectionService.connectDummy(principal.getMemberId());
        return ApiResponse.success("더미 KCB 정보 연동 완료", new Response(saved.getId(), saved.getCreatedAt(), saved.isDummy()));
    }
    public record Response(Long id, java.time.LocalDateTime createdAt, boolean dummy) {}
}
