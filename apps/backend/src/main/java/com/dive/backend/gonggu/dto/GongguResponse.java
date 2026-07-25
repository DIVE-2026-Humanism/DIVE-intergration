package com.dive.backend.gonggu.dto;

import com.dive.backend.gonggu.domain.Status;

import java.time.LocalDateTime;

public record GongguResponse(
        Long id,
        String title,
        Integer price,
        Integer targetCount,
        Integer currentCount,
        Status status,
        LocalDateTime startDate,
        LocalDateTime endDate,
        String imageUrl
) {
}
