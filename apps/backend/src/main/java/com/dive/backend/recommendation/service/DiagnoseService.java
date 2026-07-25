package com.dive.backend.recommendation.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.kcb.domain.KcbConnection;
import com.dive.backend.kcb.repository.KcbConnectionRepository;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.policy.domain.Policy;
import com.dive.backend.policy.domain.PolicyLike;
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
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class DiagnoseService {
    private static final Pattern AMOUNT = Pattern.compile("\\d+");
    private final MemberRepository memberRepository;
    private final PolicyRepository policyRepository;
    private final DiagnosisRepository diagnosisRepository;
    private final PolicyRecommendationRepository policyRecommendationRepository;
    private final PolicyLikeRepository policyLikeRepository;
    private final PolicyTypeResolver policyTypeResolver;
    private final PolicyReranker policyReranker;
    private final RecommendationProperties properties;
    private final DiveAiClient diveAiClient;
    private final KcbConnectionRepository kcbConnectionRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public DiagnoseResponse diagnose(Long memberId, DiagnoseRequest request) {
        Member member = memberRepository.findById(memberId).orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        int score = fetchScore(latestKcbRecord(memberId));
        PolicyType type = policyTypeResolver.resolve(score);
        List<Policy> candidates = candidates(type, request.userInputsOverride());
        if (candidates.isEmpty()) throw new BusinessException(ErrorCode.NO_ELIGIBLE_POLICY);

        List<LlmRecommendation> selected = rerankOrFallback(type, score, request.userInputsOverride(), candidates);
        Diagnosis diagnosis = diagnosisRepository.save(new Diagnosis(member, typeId(type), score, type));
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
        return toResponse(score, type, memberId, saved);
    }

    @Transactional(readOnly = true)
    public DiagnoseResponse latest(Long memberId) {
        Diagnosis diagnosis = diagnosisRepository.findTopByMemberIdOrderByCreatedAtDesc(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.DIAGNOSIS_NOT_FOUND));
        List<PolicyRecommendation> recommendations = policyRecommendationRepository.findByDiagnosisIdOrderByRankOrderAsc(diagnosis.getId());
        return toResponse(diagnosis.getCreditScore(), diagnosis.getUserType(), memberId, recommendations);
    }

    /** 회원이 연동한 최신 KCB 레코드(42필드)를 읽는다. 연동이 없으면 R001. */
    private Map<String, Object> latestKcbRecord(Long memberId) {
        KcbConnection connection = kcbConnectionRepository.findTopByMember_IdOrderByCreatedAtDesc(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.KCB_NOT_CONNECTED));
        try {
            return objectMapper.readValue(connection.getKcbRecordJson(), new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("저장된 KCB 레코드를 읽지 못했습니다.", exception);
        }
    }

    /** KCB 레코드로 AI 서버에서 안정성 점수(0~100)를 받아 정수로 반환한다. */
    private int fetchScore(Map<String, Object> kcbRecord) {
        try {
            return (int) Math.round(diveAiClient.compositeStabilityScore(kcbRecord));
        } catch (RuntimeException exception) {
            log.warn("Failed to fetch composite stability score from DIVE AI", exception);
            throw new BusinessException(ErrorCode.AI_FEEDBACK_UNAVAILABLE);
        }
    }

    private List<Policy> candidates(PolicyType type, UserInputsOverride profile) {
        List<Policy> primary = filter(policyRepository.findApprovedCandidates(typeId(type)), profile);
        if (primary.size() < properties.resultCount()) {
            PolicyType opposite = type == PolicyType.STABLE ? PolicyType.VULNERABLE : PolicyType.STABLE;
            primary.addAll(filter(policyRepository.findApprovedCandidates(typeId(opposite)), profile));
        }
        return primary.stream().limit(properties.candidateLimit()).toList();
    }

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

    private DiagnoseResponse toResponse(int score, PolicyType type, Long memberId, List<PolicyRecommendation> recommendations) {
        Set<Long> ids = recommendations.stream().map(r -> r.getPolicy().getId()).collect(java.util.stream.Collectors.toSet());
        Set<Long> liked = policyLikeRepository.findByMember_IdAndPolicy_IdIn(memberId, ids).stream()
                .map(pl -> pl.getPolicy().getId()).collect(java.util.stream.Collectors.toSet());
        List<RecommendedPolicy> cards = recommendations.stream().map(r -> {
            Policy p = r.getPolicy();
            return new RecommendedPolicy(p.getId(), p.getPlcyNo(), p.getPlcyNm(), p.getLclsfNm(), p.getPlcySprtCn(),
                    r.getReason(), r.getCaution(), liked.contains(p.getId()));
        }).toList();
        return new DiagnoseResponse(score, type, type.getLabel(), cards);
    }

    private int typeId(PolicyType type) { return type == PolicyType.STABLE ? properties.stablePolicyTypeId() : properties.vulnerablePolicyTypeId(); }
    private String trim(String text) { return text == null ? "" : text.substring(0, Math.min(text.length(), 500)); }
}
