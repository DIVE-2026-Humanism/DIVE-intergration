package com.dive.backend.gonggu.client;

import com.fasterxml.jackson.annotation.JsonProperty;

public record KakaoPayApproveRequest(
        @JsonProperty("cid") String cid,
        @JsonProperty("tid") String tid,
        @JsonProperty("partner_order_id") String partnerOrderId,
        @JsonProperty("partner_user_id") String partnerUserId,
        @JsonProperty("pg_token") String pgToken
) {
}
