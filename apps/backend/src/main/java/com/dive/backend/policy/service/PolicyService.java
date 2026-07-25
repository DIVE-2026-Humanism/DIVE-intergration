package com.dive.backend.policy.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.policy.domain.Policy;
import com.dive.backend.policy.domain.PolicyLike;
import com.dive.backend.policy.dto.PolicyCategoryResponse;
import com.dive.backend.policy.dto.PolicyDetailResponse;
import com.dive.backend.policy.dto.PolicyResponse;
import com.dive.backend.policy.repository.PolicyLikeRepository;
import com.dive.backend.policy.repository.PolicyRepository;
import com.dive.backend.policy.repository.PolicySpecifications;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class PolicyService {

    private final PolicyRepository policyRepository;
    private final PolicyLikeRepository policyLikeRepository;
    private final MemberRepository memberRepository;
    private final PolicyPopularityService policyPopularityService;

    /** 대분류 5개 + 각 대분류의 중분류 목록. (온통청년 분류 구조) */
    public List<PolicyCategoryResponse> getCategories() {
        return List.of(
                new PolicyCategoryResponse("일자리", List.of("취업", "재직자", "창업")),
                new PolicyCategoryResponse("주거", List.of("주택 및 거주지", "기숙사", "전월세 및 주거급여 지원")),
                new PolicyCategoryResponse("교육", List.of("미래역량강화", "교육비지원", "온라인교육")),
                new PolicyCategoryResponse("금융･복지･문화", List.of("취약계층 및 금융지원", "건강", "예술인지원", "문화활동")),
                new PolicyCategoryResponse("참여권리", List.of("청년참여", "정책인프라구축", "청년국제교류", "권익보호"))
        );
    }

    public List<PolicyResponse> getAll(String lclsfNm, String mclsfNm, String keyword) {
        Specification<Policy> spec = (root, query, cb) -> cb.conjunction();

        if (lclsfNm != null && !lclsfNm.isBlank()) {
            spec = spec.and(PolicySpecifications.lclsfNmIn(PolicyCategoryAlias.resolveLclsfNm(lclsfNm)));
        }
        if (mclsfNm != null && !mclsfNm.isBlank()) {
            spec = spec.and(PolicySpecifications.mclsfNmIn(PolicyCategoryAlias.resolveMclsfNm(mclsfNm)));
        }
        if (keyword != null && !keyword.isBlank()) {
            spec = spec.and(PolicySpecifications.keywordContains(keyword.trim()));
        }

        return policyRepository.findAll(spec).stream()
                .filter(PolicyApplicationPeriod::isOpen)
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public PolicyDetailResponse getDetail(Long policyId) {
        Policy policy = policyRepository.findById(policyId)
                .orElseThrow(() -> new BusinessException(ErrorCode.POLICY_NOT_FOUND));
        policyPopularityService.recordView(policyId);
        return toDetailResponse(policy);
    }

    private PolicyResponse toResponse(Policy policy) {
        return new PolicyResponse(
                policy.getId(),
                policy.getPlcyNo(),
                policy.getPlcyNm(),
                policy.getPlcyKywdNm(),
                policy.getPlcyExplnCn(),
                policy.getPlcySprtCn(),
                policy.getLclsfNm(),
                policy.getMclsfNm(),
                policy.getSprvsnInstNm(),
                policy.getAplyUrlAddr(),
                policy.getAplyPrdSeCd(),
                policy.getAplyYmd(),
                policy.getSprtTrgtMinAge(),
                policy.getSprtTrgtMaxAge(),
                policy.getViewCount()
        );
    }

    private PolicyDetailResponse toDetailResponse(Policy policy) {
        return new PolicyDetailResponse(
                policy.getId(),
                policy.getPlcyNo(),
                policy.getPlcyNm(),
                policy.getPlcyKywdNm(),
                policy.getPlcyExplnCn(),
                policy.getLclsfNm(),
                policy.getMclsfNm(),
                policy.getPlcySprtCn(),
                policy.getSprvsnInstNm(),
                policy.getAplyPrdSeCd(),
                policy.getAplyYmd(),
                policy.getPlcyAplyMthdCn(),
                policy.getSrngMthdCn(),
                policy.getAplyUrlAddr(),
                policy.getSbmsnDcmntCn(),
                policy.getSprtSclCnt(),
                policy.getSprtTrgtMinAge(),
                policy.getSprtTrgtMaxAge(),
                policy.getSprtTrgtAgeLmtYn(),
                policy.getMrgSttsCd(),
                policy.getEarnCndSeCd(),
                policy.getEarnMinAmt(),
                policy.getEarnMaxAmt(),
                policy.getEarnEtcCn(),
                policy.getAddAplyQlfcCndCn(),
                policy.getPtcpPrpTrgtCn(),
                policy.getZipCd(),
                policy.getSchoolCd(),
                policy.getJobCd(),
                policy.getPlcyMajorCd(),
                policy.getViewCount(),
                policy.getSrcRegDt(),
                policy.getSrcMdfcnDt()
        );
    }

    /** 좋아요 토글: 이미 눌렀으면 취소, 안 눌렀으면 등록 */
    @Transactional
    public void likeThisPolicy(Long policyId, Long memberId) {
        var existing = policyLikeRepository.findByMemberIdAndPolicyId(memberId, policyId);
        if (existing.isPresent()) {
            policyLikeRepository.delete(existing.get());
            return;
        }

        Policy policy = policyRepository.findById(policyId)
                .orElseThrow(() -> new BusinessException(ErrorCode.POLICY_NOT_FOUND));
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        policyLikeRepository.save(PolicyLike.builder()
                .member(member)
                .policy(policy)
                .build());
    }

    public List<PolicyResponse> getMyLike(Long memberId) {
        return policyLikeRepository.findByMemberId(memberId).stream()
                .map(PolicyLike::getPolicy)
                .map(this::toResponse)
                .toList();
    }

    public List<Long> getTop10() {
        List<Long> ranking = policyPopularityService.topPolicyIds();
        // 첫 10분 집계 전에는 빈 화면을 피하기 위해 기존 좋아요 순을 임시로 제공한다.
        return ranking.isEmpty() ? policyRepository.findByTopLike(PageRequest.of(0, 10)) : ranking;
    }
}
