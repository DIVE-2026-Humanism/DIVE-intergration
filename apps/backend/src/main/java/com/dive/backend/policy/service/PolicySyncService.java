package com.dive.backend.policy.service;

import com.dive.backend.policy.client.YouthPolicyApiClient;
import com.dive.backend.policy.client.YouthPolicyApiResponse;
import com.dive.backend.policy.client.YouthPolicyApiResponse.YouthPolicyItem;
import com.dive.backend.policy.domain.Policy;
import com.dive.backend.policy.domain.PolicyType;
import com.dive.backend.policy.repository.PolicyRepository;
import com.dive.backend.policy.repository.PolicyTypeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * 온통청년 API에서 정책 목록을 가져와 policy 테이블에 upsert(plcyNo 기준)한다.
 * 정책 유형(안정형/취약형)은 API가 주지 않는 자체 분류값이라, 동기화 시점에는
 * "미분류" 타입을 배정해두고 실제 분류는 이후 별도 단계(추천 시 회원 진단 기준)에서 처리한다.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PolicySyncService {

    private static final String UNCLASSIFIED_TYPE_NAME = "미분류";
    private static final int PAGE_SIZE = 100;
    private static final int MAX_PAGES = 1000; // 무한루프 방지 안전장치

    private final YouthPolicyApiClient apiClient;
    private final PolicyRepository policyRepository;
    private final PolicyTypeRepository policyTypeRepository;

    @Transactional
    public void syncAll() {
        PolicyType unclassified = getOrCreateUnclassifiedType();

        int pageIndex = 1;
        int totalSynced = 0;

        while (pageIndex <= MAX_PAGES) {
            YouthPolicyApiResponse response = apiClient.fetchPage(pageIndex, PAGE_SIZE);
            List<YouthPolicyItem> items = extractItems(response);
            if (items.isEmpty()) {
                break;
            }

            items.forEach(item -> upsert(item, unclassified));
            totalSynced += items.size();

            if (items.size() < PAGE_SIZE) {
                break; // 마지막 페이지
            }
            pageIndex++;
        }

        log.info("정책 동기화 완료: 총 {}건, {}페이지 처리", totalSynced, pageIndex);
    }

    private List<YouthPolicyItem> extractItems(YouthPolicyApiResponse response) {
        if (response == null || response.result() == null || response.result().youthPolicyList() == null) {
            return List.of();
        }
        return response.result().youthPolicyList();
    }

    private PolicyType getOrCreateUnclassifiedType() {
        return policyTypeRepository.findByName(UNCLASSIFIED_TYPE_NAME)
                .orElseGet(() -> policyTypeRepository.save(
                        PolicyType.builder()
                                .name(UNCLASSIFIED_TYPE_NAME)
                                .description("API 동기화 시 임시 배정되는 타입. 추후 재분류 대상")
                                .build()));
    }

    private void upsert(YouthPolicyItem item, PolicyType defaultType) {
        Policy.PolicyBuilder builder = policyRepository.findByPlcyNo(item.plcyNo())
                .map(Policy::toBuilder)
                .orElseGet(() -> Policy.builder()
                        .plcyNo(item.plcyNo())
                        .policyType(defaultType)
                        .viewCount(parseIntOrDefault(item.inqCnt(), 0)));

        Policy policy = builder
                .plcyNm(item.plcyNm())
                .plcyKywdNm(item.plcyKywdNm())
                .plcyExplnCn(item.plcyExplnCn())
                .lclsfNm(item.lclsfNm())
                .mclsfNm(item.mclsfNm())
                .plcySprtCn(item.plcySprtCn())
                .plcyAprvSttsCd(item.plcyAprvSttsCd())
                .sprvsnInstNm(item.sprvsnInstCdNm())
                .aplyPrdSeCd(item.aplyPrdSeCd())
                .aplyYmd(item.aplyYmd())
                .plcyAplyMthdCn(item.plcyAplyMthdCn())
                .srngMthdCn(item.srngMthdCn())
                .aplyUrlAddr(item.aplyUrlAddr())
                .sbmsnDcmntCn(item.sbmsnDcmntCn())
                .sprtSclCnt(item.sprtSclCnt())
                .sprtTrgtMinAge(parseIntOrNull(item.sprtTrgtMinAge()))
                .sprtTrgtMaxAge(parseIntOrNull(item.sprtTrgtMaxAge()))
                .sprtTrgtAgeLmtYn(item.sprtTrgtAgeLmtYn())
                .mrgSttsCd(item.mrgSttsCd())
                .earnCndSeCd(item.earnCndSeCd())
                .earnMinAmt(item.earnMinAmt())
                .earnMaxAmt(item.earnMaxAmt())
                .earnEtcCn(item.earnEtcCn())
                .addAplyQlfcCndCn(item.addAplyQlfcCndCn())
                .ptcpPrpTrgtCn(item.ptcpPrpTrgtCn())
                .zipCd(item.zipCd())
                .schoolCd(item.schoolCd())
                .jobCd(item.jobCd())
                .plcyMajorCd(item.plcyMajorCd())
                .srcRegDt(parseDateTime(item.frstRegDt()))
                .srcMdfcnDt(parseDateTime(item.lastMdfcnDt()))
                .build();

        policyRepository.save(policy);
    }

    /** 온통청년 API 날짜는 "yyyy-MM-dd HH:mm:ss" 형식. 방어적으로 14자리 압축 형식도 시도한다. */
    private LocalDateTime parseDateTime(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        try {
            if (raw.length() == 14 && raw.chars().allMatch(Character::isDigit)) {
                return LocalDateTime.parse(raw, DateTimeFormatter.ofPattern("yyyyMMddHHmmss"));
            }
            return LocalDateTime.parse(raw.trim().replace(" ", "T"));
        } catch (Exception e) {
            log.warn("정책 날짜 파싱 실패, null 처리: raw={}", raw);
            return null;
        }
    }

    /** API의 나이/조회수 필드는 숫자가 아니라 문자열("19", "108")로 내려온다. */
    private Integer parseIntOrNull(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        try {
            return Integer.parseInt(raw.trim());
        } catch (NumberFormatException e) {
            log.warn("정수 파싱 실패, null 처리: raw={}", raw);
            return null;
        }
    }

    private int parseIntOrDefault(String raw, int defaultValue) {
        Integer parsed = parseIntOrNull(raw);
        return parsed != null ? parsed : defaultValue;
    }
}
