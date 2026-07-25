package com.dive.backend.Kakao.controller;

import com.dive.backend.Kakao.service.KakaoAuthService;
import com.dive.backend.member.dto.RefreshRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * 카카오 로그인 콜백을 처리하는 컨트롤러.
 * 프론트엔드(React)가 카카오로부터 받은 인가 코드(code)를 이 엔드포인트로 전달하면,
 * 서버가 카카오 토큰 교환 → 사용자 정보 조회 → 회원 upsert → 자체 JWT 발급까지 수행한다.
 */
@RestController
@RequestMapping("/api/auth")
public class KakaoAuthController {

    private final KakaoAuthService kakaoAuthService;

    public KakaoAuthController(KakaoAuthService kakaoAuthService) {
        this.kakaoAuthService = kakaoAuthService;
    }

    /**
     * 카카오 로그인 처리
     * @param request 프론트에서 전달한 인가 코드와 redirect_uri
     * @return 자체 발급 access/refresh 토큰
     */
    @PostMapping("/kakao")
    public ResponseEntity<TokenResponse> kakaoLogin(@Valid @RequestBody KakaoLoginRequest request) {
        TokenResponse tokenResponse = kakaoAuthService.login(request.code(), request.redirectUri());
        return ResponseEntity.ok(tokenResponse);
    }

    /**
     * 로그아웃
     * AT는 남은 만료시간만큼 Redis 블랙리스트에 등록하고, RT는 삭제한다.
     * (AuthController.logout과 동일한 방식)
     */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(
            @RequestHeader("Authorization") String authorizationHeader,
            @Valid @RequestBody RefreshRequest request) {
        String accessToken = authorizationHeader.replace("Bearer ", "");
        kakaoAuthService.logout(accessToken, request.refreshToken());
        return ResponseEntity.noContent().build();
    }

    public record KakaoLoginRequest(
            @NotBlank String code,
            @NotBlank String redirectUri
    ) {}

    public record TokenResponse(
            String accessToken,
            String refreshToken
    ) {}
}

