package com.dive.backend.gonggu.client;

import com.fasterxml.jackson.annotation.JsonProperty;

public record KakaoPayReadyRequest(
        @JsonProperty("cid") String cid,
        @JsonProperty("partner_order_id") String partnerOrderId,
        @JsonProperty("partner_user_id") String partnerUserId,
        @JsonProperty("item_name") String itemName,
        @JsonProperty("quantity") Integer quantity,
        @JsonProperty("total_amount") Integer totalAmount,
        @JsonProperty("tax_free_amount") Integer taxFreeAmount,
        @JsonProperty("approval_url") String approvalUrl,
        @JsonProperty("cancel_url") String cancelUrl,
        @JsonProperty("fail_url") String failUrl
) {
}
