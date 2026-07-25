package com.dive.backend.recommendation.llm;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "openai")
public record OpenAiProperties(String baseUrl, String model, int timeoutMs, int maxRetries) { }
