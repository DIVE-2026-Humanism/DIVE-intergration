package com.dive.backend.policy.dto;

public record PolicyResponse(
        Long id,
        String plcyNo,
        String plcyNm,
        String plcyKywdNm,
        String plcyExplnCn,
        String lclsfNm,
        String mclsfNm,
        String sprvsnInstNm,
        String aplyUrlAddr,
        String aplyPrdSeCd,
        String aplyYmd,
        Integer viewCount
) {
}
