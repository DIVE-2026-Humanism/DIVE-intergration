package com.dive.backend.member.dto;

import jakarta.validation.constraints.NotBlank;

public record OnboardingRequest(
        @NotBlank String career,
        @NotBlank String finalEducation
) {
}
