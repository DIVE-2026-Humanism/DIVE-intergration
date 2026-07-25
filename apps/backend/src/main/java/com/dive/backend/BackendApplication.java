package com.dive.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import com.dive.backend.recommendation.llm.RecommendationProperties;
import com.dive.backend.recommendation.llm.OpenAiProperties;
import com.dive.backend.recommendation.client.DiveAiProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
@EnableConfigurationProperties({DiveAiProperties.class, RecommendationProperties.class, OpenAiProperties.class})
public class BackendApplication {

	public static void main(String[] args) {
		SpringApplication.run(BackendApplication.class, args);
	}

}
