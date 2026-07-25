package com.dive.backend.policy.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 정책 대분류(5개). lclsfNm 값을 실제 온통청년 공식 분류명으로 채워넣을 것.
 */
@Getter
@RequiredArgsConstructor
public enum PolicyLargeCategory {
    CATEGORY_1("일자리"),
    CATEGORY_2("주거"),
    CATEGORY_3("교육"),
    CATEGORY_4("금융･복지･문화"),
    CATEGORY_5("참여권리");

    private final String lclsfNm;
}
