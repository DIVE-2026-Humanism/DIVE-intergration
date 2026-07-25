package com.dive.backend.gonggu.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Pattern;

import java.time.LocalDateTime;

public record GongguRequest(
        @NotBlank String title,
        String content,
        @NotNull @Positive Integer price,
        @NotNull @Positive Integer targetCount,
        LocalDateTime startDate,
        LocalDateTime endDate,
        @Pattern(regexp = "^https?://.+$", message = "상품 링크는 http 또는 https 주소여야 합니다.") String productUrl
) {
}
