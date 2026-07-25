package com.dive.backend.recommendation.dto;

/** 현재 로그인 회원의 정책 추천 생성 단계. 완료 전까지 앱이 짧게 폴링한다. */
public record RecommendationProgressResponse(String stage, String message, int percent, boolean completed) {
}
