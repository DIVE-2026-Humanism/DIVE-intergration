package com.dive.backend.policy.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;


@Component
public class YouthPolicyApiClient {

    /** 부산광역시 법정동코드(시/도 단위). 부산 전용 + 전국 대상 정책까지 포함해서 내려온다. */
    private static final String BUSAN_ZIP_CD = "26000";

    @Value("${youthcenter.api-key}")
    private String apiKey;

    private final RestClient restClient = RestClient.create("https://www.youthcenter.go.kr");

    /**
     * @param pageNum  1부터 시작하는 페이지 번호
     * @param pageSize 페이지당 조회 건수
     */
    public YouthPolicyApiResponse fetchPage(int pageNum, int pageSize) {
        return restClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/go/ythip/getPlcy")
                        .queryParam("apiKeyNm", apiKey)
                        .queryParam("pageNum", pageNum)
                        .queryParam("pageSize", pageSize)
                        .queryParam("rtnType", "json")
                        .queryParam("zipCd", BUSAN_ZIP_CD)
                        .build())
                .retrieve()
                .body(YouthPolicyApiResponse.class);
    }
}
