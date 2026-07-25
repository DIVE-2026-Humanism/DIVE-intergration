package com.dive.backend.policy.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.policy.domain.Policy;
import com.dive.backend.policy.domain.PolicyLike;
import com.dive.backend.policy.dto.PolicyDetailResponse;
import com.dive.backend.policy.dto.PolicyResponse;
import com.dive.backend.policy.repository.PolicyLikeRepository;
import com.dive.backend.policy.repository.PolicyRepository;
import com.dive.backend.policy.repository.PolicySpecifications;
import lombok.RequiredArgsConstructor;
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

    public List<PolicyResponse> getAll(String lclsfNm, String mclsfNm) {
        Specification<Policy> spec = (root, query, cb) -> cb.conjunction();

        if (lclsfNm != null && !lclsfNm.isBlank()) {
            spec = spec.and(PolicySpecifications.lclsfNmIn(PolicyCategoryAlias.resolveLclsfNm(lclsfNm)));
        }
        if (mclsfNm != null && !mclsfNm.isBlank()) {
            spec = spec.and(PolicySpecifications.mclsfNmIn(PolicyCategoryAlias.resolveMclsfNm(mclsfNm)));
        }

        return policyRepository.findAll(spec).stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public PolicyDetailResponse getDetail(Long policyId) {
        Policy policy = policyRepository.findById(policyId)
                .orElseThrow(() -> new BusinessException(ErrorCode.POLICY_NOT_FOUND));
        policy.increaseViewCount();
        return toDetailResponse(policy);
    }

    private PolicyResponse toResponse(Policy policy) {
        return new PolicyResponse(
                policy.getId(),
                policy.getPlcyNo(),
                policy.getPlcyNm(),
                policy.getPlcyKywdNm(),
                policy.getPlcyExplnCn(),
                policy.getLclsfNm(),
                policy.getMclsfNm(),
                policy.getSprvsnInstNm(),
                policy.getAplyUrlAddr(),
                policy.getAplyPrdSeCd(),
                policy.getAplyYmd(),
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
}
