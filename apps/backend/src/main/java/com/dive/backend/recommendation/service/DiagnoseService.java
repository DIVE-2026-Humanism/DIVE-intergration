package com.dive.backend.recommendation.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.kcb.domain.KcbConnection;
import com.dive.backend.kcb.repository.KcbConnectionRepository;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.policy.domain.Policy;
import com.dive.backend.policy.domain.PolicyLike;
import com.dive.backend.policy.service.PolicyApplicationPeriod;
import com.dive.backend.recommendation.client.DiveAiClient;
import com.dive.backend.recommendation.domain.*;
import com.dive.backend.recommendation.dto.*;
import com.dive.backend.recommendation.llm.LlmRecommendation;
import com.dive.backend.recommendation.llm.PolicyReranker;
import com.dive.backend.recommendation.llm.RecommendationProperties;
import com.dive.backend.recommendation.repository.*;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class DiagnoseService {
    private static final Pattern AMOUNT = Pattern.compile("\\d+");
    private static final Map<String, Integer> VULNERABLE_PRIORITIES = Map.ofEntries(
            Map.entry("주거", 10), Map.entry("월세", 9), Map.entry("금융", 8), Map.entry("복지", 8),
            Map.entry("대출", 7), Map.entry("바우처", 7), Map.entry("건강", 5), Map.entry("취업", 5),
            Map.entry("상담", 4), Map.entry("수당", 4), Map.entry("생활", 4));
    private static final Map<String, Integer> STABLE_PRIORITIES = Map.ofEntries(
            Map.entry("창업", 10), Map.entry("교육", 8), Map.entry("직업훈련", 8), Map.entry("역량", 7),
            Map.entry("자격", 6), Map.entry("인턴", 6), Map.entry("자산", 6), Map.entry("적금", 6),
            Map.entry("청약", 6), Map.entry("네트워킹", 4), Map.entry("국제교류", 4));
    private final MemberRepository memberRepository;
    private final PolicyRepository policyRepository;
    private final DiagnosisRepository diagnosisRepository;
    private final PolicyRecommendationRepository policyRecommendationRepository;
    private final SavedRecommendationResultRepository savedRecommendationResultRepository;
    private final PolicyLikeRepository policyLikeRepository;
    private final PolicyTypeResolver policyTypeResolver;
    private final PolicyReranker policyReranker;
    private final RecommendationProperties properties;
    private final DiveAiClient diveAiClient;
    private final KcbConnectionRepository kcbConnectionRepository;
    private final ObjectMapper objectMapper;
    private final RecommendationProgressService recommendationProgressService;

    @Transactional
    public DiagnoseResponse diagnose(Long memberId, DiagnoseRequest request) {
        recommendationProgressService.start(memberId);
        try {
            Member member = memberRepository.findById(memberId).orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
            KcbConnection connection = latestKcbConnection(memberId);
            AiEconomicReport aiReport = fetchAiReport(kcbRecord(connection));
            int score = (int) Math.round(score(aiReport));
            PolicyType type = policyType(aiReport, score);
            saveAiAnalysis(connection, aiReport, score);
            recommendationProgressService.scoringComplete(memberId);
            List<Policy> candidates = candidates(type, request.userInputsOverride());
            if (candidates.isEmpty()) throw new BusinessException(ErrorCode.NO_ELIGIBLE_POLICY);

            List<LlmRecommendation> selected = rerankOrFallback(type, score, request.userInputsOverride(), candidates);
            recommendationProgressService.reportGenerating(memberId);
            Diagnosis diagnosis = diagnosisRepository.save(new Diagnosis(member, score, type));
            Map<String, Policy> byNo = new HashMap<>();
            candidates.forEach(policy -> byNo.put(policy.getPlcyNo(), policy));
            List<PolicyRecommendation> saved = new ArrayList<>();
            int rank = 1;
            for (LlmRecommendation recommendation : selected) {
                Policy policy = byNo.get(recommendation.plcyNo());
                if (policy != null) saved.add(policyRecommendationRepository.save(new PolicyRecommendation(
                        diagnosis, member, policy, rank++, trim(recommendation.reason()), trim(recommendation.caution()))));
            }
            if (saved.isEmpty()) throw new BusinessException(ErrorCode.NO_ELIGIBLE_POLICY);
            DiagnoseResponse response = toResponse(score, type, aiReport, memberId, saved);
            recommendationProgressService.completed(memberId);
            return response;
        } catch (RuntimeException exception) {
            recommendationProgressService.failed(memberId);
            throw exception;
        }
    }

    public RecommendationProgressResponse progress(Long memberId) {
        return recommendationProgressService.get(memberId);
    }

    @Transactional(readOnly = true)
    public DiagnoseResponse latest(Long memberId) {
        Diagnosis diagnosis = diagnosisRepository.findTopByMemberIdOrderByCreatedAtDesc(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.DIAGNOSIS_NOT_FOUND));
        List<PolicyRecommendation> recommendations = policyRecommendationRepository.findByDiagnosisIdOrderByRankOrderAsc(diagnosis.getId());
        return toResponse(diagnosis.getCreditScore(), diagnosis.getUserType(), latestAiReport(memberId), memberId, recommendations);
    }

    @Transactional
    public SavedRecommendationResultDetail saveRecommendationResult(Long memberId) {
        Member member = memberRepository.findById(memberId).orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        Diagnosis diagnosis = diagnosisRepository.findTopByMemberIdOrderByCreatedAtDesc(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.DIAGNOSIS_NOT_FOUND));
        Optional<SavedRecommendationResult> existing = savedRecommendationResultRepository
                .findByMember_IdAndDiagnosis_Id(memberId, diagnosis.getId());
        if (existing.isPresent()) {
            return savedResultDetail(existing.get());
        }

        List<PolicyRecommendation> recommendations = policyRecommendationRepository
                .findByDiagnosisIdOrderByRankOrderAsc(diagnosis.getId());
        if (recommendations.isEmpty()) throw new BusinessException(ErrorCode.NO_ELIGIBLE_POLICY);
        DiagnoseResponse snapshot = toResponse(diagnosis.getCreditScore(), diagnosis.getUserType(), latestAiReport(memberId), memberId, recommendations);
        try {
            SavedRecommendationResult saved = savedRecommendationResultRepository.save(
                    new SavedRecommendationResult(member, diagnosis, savedResultTitle(snapshot, LocalDateTime.now()), objectMapper.writeValueAsString(snapshot)));
            return new SavedRecommendationResultDetail(saved.getId(), saved.getTitle(), saved.getSavedAt(), snapshot);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("추천 결과를 저장하지 못했습니다.", exception);
        }
    }

    @Transactional(readOnly = true)
    public List<SavedRecommendationResultSummary> savedRecommendationResults(Long memberId) {
        return savedRecommendationResultRepository.findByMember_IdOrderBySavedAtDesc(memberId).stream()
                .map(saved -> {
                    DiagnoseResponse result = savedSnapshot(saved);
                    return new SavedRecommendationResultSummary(saved.getId(), savedResultTitle(saved, result), result.creditScore(), result.userType(),
                            result.typeLabel(), result.recommendations().size(), saved.getSavedAt());
                }).toList();
    }

    @Transactional(readOnly = true)
    public SavedRecommendationResultDetail savedRecommendationResult(Long memberId, Long resultId) {
        SavedRecommendationResult saved = savedRecommendationResultRepository.findByIdAndMember_Id(resultId, memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.DIAGNOSIS_NOT_FOUND));
        return savedResultDetail(saved);
    }

    private SavedRecommendationResultDetail savedResultDetail(SavedRecommendationResult saved) {
        DiagnoseResponse result = savedSnapshot(saved);
        return new SavedRecommendationResultDetail(saved.getId(), savedResultTitle(saved, result), saved.getSavedAt(), result);
    }

    private String savedResultTitle(SavedRecommendationResult saved, DiagnoseResponse result) {
        return saved.getTitle() == null || saved.getTitle().isBlank()
                ? savedResultTitle(result, saved.getSavedAt()) : saved.getTitle();
    }

    private String savedResultTitle(DiagnoseResponse result, LocalDateTime savedAt) {
        return savedAt.format(DateTimeFormatter.ofPattern("yyyy년 M월 d일")) + " "
                + result.typeLabel() + " 정책 추천";
    }

    private DiagnoseResponse savedSnapshot(SavedRecommendationResult saved) {
        try {
            return objectMapper.readValue(saved.getResultJson(), DiagnoseResponse.class);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("저장한 추천 결과를 읽지 못했습니다.", exception);
        }
    }

    /** 회원이 연동한 최신 KCB 레코드(42필드)를 읽는다. 연동이 없으면 R001. */
    private KcbConnection latestKcbConnection(Long memberId) {
        return kcbConnectionRepository.findTopByMember_IdOrderByCreatedAtDesc(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.KCB_NOT_CONNECTED));
    }

    private Map<String, Object> kcbRecord(KcbConnection connection) {
        try {
            return objectMapper.readValue(connection.getKcbRecordJson(), new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("저장된 KCB 레코드를 읽지 못했습니다.", exception);
        }
    }

    private AiEconomicReport fetchAiReport(Map<String, Object> kcbRecord) {
        try {
            return aiReport(diveAiClient.economicFeedback(kcbRecord));
        } catch (RuntimeException exception) {
            log.warn("Failed to fetch composite stability score from DIVE AI", exception);
            throw new BusinessException(ErrorCode.AI_FEEDBACK_UNAVAILABLE);
        }
    }

    private void saveAiAnalysis(KcbConnection connection, AiEconomicReport report, int score) {
        try {
            connection.updateAiAnalysis(objectMapper.writeValueAsString(report), score, report.economicType(),
                    report.economicTypeName(), report.majorClass(), confidence(report.typeConfidence()));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("AI 분석 결과를 저장하지 못했습니다.", exception);
        }
    }

    private AiEconomicReport latestAiReport(Long memberId) {
        try {
            String raw = latestKcbConnection(memberId).getAiResponseJson();
            return raw == null || raw.isBlank() ? null : objectMapper.readValue(raw, AiEconomicReport.class);
        } catch (JsonProcessingException exception) {
            log.warn("Stored DIVE AI report could not be read", exception);
            return null;
        } catch (BusinessException exception) {
            return null;
        }
    }

    private PolicyType policyType(AiEconomicReport report, int score) {
        if (Set.of("E1", "E2", "E3").contains(report.economicType())) return PolicyType.STABLE;
        if (Set.of("E4", "E5", "E6").contains(report.economicType())) return PolicyType.VULNERABLE;
        if ("안정".equals(report.majorClass())) return PolicyType.STABLE;
        if ("취약".equals(report.majorClass())) return PolicyType.VULNERABLE;
        return policyTypeResolver.resolve(score);
    }

    private double score(AiEconomicReport report) {
        if (report == null || report.compositeStabilityScore() == null) {
            throw new IllegalStateException("DIVE AI 응답에 composite_stability_score가 없습니다.");
        }
        return report.compositeStabilityScore();
    }

    /**
     * 정책의 policy_type_id는 동기화 원본의 분류값이므로 사용자 신용 진단 결과로 필터링하지 않는다.
     * 모든 승인 정책에서 자격 조건을 먼저 확인하고, 사용자 유형은 추천 우선순위에만 반영한다.
     */
    private List<Policy> candidates(PolicyType type, UserInputsOverride profile) {
        List<Policy> approved = policyRepository.findAllApprovedCandidates();
        List<Policy> eligible = filter(approved, profile).stream()
                .filter(PolicyApplicationPeriod::isOpen)
                .toList();
        List<Policy> ranked = eligible.stream()
                .sorted(Comparator.comparingInt((Policy policy) -> priority(policy, type)).reversed()
                        .thenComparing(Policy::getViewCount, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(Policy::getId))
                .limit(properties.candidateLimit())
                .toList();

        log.info("Policy candidate selection: userType={}, approved={}, eligible={}, selected={}, top={}",
                type, approved.size(), eligible.size(), ranked.size(),
                ranked.stream().limit(5)
                        .map(policy -> policy.getId() + ":" + priority(policy, type))
                        .toList());
        return ranked;
    }

    private int priority(Policy policy, PolicyType type) {
        Map<String, Integer> priorities = type == PolicyType.VULNERABLE
                ? VULNERABLE_PRIORITIES : STABLE_PRIORITIES;
        String text = String.join(" ", value(policy.getLclsfNm()), value(policy.getMclsfNm()),
                value(policy.getPlcyKywdNm()), value(policy.getPlcyNm()), value(policy.getPlcySprtCn()));
        return priorities.entrySet().stream()
                .filter(entry -> text.contains(entry.getKey()))
                .mapToInt(Map.Entry::getValue)
                .sum();
    }

    private String value(String text) { return text == null ? "" : text; }

    private List<Policy> filter(List<Policy> policies, UserInputsOverride profile) {
        if (profile == null) return new ArrayList<>(policies);
        return policies.stream().filter(p -> ageMatches(p, profile.age()))
                .filter(p -> codeMatches(p.getZipCd(), profile.regionCode(), ""))
                .filter(p -> codeMatches(p.getJobCd(), profile.jobCode(), "0013010"))
                .filter(p -> codeMatches(p.getSchoolCd(), profile.schoolCode(), "0049010"))
                .filter(p -> codeMatches(p.getMrgSttsCd(), profile.marriageCode(), "0055003"))
                .filter(p -> incomeMatches(p, profile.annualIncome())).toList();
    }

    private boolean ageMatches(Policy policy, Integer age) {
        return age == null || (policy.getSprtTrgtMinAge() == null || age >= policy.getSprtTrgtMinAge())
                && (policy.getSprtTrgtMaxAge() == null || age <= policy.getSprtTrgtMaxAge());
    }

    private boolean codeMatches(String condition, String value, String unrestrictedCode) {
        return value == null || value.isBlank() || condition == null || condition.isBlank()
                || (!unrestrictedCode.isBlank() && condition.contains(unrestrictedCode)) || condition.contains(value);
    }

    private boolean incomeMatches(Policy policy, Integer income) {
        if (income == null) return true;
        Integer min = amount(policy.getEarnMinAmt());
        Integer max = amount(policy.getEarnMaxAmt());
        return (min == null || income >= min) && (max == null || income <= max);
    }

    private Integer amount(String raw) {
        if (raw == null) return null;
        Matcher matcher = AMOUNT.matcher(raw.replace(",", ""));
        if (!matcher.find()) return null;
        try { return Integer.parseInt(matcher.group()); } catch (NumberFormatException ignored) { return null; }
    }

    private List<LlmRecommendation> rerankOrFallback(PolicyType type, int score, UserInputsOverride profile, List<Policy> candidates) {
        try {
            Set<String> candidateNos = candidates.stream().map(Policy::getPlcyNo).collect(java.util.stream.Collectors.toSet());
            LinkedHashMap<String, LlmRecommendation> valid = new LinkedHashMap<>();
            policyReranker.recommend(type, score, profile, candidates).stream()
                    .sorted(Comparator.comparingInt(LlmRecommendation::rank))
                    .filter(r -> candidateNos.contains(r.plcyNo()))
                    .forEach(r -> valid.putIfAbsent(r.plcyNo(), r));
            if (!valid.isEmpty()) return valid.values().stream().limit(properties.resultCount()).toList();
            throw new IllegalArgumentException("No whitelisted LLM recommendations");
        } catch (RuntimeException exception) {
            log.warn("Policy rerank unavailable; using deterministic fallback", exception);
            return candidates.stream().limit(properties.resultCount())
                    .map(p -> new LlmRecommendation(p.getPlcyNo(), 0,
                            type.getLabel() + " 사용자에게 " + (p.getLclsfNm() == null ? "정책" : p.getLclsfNm()) + " 지원 조건이 맞을 수 있어요.",
                            "신청 전 세부 자격과 신청 기간을 확인하세요.")).toList();
        }
    }

    private DiagnoseResponse toResponse(int score, PolicyType type, AiEconomicReport aiReport, Long memberId, List<PolicyRecommendation> recommendations) {
        Set<Long> ids = recommendations.stream().map(r -> r.getPolicy().getId()).collect(java.util.stream.Collectors.toSet());
        Set<Long> liked = policyLikeRepository.findByMember_IdAndPolicy_IdIn(memberId, ids).stream()
                .map(pl -> pl.getPolicy().getId()).collect(java.util.stream.Collectors.toSet());
        List<RecommendedPolicy> cards = recommendations.stream().map(r -> {
            Policy p = r.getPolicy();
            return new RecommendedPolicy(p.getId(), p.getPlcyNo(), p.getPlcyNm(), p.getLclsfNm(), p.getPlcySprtCn(),
                    r.getReason(), r.getCaution(), liked.contains(p.getId()));
        }).toList();
        String typeLabel = aiReport != null && aiReport.economicTypeName() != null && !aiReport.economicTypeName().isBlank()
                ? aiReport.economicTypeName() : type.getLabel();
        return new DiagnoseResponse(score, type, typeLabel, aiReport, cards);
    }

    @SuppressWarnings("unchecked")
    private AiEconomicReport aiReport(Map<String, Object> body) {
        Map<String, Object> feedback = object(body.get("feedback"));
        Map<String, Object> housing = object(body.get("housing_benchmark"));
        return new AiEconomicReport(number(body.get("composite_stability_score")), text(body.get("economic_type")),
                text(body.get("economic_type_name")), text(body.get("major_class")), number(body.get("type_confidence")),
                text(body.get("model_version")), text(body.get("feedback_method")), text(feedback.get("summary")),
                objects(body.get("peer_comparisons")).stream().map(item -> new AiEconomicReport.PeerComparison(
                        text(item.get("metric")), number(item.get("user_value")), number(item.get("peer_average")), number(item.get("gap_percent")),
                        text(item.get("direction")), text(item.get("unit")), text(item.get("source")))).toList(),
                housing.isEmpty() ? null : new AiEconomicReport.HousingBenchmark(text(housing.get("지역")), number(housing.get("월세_중앙값만원")),
                        number(housing.get("월세보증금_중앙값만원")), number(housing.get("전세보증금_중앙값만원")), text(housing.get("기준기간")),
                        text(housing.get("출처")), text(housing.get("주의"))),
                objects(feedback.get("feedback")).stream().map(item -> new AiEconomicReport.FeedbackItem(text(item.get("category")), text(item.get("message")), text(item.get("evidence")))).toList(),
                objects(feedback.get("guides")).stream().map(item -> new AiEconomicReport.ActionGuide(integer(item.get("priority")), text(item.get("title")), text(item.get("action")))).toList(),
                text(feedback.get("disclaimer")), strings(body.get("sources")));
    }

    private Map<String, Object> object(Object value) {
        if (!(value instanceof Map<?, ?> map)) return Map.of();
        Map<String, Object> result = new LinkedHashMap<>();
        map.forEach((key, entry) -> result.put(String.valueOf(key), entry));
        return result;
    }

    private List<Map<String, Object>> objects(Object value) {
        if (!(value instanceof List<?> values)) return List.of();
        return values.stream().map(this::object).filter(map -> !map.isEmpty()).toList();
    }

    private List<String> strings(Object value) {
        if (!(value instanceof List<?> values)) return List.of();
        return values.stream().map(this::text).filter(item -> !item.isBlank()).toList();
    }

    private String text(Object value) { return value == null ? "" : String.valueOf(value); }
    private Double number(Object value) { return value instanceof Number number ? number.doubleValue() : null; }
    private Integer integer(Object value) { return value instanceof Number number ? number.intValue() : null; }
    private double confidence(Double value) { return value == null ? 0 : value; }

    private String trim(String text) { return text == null ? "" : text.substring(0, Math.min(text.length(), 500)); }
}
