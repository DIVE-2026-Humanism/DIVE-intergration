package com.dive.backend.gonggu.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record KakaoPayCancelResponse(
        @JsonProperty("aid") String aid,
        @JsonProperty("tid") String tid,
        @JsonProperty("cid") String cid,
        @JsonProperty("status") String status,
        @JsonProperty("canceled_at") String canceledAt
) {
}
