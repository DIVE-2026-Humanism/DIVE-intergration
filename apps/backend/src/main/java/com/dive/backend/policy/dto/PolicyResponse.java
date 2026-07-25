package com.dive.backend.policy.dto;

public record PolicyResponse(
        Long id,
        String plcyNo,
        String plcyNm,
        String plcyKywdNm,
        String plcyExplnCn,
        String plcySprtCn,
        String lclsfNm,
        String mclsfNm,
        String sprvsnInstNm,
        String aplyUrlAddr,
        String aplyPrdSeCd,
        String aplyYmd,
        Integer sprtTrgtMinAge,
        Integer sprtTrgtMaxAge,
        Integer viewCount
) {
}
