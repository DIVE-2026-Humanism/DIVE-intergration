package com.dive.backend.recommendation.service;

import com.dive.backend.recommendation.dto.RecommendationProgressResponse;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 동기식 추천 요청의 화면 진행 상태를 제공한다. 결과나 KCB 원문은 저장하지 않고
 * 회원별 짧은 상태만 메모리에 보관하므로, 재시작 뒤에는 초기 상태로 돌아간다.
 */
@Service
public class RecommendationProgressService {
    private static final long RETENTION_MILLIS = 5 * 60 * 1_000L;
    private final Map<Long, Progress> progressByMember = new ConcurrentHashMap<>();

    public void start(Long memberId) { update(memberId, "SCORING", "AI가 경제 안정성 점수를 판단하고 있어요", 20, false); }
    public void scoringComplete(Long memberId) { update(memberId, "POLICY_RECOMMENDING", "AI가 맞춤 정책을 추천하고 있어요", 55, false); }
    public void reportGenerating(Long memberId) { update(memberId, "REPORT_GENERATING", "AI가 리포트를 작성하고 있어요", 82, false); }
    public void completed(Long memberId) { update(memberId, "COMPLETED", "추천 결과를 정리하고 있어요", 100, true); }
    public void failed(Long memberId) { update(memberId, "FAILED", "추천 결과를 확인하고 있어요", 100, true); }

    public RecommendationProgressResponse get(Long memberId) {
        Progress progress = progressByMember.get(memberId);
        if (progress == null || Instant.now().toEpochMilli() - progress.updatedAt > RETENTION_MILLIS) {
            progressByMember.remove(memberId);
            return new RecommendationProgressResponse("IDLE", "AI 추천을 준비하고 있어요", 0, false);
        }
        return new RecommendationProgressResponse(progress.stage, progress.message, progress.percent, progress.completed);
    }

    private void update(Long memberId, String stage, String message, int percent, boolean completed) {
        progressByMember.put(memberId, new Progress(stage, message, percent, completed, Instant.now().toEpochMilli()));
    }

    private record Progress(String stage, String message, int percent, boolean completed, long updatedAt) { }
}
