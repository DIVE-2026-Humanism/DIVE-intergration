package com.dive.backend.recommendation.dto;

import java.util.List;

/** DIVE AI economic-feedback 중 정책 추천 화면에 노출 가능한 값만 담는다. */
public record AiEconomicReport(
        Double compositeStabilityScore,
        String economicType,
        String economicTypeName,
        String majorClass,
        Double typeConfidence,
        String modelVersion,
        String feedbackMethod,
        String summary,
        List<PeerComparison> peerComparisons,
        HousingBenchmark housingBenchmark,
        List<FeedbackItem> feedback,
        List<ActionGuide> guides,
        String disclaimer,
        List<String> sources
) {
    public record PeerComparison(String metric, Double userValue, Double peerAverage, Double gapPercent, String direction, String unit, String source) { }
    public record HousingBenchmark(String region, Double monthlyRentMedian, Double monthlyDepositMedian, Double jeonseDepositMedian, String period, String source, String notice) { }
    public record FeedbackItem(String category, String message, String evidence) { }
    public record ActionGuide(Integer priority, String title, String action) { }
}
