package com.dive.backend.gonggu.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record KakaoPayApproveResponse(
        @JsonProperty("aid") String aid,
        @JsonProperty("tid") String tid,
        @JsonProperty("cid") String cid,
        @JsonProperty("partner_order_id") String partnerOrderId,
        @JsonProperty("partner_user_id") String partnerUserId,
        @JsonProperty("payment_method_type") String paymentMethodType,
        @JsonProperty("amount") Amount amount,
        @JsonProperty("approved_at") String approvedAt
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Amount(
            @JsonProperty("total") Integer total,
            @JsonProperty("tax_free") Integer taxFree,
            @JsonProperty("vat") Integer vat,
            @JsonProperty("point") Integer point,
            @JsonProperty("discount") Integer discount
    ) {
    }
}
