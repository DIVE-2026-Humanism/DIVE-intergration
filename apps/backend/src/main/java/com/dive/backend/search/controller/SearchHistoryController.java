package com.dive.backend.search.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.global.security.PrincipalDetails;
import com.dive.backend.search.SearchHistoryService;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 검색 이력(최근 검색어, 최대 10개). 로그인 필요(Bearer).
 */
@RestController
@RequestMapping("/api/v1/members/me/search-history")
@RequiredArgsConstructor
public class SearchHistoryController {

    private final SearchHistoryService service;

    /** 최근 검색어 목록(최신순, 최대 10) */
    @GetMapping
    public ApiResponse<List<String>> list(@AuthenticationPrincipal PrincipalDetails principal) {
        return ApiResponse.success("조회 성공", service.list(principal.getMemberId()));
    }

    /** 검색어 기록 */
    @PostMapping
    public ApiResponse<Void> add(
            @AuthenticationPrincipal PrincipalDetails principal,
            @RequestBody SearchKeywordRequest request) {
        service.add(principal.getMemberId(), request.keyword());
        return ApiResponse.success("검색어 저장 완료");
    }

    /** keyword 있으면 단건 삭제, 없으면 전체 삭제 */
    @DeleteMapping
    public ApiResponse<Void> delete(
            @AuthenticationPrincipal PrincipalDetails principal,
            @RequestParam(required = false) String keyword) {
        if (keyword != null && !keyword.isBlank()) {
            service.remove(principal.getMemberId(), keyword);
            return ApiResponse.success("검색어 삭제 완료");
        }
        service.clear(principal.getMemberId());
        return ApiResponse.success("검색 이력 전체 삭제 완료");
    }

    public record SearchKeywordRequest(@NotBlank String keyword) {
    }
}
