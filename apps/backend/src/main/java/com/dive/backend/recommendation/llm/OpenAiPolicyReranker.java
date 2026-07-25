package com.dive.backend.recommendation.llm;

import com.dive.backend.policy.domain.Policy;
import com.dive.backend.recommendation.domain.PolicyType;
import com.dive.backend.recommendation.dto.UserInputsOverride;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.*;

@Slf4j
@Component
@RequiredArgsConstructor
public class OpenAiPolicyReranker implements PolicyReranker {
    private static final String SYSTEM_PROMPT = """
            You recommend Korean youth policies. Select only eligible policies from the supplied candidates.
            Consider the natural-language eligibility and exclusion conditions. Never invent a policy number.
            Return Korean reasons and cautions; reason is one concise sentence and caution may be empty.
            """;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final OpenAiProperties properties;
    @Value("${spring.ai.openai.api-key:}") private String apiKey;

    @Override
    public List<LlmRecommendation> recommend(PolicyType type, int creditScore, UserInputsOverride profile, List<Policy> candidates) {
        if (apiKey == null || apiKey.isBlank()) throw new IllegalStateException("OpenAI API key is not configured");
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", properties.model());
        body.put("temperature", 0);
        body.put("messages", List.of(Map.of("role", "system", "content", SYSTEM_PROMPT), Map.of("role", "user", "content", userPrompt(type, creditScore, profile, candidates))));
        body.put("response_format", responseFormat());
        RuntimeException last = null;
        for (int attempt = 0; attempt <= properties.maxRetries(); attempt++) {
            try {
                String response = RestClient.builder().baseUrl(properties.baseUrl()).build().post().uri("/chat/completions")
                        .contentType(MediaType.APPLICATION_JSON).header("Authorization", "Bearer " + apiKey).body(body).retrieve().body(String.class);
                return parse(response);
            } catch (RuntimeException e) {
                last = e;
                log.warn("OpenAI policy rerank failed (attempt {}/{})", attempt + 1, properties.maxRetries() + 1, e);
            }
        }
        throw last == null ? new IllegalStateException("OpenAI request failed") : last;
    }

    private List<LlmRecommendation> parse(String response) {
        try {
            JsonNode recommendations = objectMapper.readTree(objectMapper.readTree(response).at("/choices/0/message/content").asText()).path("recommendations");
            if (!recommendations.isArray()) throw new IllegalArgumentException("Missing recommendations");
            List<LlmRecommendation> result = new ArrayList<>();
            for (JsonNode item : recommendations) result.add(new LlmRecommendation(item.path("plcyNo").asText(), item.path("rank").asInt(), item.path("reason").asText(), item.path("caution").asText()));
            return result;
        } catch (Exception e) { throw new IllegalArgumentException("Invalid OpenAI recommendation response", e); }
    }

    private Map<String, Object> responseFormat() {
        Map<String, Object> item = Map.of("type", "object", "additionalProperties", false, "required", List.of("plcyNo", "rank", "reason", "caution"), "properties", Map.of("plcyNo", Map.of("type", "string"), "rank", Map.of("type", "integer"), "reason", Map.of("type", "string"), "caution", Map.of("type", "string")));
        return Map.of("type", "json_schema", "json_schema", Map.of("name", "policy_recommendations", "strict", true, "schema", Map.of("type", "object", "additionalProperties", false, "required", List.of("recommendations"), "properties", Map.of("recommendations", Map.of("type", "array", "minItems", 1, "maxItems", 5, "items", item)))));
    }

    private String userPrompt(PolicyType type, int score, UserInputsOverride p, List<Policy> candidates) {
        List<Map<String, Object>> policies = candidates.stream().map(policy -> Map.<String, Object>of("plcyNo", policy.getPlcyNo(), "name", nullToEmpty(policy.getPlcyNm()), "description", nullToEmpty(policy.getPlcyExplnCn()), "benefit", nullToEmpty(policy.getPlcySprtCn()), "additionalEligibility", nullToEmpty(policy.getAddAplyQlfcCndCn()), "exclusions", nullToEmpty(policy.getPtcpPrpTrgtCn()))).toList();
        Map<String, Object> safeProfile = new LinkedHashMap<>();
        safeProfile.put("ageBand", ageBand(p == null ? null : p.age())); safeProfile.put("incomeBand", incomeBand(p == null ? null : p.annualIncome())); safeProfile.put("regionCode", p == null ? "" : nullToEmpty(p.regionCode())); safeProfile.put("jobCode", p == null ? "" : nullToEmpty(p.jobCode())); safeProfile.put("schoolCode", p == null ? "" : nullToEmpty(p.schoolCode())); safeProfile.put("marriageCode", p == null ? "" : nullToEmpty(p.marriageCode()));
        return "userType=" + type + ", creditScore=" + score + ", profile=" + safeProfile + ", candidates=" + policies;
    }
    private String nullToEmpty(String value) { return value == null ? "" : value; }
    private String ageBand(Integer age) { return age == null ? "unknown" : (age / 10 * 10) + "s"; }
    private String incomeBand(Integer income) { if (income == null) return "unknown"; if (income < 20_000_000) return "under-20m-krw"; if (income < 40_000_000) return "20m-40m-krw"; return "over-40m-krw"; }
}
