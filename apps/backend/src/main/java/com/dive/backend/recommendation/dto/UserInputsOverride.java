package com.dive.backend.recommendation.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record UserInputsOverride(
        @Min(value = 0, message = "나이는 0 이상이어야 합니다.") @Max(value = 120, message = "나이는 120 이하여야 합니다.") Integer age,
        String regionCode,
        @Min(value = 0, message = "연소득은 0 이상이어야 합니다.") Integer annualIncome,
        String jobCode,
        String schoolCode,
        String marriageCode,
        String specializationCode
) {
}
