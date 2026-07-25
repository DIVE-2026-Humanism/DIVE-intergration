package com.dive.backend.member.service;

import com.dive.backend.member.domain.Member;
import com.dive.backend.member.dto.MemberResponse;
import com.dive.backend.member.dto.OnboardingRequest;
import com.dive.backend.member.dto.PasswordChangeRequest;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class MemberService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    public MemberResponse getMe(Long memberId) {
        Member member = findMember(memberId);
        return toResponse(member);
    }

    @Transactional
    public MemberResponse updateOnboarding(Long memberId, OnboardingRequest request) {
        Member member = findMember(memberId);
        member.updateOnboarding(request.career(), request.finalEducation());
        return toResponse(member);
    }

    private MemberResponse toResponse(Member member) {
        return new MemberResponse(
                member.getId(), member.getEmail(), member.getRole().name(),
                member.getCareer(), member.getFinalEducation());
    }

    @Transactional
    public void changePassword(Long memberId, PasswordChangeRequest request) {
        Member member = findMember(memberId);
        if (member.getPassword() == null || !passwordEncoder.matches(request.currentPassword(), member.getPassword())) {
            throw new BusinessException(ErrorCode.INVALID_PASSWORD);
        }
        member.updatePassword(passwordEncoder.encode(request.newPassword()));
    }

    @Transactional
    public void deleteMe(Long memberId) {
        Member member = findMember(memberId);
        memberRepository.delete(member);
        // 주의: 남아있는 Refresh Token은 Redis에 key=토큰문자열로 저장되어 있어 memberId로
        // 일괄 삭제가 안 됨 — 자연 TTL(7일)로 만료됨. 탈퇴 즉시 완전 무효화가 필요하면
        // RefreshToken에 memberId 보조 인덱스를 추가하는 걸 고려할 것.
    }

    private Member findMember(Long memberId) {
        return memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
    }
}
