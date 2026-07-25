package com.dive.backend.member.dto;

public record MemberResponse(
        Long id,
        String email,
        String nickname,
        String role,
        String career,
        String finalEducation
) {
}
