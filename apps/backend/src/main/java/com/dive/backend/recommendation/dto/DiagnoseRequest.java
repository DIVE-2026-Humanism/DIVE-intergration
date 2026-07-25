package com.dive.backend.recommendation.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record DiagnoseRequest(
        @NotNull(message = "신용 점수가 필요합니다.")
        @Min(value = 0, message = "신용 점수는 0 이상이어야 합니다.")
        @Max(value = 100, message = "신용 점수는 100 이하여야 합니다.")
        Integer creditScore,
        @Valid UserInputsOverride userInputsOverride
) {
}
