package com.dive.backend.gonggu.client;

import com.fasterxml.jackson.annotation.JsonProperty;

public record KakaoPayCancelRequest(
        @JsonProperty("cid") String cid,
        @JsonProperty("tid") String tid,
        @JsonProperty("cancel_amount") Integer cancelAmount,
        @JsonProperty("cancel_tax_free_amount") Integer cancelTaxFreeAmount
) {
}
