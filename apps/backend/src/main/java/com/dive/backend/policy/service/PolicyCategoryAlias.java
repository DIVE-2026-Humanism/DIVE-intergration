package com.dive.backend.policy.service;

import java.util.List;
import java.util.Map;

/**
 * 온통청년 API의 정책 대분류(lclsfNm)가 신/구 명칭 혼용으로 내려오는 경우가 있어
 * (예: "복지문화" ↔ "금융･복지･문화") 같은 의미의 이름을 하나의 검색 조건으로 묶어준다.
 * 새로운 신/구 명칭 쌍이 발견되면 여기에 추가한다.
 */
public final class PolicyCategoryAlias {

    private static final Map<String, List<String>> LARGE_CATEGORY_ALIASES = Map.of(
            "복지문화", List.of("복지문화", "금융･복지･문화"),
            "교육", List.of("교육", "교육･직업훈련"),
            "참여권리", List.of("참여권리", "참여･기반")
    );

    private static final Map<String, List<String>> MEDIUM_CATEGORY_ALIASES = Map.of(
            "온라인교육", List.of("온라인교육", "온·오프라인교육")
    );

    private PolicyCategoryAlias() {
    }

    /** 입력값과 같은 의미로 취급할 대분류 이름들(본인 포함)을 반환한다. 별칭이 없으면 입력값 그대로 하나만 반환. */
    public static List<String> resolveLclsfNm(String lclsfNm) {
        return LARGE_CATEGORY_ALIASES.getOrDefault(lclsfNm, List.of(lclsfNm));
    }

    /** 입력값과 같은 의미로 취급할 중분류 이름들(본인 포함)을 반환한다. 별칭이 없으면 입력값 그대로 하나만 반환. */
    public static List<String> resolveMclsfNm(String mclsfNm) {
        return MEDIUM_CATEGORY_ALIASES.getOrDefault(mclsfNm, List.of(mclsfNm));
    }
}
