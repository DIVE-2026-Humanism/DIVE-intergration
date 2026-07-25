package com.dive.backend.global.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 주입 가능한 ObjectMapper 빈. (스타터 구성상 자동 등록이 안 되어 명시적으로 제공)
 * JavaTimeModule 등 모듈을 자동 등록하고, 날짜는 타임스탬프가 아닌 ISO-8601 문자열로 직렬화한다.
 */
@Configuration
public class JacksonConfig {

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper()
                .findAndRegisterModules()
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
}
