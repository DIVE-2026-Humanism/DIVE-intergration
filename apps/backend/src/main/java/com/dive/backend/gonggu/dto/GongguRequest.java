package com.dive.backend.gonggu.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.time.LocalDateTime;

public record GongguRequest(
        @NotBlank String title,
        String content,
        @NotNull @Positive Integer price,
        @NotNull @Positive Integer targetCount,
        LocalDateTime startDate,
        LocalDateTime endDate
) {
}
