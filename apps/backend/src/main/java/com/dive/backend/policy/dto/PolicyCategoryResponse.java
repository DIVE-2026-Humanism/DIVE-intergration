package com.dive.backend.policy.dto;

import java.util.List;

/**
 * 정책 대분류 + 그에 속한 중분류 목록. 프론트 카테고리 필터(대분류 선택 → 중분류) 구성에 사용.
 */
public record PolicyCategoryResponse(
        String lclsfNm,
        List<String> mclsfNms
) {
}
