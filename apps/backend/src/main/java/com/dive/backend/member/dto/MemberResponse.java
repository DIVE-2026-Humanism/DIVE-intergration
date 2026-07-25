package com.dive.backend.member.dto;

public record MemberResponse(
        Long id,
        String email,
        String role
) {
}
