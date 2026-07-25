package com.dive.backend.policy.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 정책 중분류(17개). mclsfNm 값을 실제 온통청년 공식 분류명으로 채워넣을 것.
 */
@Getter
@RequiredArgsConstructor
public enum PolicyMediumCategory {
    CATEGORY_1("취업"),
    CATEGORY_2("재직자"),
    CATEGORY_3("창업"),
    CATEGORY_4("주택 및 거주지"),
    CATEGORY_5("기숙사"),
    CATEGORY_6("전월세 및 주거급여 지원"),
    CATEGORY_7("미래역량강화"),
    CATEGORY_8("교육비지원"),
    CATEGORY_9("온라인교육"),
    CATEGORY_10("취약계층 및 금융지원"),
    CATEGORY_11("건강"),
    CATEGORY_12("예술인지원"),
    CATEGORY_13("문화활동"),
    CATEGORY_14("청년참여"),
    CATEGORY_15("정책인프라구축"),
    CATEGORY_16("청년국제교류"),
    CATEGORY_17("권익보호");

    private final String mclsfNm;
}
