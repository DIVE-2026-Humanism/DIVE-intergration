package com.dive.backend.policy.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;


@JsonIgnoreProperties(ignoreUnknown = true)
public record YouthPolicyApiResponse(
        @JsonProperty("resultCode") String resultCode,
        @JsonProperty("resultMessage") String resultMessage,
        @JsonProperty("result") Result result
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Result(
            @JsonProperty("pagging") Pagging pagging,
            @JsonProperty("youthPolicyList") List<YouthPolicyItem> youthPolicyList
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Pagging(
            @JsonProperty("totCount") Integer totCount,
            @JsonProperty("pageNum") Integer pageNum,
            @JsonProperty("pageSize") Integer pageSize
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record YouthPolicyItem(
            @JsonProperty("plcyNo") String plcyNo,
            @JsonProperty("plcyNm") String plcyNm,
            @JsonProperty("plcyKywdNm") String plcyKywdNm,
            @JsonProperty("plcyExplnCn") String plcyExplnCn,
            @JsonProperty("lclsfNm") String lclsfNm,
            @JsonProperty("mclsfNm") String mclsfNm,
            @JsonProperty("plcySprtCn") String plcySprtCn,
            @JsonProperty("plcyAprvSttsCd") String plcyAprvSttsCd,
            @JsonProperty("sprvsnInstCdNm") String sprvsnInstCdNm,
            @JsonProperty("aplyPrdSeCd") String aplyPrdSeCd,
            @JsonProperty("aplyYmd") String aplyYmd,
            @JsonProperty("plcyAplyMthdCn") String plcyAplyMthdCn,
            @JsonProperty("srngMthdCn") String srngMthdCn,
            @JsonProperty("aplyUrlAddr") String aplyUrlAddr,
            @JsonProperty("sbmsnDcmntCn") String sbmsnDcmntCn,
            @JsonProperty("sprtSclCnt") String sprtSclCnt,
            @JsonProperty("sprtTrgtMinAge") String sprtTrgtMinAge,
            @JsonProperty("sprtTrgtMaxAge") String sprtTrgtMaxAge,
            @JsonProperty("sprtTrgtAgeLmtYn") String sprtTrgtAgeLmtYn,
            @JsonProperty("mrgSttsCd") String mrgSttsCd,
            @JsonProperty("earnCndSeCd") String earnCndSeCd,
            @JsonProperty("earnMinAmt") String earnMinAmt,
            @JsonProperty("earnMaxAmt") String earnMaxAmt,
            @JsonProperty("earnEtcCn") String earnEtcCn,
            @JsonProperty("addAplyQlfcCndCn") String addAplyQlfcCndCn,
            @JsonProperty("ptcpPrpTrgtCn") String ptcpPrpTrgtCn,
            @JsonProperty("zipCd") String zipCd,
            @JsonProperty("schoolCd") String schoolCd,
            @JsonProperty("jobCd") String jobCd,
            @JsonProperty("plcyMajorCd") String plcyMajorCd,
            @JsonProperty("inqCnt") String inqCnt,
            @JsonProperty("frstRegDt") String frstRegDt,
            @JsonProperty("lastMdfcnDt") String lastMdfcnDt
    ) {}
}
