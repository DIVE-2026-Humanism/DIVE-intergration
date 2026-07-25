package com.dive.backend.global.config;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * Firebase Admin SDK 초기화.
 *
 * 서비스 계정 자격증명 우선순위:
 *   1) 환경변수 FIREBASE_CREDENTIALS_JSON (서비스계정 JSON 원문)
 *   2) 환경변수 FIREBASE_CREDENTIALS_PATH (서비스계정 JSON 파일 경로)
 *   3) classpath:firebase-service-account.json
 *
 * 셋 다 없으면 초기화를 건너뛴다(경고만 로깅). FCM 미설정이어도 앱은 정상 기동한다.
 */
@Slf4j
@Configuration
public class FirebaseConfig {

    @Value("${firebase.credentials-json:}")
    private String credentialsJson;

    @Value("${firebase.credentials-path:}")
    private String credentialsPath;

    @PostConstruct
    public void init() {
        if (!FirebaseApp.getApps().isEmpty()) return;
        try {
            InputStream stream = resolveCredentials();
            if (stream == null) {
                log.warn("[FCM] Firebase 자격증명이 없어 초기화를 건너뜁니다. 푸시 발송은 비활성화됩니다.");
                return;
            }
            FirebaseOptions options = FirebaseOptions.builder()
                    .setCredentials(GoogleCredentials.fromStream(stream))
                    .build();
            FirebaseApp.initializeApp(options);
            log.info("[FCM] FirebaseApp 초기화 완료");
        } catch (Exception e) {
            log.error("[FCM] Firebase 초기화 실패 — 푸시 발송 비활성화", e);
        }
    }

    private InputStream resolveCredentials() throws Exception {
        if (credentialsJson != null && !credentialsJson.isBlank()) {
            return new ByteArrayInputStream(credentialsJson.getBytes(StandardCharsets.UTF_8));
        }
        if (credentialsPath != null && !credentialsPath.isBlank()) {
            return new java.io.FileInputStream(credentialsPath);
        }
        ClassPathResource resource = new ClassPathResource("firebase-service-account.json");
        return resource.exists() ? resource.getInputStream() : null;
    }
}
