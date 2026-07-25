package com.dive.backend.gonggu.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.gonggu.dto.GongguDetailResponse;
import com.dive.backend.gonggu.dto.GongguRequest;
import com.dive.backend.gonggu.dto.GongguResponse;
import com.dive.backend.gonggu.service.GongguService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/v1/gonggu")
@RequiredArgsConstructor
public class GongguController {

    private final GongguService gongguService;

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Long> createGonggu(
            @AuthenticationPrincipal PrincipalDetails principalDetails,
            @Valid @ModelAttribute GongguRequest request,
            @RequestParam(value = "image", required = false) MultipartFile image
    ) {
        return ApiResponse.success("공구 등록 성공", gongguService.create(principalDetails.getMemberId(), request, image));
    }

    @GetMapping("/all")
    public ApiResponse<List<GongguResponse>> getAllGonggu() {
        return ApiResponse.success("조회 성공", gongguService.getAll());
    }

    @GetMapping("/{gongguId}")
    public ApiResponse<GongguDetailResponse> getDetailGonggu(@PathVariable Long gongguId) {
        return ApiResponse.success("조회 성공", gongguService.getDetail(gongguId));
    }

    @PostMapping("/{gongguId}")
    public ApiResponse<Void> likeThisGonggu(
            @PathVariable Long gongguId,
            @AuthenticationPrincipal PrincipalDetails principalDetails
    ) {
        gongguService.likeThisGonggu(gongguId, principalDetails.getMemberId());
        return ApiResponse.success("좋아요 하였습니다!");
    }

    @GetMapping("/myLike")
    public ApiResponse<List<GongguResponse>> getMyLike(@AuthenticationPrincipal PrincipalDetails principalDetails) {
        return ApiResponse.success("내가 좋아요한 공구 조회 성공", gongguService.getMyLike(principalDetails.getMemberId()));
    }
}
