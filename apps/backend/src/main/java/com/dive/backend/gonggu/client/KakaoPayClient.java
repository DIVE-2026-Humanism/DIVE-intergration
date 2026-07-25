package com.dive.backend.gonggu.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class KakaoPayClient {

    @Value("${kakaopay.secret-key}")
    private String secretKey;

    private final RestClient restClient = RestClient.create("https://open-api.kakaopay.com");

    public KakaoPayReadyResponse ready(KakaoPayReadyRequest request) {
        return restClient.post()
                .uri("/online/v1/payment/ready")
                .header("Authorization", "SECRET_KEY " + secretKey)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(KakaoPayReadyResponse.class);
    }

    public KakaoPayApproveResponse approve(KakaoPayApproveRequest request) {
        return restClient.post()
                .uri("/online/v1/payment/approve")
                .header("Authorization", "SECRET_KEY " + secretKey)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(KakaoPayApproveResponse.class);
    }
}
