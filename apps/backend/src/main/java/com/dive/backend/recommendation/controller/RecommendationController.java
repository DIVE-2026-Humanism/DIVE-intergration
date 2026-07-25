package com.dive.backend.recommendation.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.recommendation.dto.DiagnoseRequest;
import com.dive.backend.recommendation.dto.DiagnoseResponse;
import com.dive.backend.recommendation.dto.RecommendationProgressResponse;
import com.dive.backend.recommendation.dto.SavedRecommendationResultDetail;
import com.dive.backend.recommendation.dto.SavedRecommendationResultSummary;
import com.dive.backend.recommendation.service.DiagnoseService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

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

    @GetMapping("/diagnose/progress")
    public ApiResponse<RecommendationProgressResponse> progress(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("추천 생성 상태 조회 성공", diagnoseService.progress(principal.getMemberId()));
    }

    @GetMapping("/recommendations")
    public ApiResponse<DiagnoseResponse> latest(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("최신 추천 조회 성공", diagnoseService.latest(principal.getMemberId()));
    }

    @PostMapping("/recommendations/saved")
    public ApiResponse<SavedRecommendationResultDetail> save(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("추천 결과 저장 완료", diagnoseService.saveRecommendationResult(principal.getMemberId()));
    }

    @GetMapping("/recommendations/saved")
    public ApiResponse<List<SavedRecommendationResultSummary>> saved(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("저장한 추천 결과 조회 성공", diagnoseService.savedRecommendationResults(principal.getMemberId()));
    }

    @GetMapping("/recommendations/saved/{resultId}")
    public ApiResponse<SavedRecommendationResultDetail> savedDetail(@AuthenticationPrincipal PrincipalDetails principal,
                                                                      @PathVariable Long resultId) {
        return ApiResponse.success("저장한 추천 결과 상세 조회 성공", diagnoseService.savedRecommendationResult(principal.getMemberId(), resultId));
    }
}
