package com.dive.backend.gonggu.dto;

public record KakaoPayReadyResult(
        Long paymentId,
        String nextRedirectPcUrl,
        String nextRedirectMobileUrl
) {
}
