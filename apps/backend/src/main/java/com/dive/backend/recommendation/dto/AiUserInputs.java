package com.dive.backend.recommendation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;

/** AI 서버 /v1/diagnose의 user_inputs 계약. enum 값은 AI 서버 /v1/meta와 일치해야 한다. */
public record AiUserInputs(
        @JsonProperty("성별") @NotBlank String gender,
        @JsonProperty("결혼여부") @NotBlank String marriageStatus,
        @JsonProperty("연소득") @NotNull @Min(0) Integer annualIncome,
        @JsonProperty("직업군") @NotBlank String occupation,
        @JsonProperty("학력") @NotBlank String education,
        @JsonProperty("특화") @NotNull List<String> specializations,
        @JsonProperty("사는곳") @NotBlank String residence,
        @JsonProperty("나이") @NotNull @Min(0) @Max(120) Integer age
) { }
