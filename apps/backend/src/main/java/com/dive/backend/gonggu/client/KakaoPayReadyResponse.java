package com.dive.backend.gonggu.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record KakaoPayReadyResponse(
        @JsonProperty("tid") String tid,
        @JsonProperty("next_redirect_pc_url") String nextRedirectPcUrl,
        @JsonProperty("next_redirect_mobile_url") String nextRedirectMobileUrl,
        @JsonProperty("next_redirect_app_url") String nextRedirectAppUrl,
        @JsonProperty("android_app_scheme") String androidAppScheme,
        @JsonProperty("ios_app_scheme") String iosAppScheme,
        @JsonProperty("created_at") String createdAt
) {
}
