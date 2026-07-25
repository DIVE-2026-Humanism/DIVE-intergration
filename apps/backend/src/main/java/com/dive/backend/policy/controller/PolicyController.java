package com.dive.backend.policy.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.policy.dto.PolicyDetailResponse;
import com.dive.backend.policy.dto.PolicyResponse;
import com.dive.backend.policy.service.PolicyService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/policy")
@RequiredArgsConstructor
public class PolicyController {

    private final PolicyService policyService;

    @GetMapping("/all")
    public ApiResponse<List<PolicyResponse>> getAllPolicies(
            @AuthenticationPrincipal PrincipalDetails principalDetails,
            @RequestParam(required = false) String lclsfNm,
            @RequestParam(required = false) String mclsfNm
    ) {
        return ApiResponse.success("조회 성공", policyService.getAll(lclsfNm, mclsfNm));
    }

    @GetMapping("/{plcyId}")
    public ApiResponse<PolicyDetailResponse> getDetailPolicy(@PathVariable Long plcyId) {
        return ApiResponse.success("조회 성공", policyService.getDetail(plcyId));
    }

    @PostMapping("/{plcyId}")
    public ApiResponse<Void> likeThisPolicy(
            @PathVariable Long plcyId,
            @AuthenticationPrincipal PrincipalDetails principalDetails                                ) {
        policyService.likeThisPolicy(plcyId, principalDetails.getMemberId());
        return ApiResponse.success("좋아요 하였습니다!");
    }

    @GetMapping("/myLike")
    public ApiResponse<List<PolicyResponse>> getMyLike(@AuthenticationPrincipal PrincipalDetails principalDetails) {
        return ApiResponse.success("내가 좋아한 정책들 조회 성공", policyService.getMyLike(principalDetails.getMemberId()));
    }
}
