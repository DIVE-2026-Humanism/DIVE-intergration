package com.dive.backend.recommendation.client;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "dive.ai")
public record DiveAiProperties(String baseUrl, int connectTimeoutMs, int readTimeoutMs, int maxRetries) { }
