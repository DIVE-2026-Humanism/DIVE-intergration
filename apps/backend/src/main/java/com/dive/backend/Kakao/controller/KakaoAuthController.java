package com.dive.backend.Kakao.controller;

import com.dive.backend.Kakao.service.KakaoAuthService;
import com.dive.backend.member.dto.RefreshRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;

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
     * 카카오 인증 서버가 호출하는 브라우저 콜백.
     *
     * 카카오 REST 로그인은 HTTP(S) Redirect URI만 등록할 수 있으므로, 받은 인가 코드와
     * state/error 값을 앱의 딥링크로 그대로 전달한다. 실제 토큰 교환은 앱이 기존
     * POST /api/auth/kakao 호출로 수행한다.
     */
    @GetMapping("/kakao/callback")
    public ResponseEntity<Void> kakaoCallback(
            @RequestParam(required = false) String code,
            @RequestParam(required = false) String state,
            @RequestParam(required = false) String error,
            @RequestParam(name = "error_description", required = false) String errorDescription) {
        UriComponentsBuilder redirect = UriComponentsBuilder.fromUriString("jabgonggu://auth");
        if (code != null) redirect.queryParam("code", code);
        if (state != null) redirect.queryParam("state", state);
        if (error != null) redirect.queryParam("error", error);
        if (errorDescription != null) redirect.queryParam("error_description", errorDescription);

        URI location = redirect.build().encode().toUri();
        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.LOCATION, location.toString())
                .build();
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

