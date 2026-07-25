package com.dive.backend.policy.controller;

import com.dive.backend.global.common.ApiResponse;
import com.dive.backend.policy.service.PolicySyncService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/policies")
@RequiredArgsConstructor
public class PolicySyncController {

    private final PolicySyncService policySyncService;

    @PostMapping("/sync")
    public ApiResponse<Void> sync() {
        policySyncService.syncAll();
        return ApiResponse.success("정책 동기화 완료");
    }
}
