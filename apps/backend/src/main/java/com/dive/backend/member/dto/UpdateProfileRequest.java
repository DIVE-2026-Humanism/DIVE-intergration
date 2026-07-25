package com.dive.backend.member.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdateProfileRequest(
        @NotBlank @Size(max = 50) String nickname,
        @NotBlank @Size(max = 100) String career,
        @NotBlank @Size(max = 100) String finalEducation
) { }
