package com.dive.backend.gonggu.dto;

import com.dive.backend.gonggu.domain.Status;

import java.time.LocalDateTime;

public record GongguDetailResponse(
        Long id,
        String writerNickname,
        String title,
        String content,
        Integer price,
        Integer targetCount,
        Integer currentCount,
        Status status,
        LocalDateTime startDate,
        LocalDateTime endDate,
        String imageUrl,
        String productUrl,
        LocalDateTime createdAt
) {
}
