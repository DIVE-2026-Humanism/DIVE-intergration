package com.dive.backend.recommendation.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.recommendation.dto.DiagnoseRequest;
import com.dive.backend.recommendation.dto.DiagnoseResponse;
import com.dive.backend.recommendation.service.DiagnoseService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class RecommendationController {
    private final DiagnoseService diagnoseService;

    @PostMapping("/diagnose")
    public ApiResponse<DiagnoseResponse> diagnose(@AuthenticationPrincipal PrincipalDetails principal, @Valid @RequestBody DiagnoseRequest request) {
        // KCB 원본은 민감정보이므로 로깅하지 않는다.
        log.info("Diagnose request received (memberId={})", principal.getMemberId());
        return ApiResponse.success("정책 추천 완료", diagnoseService.diagnose(principal.getMemberId(), request));
    }

    @GetMapping("/recommendations")
    public ApiResponse<DiagnoseResponse> latest(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("최신 추천 조회 성공", diagnoseService.latest(principal.getMemberId()));
    }
}
