package com.dive.backend.policy.dto;

import java.time.LocalDateTime;

public record PolicyDetailResponse(
        Long id,
        String plcyNo,
        String plcyNm,
        String plcyKywdNm,
        String plcyExplnCn,
        String lclsfNm,
        String mclsfNm,
        String plcySprtCn,
        String sprvsnInstNm,
        String aplyPrdSeCd,
        String aplyYmd,
        String plcyAplyMthdCn,
        String srngMthdCn,
        String aplyUrlAddr,
        String sbmsnDcmntCn,
        String sprtSclCnt,
        Integer sprtTrgtMinAge,
        Integer sprtTrgtMaxAge,
        String sprtTrgtAgeLmtYn,
        String mrgSttsCd,
        String earnCndSeCd,
        String earnMinAmt,
        String earnMaxAmt,
        String earnEtcCn,
        String addAplyQlfcCndCn,
        String ptcpPrpTrgtCn,
        String zipCd,
        String schoolCd,
        String jobCd,
        String plcyMajorCd,
        Integer viewCount,
        LocalDateTime srcRegDt,
        LocalDateTime srcMdfcnDt
) {
}
