package com.dive.backend.recommendation.client;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Slf4j
@Component
public class DiveAiClient {
    /** economic-feedback 응답의 안정성(신용) 점수 필드. */
    private static final String SCORE_FIELD = "composite_stability_score";

    private final DiveAiProperties properties;
    private final RestClient restClient;

    public DiveAiClient(DiveAiProperties properties) {
        this.properties = properties;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.connectTimeoutMs()); // 연결 3초
        factory.setReadTimeout(properties.readTimeoutMs());       // 응답 30초
        this.restClient = RestClient.builder()
                .baseUrl(properties.baseUrl())
                .requestFactory(factory)
                .build();
    }

    /** KCB 레코드로 economic-feedback를 호출해 안정성 점수(0~100)를 반환한다. */
    public double compositeStabilityScore(Map<String, Object> kcbRecord) {
        JsonNode body = economicFeedback(kcbRecord);
        JsonNode score = body.path(SCORE_FIELD);
        if (score.isMissingNode() || !score.isNumber()) {
            throw new IllegalStateException("economic-feedback 응답에 " + SCORE_FIELD + "가 없습니다: " + body);
        }
        return score.asDouble();
    }

    public JsonNode economicFeedback(Map<String, Object> kcbRecord) {
        Map<String, Object> payload = Map.of("kcb_record", kcbRecord);

        RuntimeException last = null;
        for (int attempt = 0; attempt <= properties.maxRetries(); attempt++) {
            try {
                return restClient.post()
                        .uri("/v1/economic-feedback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("User-Agent", "DIVE-Backend/1.0")
                        .body(payload)
                        .retrieve()
                        .body(JsonNode.class);
            } catch (RuntimeException exception) {
                last = exception;
                log.warn("DIVE AI economic feedback failed (attempt {}/{})", attempt + 1, properties.maxRetries() + 1, exception);
            }
        }
        throw last == null ? new IllegalStateException("DIVE AI economic feedback request failed") : last;
    }
}
