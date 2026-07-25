package com.dive.backend.recommendation.dto;

import jakarta.validation.Valid;

// 점수는 서버가 연동 저장된 KCB(kcb_connection)를 /v1/economic-feedback로 보내 산정한다.
// 따라서 요청에 KCB 원본을 담지 않는다. 온보딩값만 선택적으로 덮어쓴다.
public record DiagnoseRequest(
        @Valid UserInputsOverride userInputsOverride
) {
}
