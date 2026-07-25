package com.dive.backend.recommendation.client;

import com.dive.backend.recommendation.dto.AiUserInputs;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.LinkedHashMap;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class DiveAiClient {
    private final DiveAiProperties properties;

    public JsonNode diagnose(AiUserInputs userInputs, Map<String, Object> kcbRecord) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("mode", "precise");
        payload.put("user_inputs", userInputs);
        payload.put("kcb_record", kcbRecord);

        RuntimeException last = null;
        for (int attempt = 0; attempt <= properties.maxRetries(); attempt++) {
            try {
                return RestClient.builder().baseUrl(properties.baseUrl()).build().post()
                        .uri("/v1/diagnose")
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(payload)
                        .retrieve()
                        .body(JsonNode.class);
            } catch (RuntimeException exception) {
                last = exception;
                log.warn("DIVE AI diagnose failed (attempt {}/{})", attempt + 1, properties.maxRetries() + 1, exception);
            }
        }
        throw last == null ? new IllegalStateException("DIVE AI request failed") : last;
    }
}
