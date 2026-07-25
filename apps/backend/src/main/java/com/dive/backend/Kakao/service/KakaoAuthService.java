package com.dive.backend.Kakao.service;

import com.dive.backend.Kakao.controller.KakaoAuthController;
import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.global.security.JwtProvider;
import com.dive.backend.global.security.RefreshToken;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.domain.TokenDto;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.member.repository.RefreshTokenRepository;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * 카카오 로그인 비즈니스 로직.
 *
 * 흐름: 인가코드 → 카카오 액세스 토큰 → 카카오 사용자 정보 → 회원 upsert(Member.kakaoId) → 자체 JWT 발급
 *
 * 세션 모델은 AuthService(이메일/비밀번호 로그인)와 동일하게 맞췄다: refresh token은
 * Member 컬럼이 아니라 Redis(RefreshTokenRepository)에 key=토큰, value=email로 저장하고,
 * 로그아웃 시 access token은 남은 만료시간만큼 Redis 블랙리스트에 등록한다.
 */
@Service
public class KakaoAuthService {

    // application.yml의 kakao.client-id, kakao.client-secret 값을 주입받는다.
    @Value("${kakao.client-id}")
    private String clientId;

    @Value("${kakao.client-secret}")
    private String clientSecret;

    private final RestClient kakaoAuthClient = RestClient.create("https://kauth.kakao.com");
    private final RestClient kakaoApiClient = RestClient.create("https://kapi.kakao.com");

    private final MemberRepository memberRepository;
    private final RefreshTokenRepository refreshTokenRepository;
    private final JwtProvider jwtProvider;
    private final RedisTemplate<String, Object> redisTemplate;

    public KakaoAuthService(MemberRepository memberRepository,
                            RefreshTokenRepository refreshTokenRepository,
                            JwtProvider jwtProvider,
                            RedisTemplate<String, Object> redisTemplate) {
        this.memberRepository = memberRepository;
        this.refreshTokenRepository = refreshTokenRepository;
        this.jwtProvider = jwtProvider;
        this.redisTemplate = redisTemplate;
    }

    /**
     * 카카오 로그인 전체 처리.
     */
    public KakaoAuthController.TokenResponse login(String code, String redirectUri) {
        KakaoTokenResponse kakaoToken = requestKakaoToken(code, redirectUri);
        KakaoUserResponse kakaoUser = requestKakaoUserInfo(kakaoToken.accessToken());

        Member member = memberRepository.findByKakaoId(String.valueOf(kakaoUser.id()))
                .map(existing -> updateProfile(existing, kakaoUser))
                .orElseGet(() -> createMember(kakaoUser));

        TokenDto tokenDto = jwtProvider.createTokenForSocial(
                member.getId(), member.getEmail(), member.getRole().name());
        saveRefreshToken(member.getEmail(), tokenDto.getRefreshToken());

        return new KakaoAuthController.TokenResponse(tokenDto.getAccessToken(), tokenDto.getRefreshToken());
    }

    /**
     * 로그아웃: 현재 AT를 Redis 블랙리스트에 등록(남은 만료시간만큼 TTL) + RT 삭제.
     * AuthService.logout과 동일한 방식.
     */
    public void logout(String accessToken, String refreshToken) {
        Long remainingMillis = jwtProvider.getExpiration(accessToken);
        if (remainingMillis > 0) {
            redisTemplate.opsForValue().set(accessToken, "logout", Duration.ofMillis(remainingMillis));
        }
        refreshTokenRepository.deleteById(refreshToken);
    }

    private void saveRefreshToken(String email, String refreshToken) {
        refreshTokenRepository.save(RefreshToken.builder()
                .key(refreshToken)
                .value(email)
                .build());
    }

    /**
     * 인가 코드를 카카오 access_token으로 교환한다.
     * POST https://kauth.kakao.com/oauth/token
     */
    private KakaoTokenResponse requestKakaoToken(String code, String redirectUri) {
        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "authorization_code");
        body.add("client_id", clientId);
        body.add("client_secret", clientSecret); // 보안 강화 시 발급받은 Client Secret
        body.add("redirect_uri", redirectUri);
        body.add("code", code);

        try {
            return kakaoAuthClient.post()
                    .uri("/oauth/token")
                    .contentType(org.springframework.http.MediaType.APPLICATION_FORM_URLENCODED)
                    .body(body)
                    .retrieve()
                    .body(KakaoTokenResponse.class);
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.AUTHENTICATION_FAILED);
        }
    }

    /**
     * access_token으로 카카오 사용자 정보를 조회한다.
     * GET https://kapi.kakao.com/v2/user/me
     */
    private KakaoUserResponse requestKakaoUserInfo(String accessToken) {
        return kakaoApiClient.get()
                .uri("/v2/user/me")
                .header("Authorization", "Bearer " + accessToken)
                .retrieve()
                .body(KakaoUserResponse.class);
    }

    private Member createMember(KakaoUserResponse kakaoUser) {
        Member member = Member.createFromKakao(
                String.valueOf(kakaoUser.id()),
                extractNickname(kakaoUser),
                extractEmail(kakaoUser)
        );
        return memberRepository.save(member);
    }

    private Member updateProfile(Member member, KakaoUserResponse kakaoUser) {
        member.updateProfile(extractNickname(kakaoUser), extractEmail(kakaoUser));
        return memberRepository.save(member);
    }

    /**
     * 카카오 로그인 동의항목(닉네임/카카오계정)에 따라 kakao_account 또는
     * profile이 응답에서 아예 빠질 수 있어 null-safe하게 꺼낸다.
     */
    private String extractNickname(KakaoUserResponse kakaoUser) {
        if (kakaoUser.kakaoAccount() == null || kakaoUser.kakaoAccount().profile() == null) {
            return "카카오사용자" + kakaoUser.id();
        }
        return kakaoUser.kakaoAccount().profile().nickname();
    }

    /**
     * 카카오 계정이 이메일 동의를 안 하면 email이 null이다. 그런데 이메일을 principal username /
     * JWT subject / refresh 매핑 키로 쓰기 때문에 null이면 로그인 이후 흐름이 전부 깨진다.
     * 따라서 이메일이 없으면 kakaoId 기반의 고유한 합성 이메일을 부여한다.
     */
    private String extractEmail(KakaoUserResponse kakaoUser) {
        String email = kakaoUser.kakaoAccount() == null ? null : kakaoUser.kakaoAccount().email();
        if (email == null || email.isBlank()) {
            return "kakao_" + kakaoUser.id() + "@kakao.local";
        }
        return email;
    }

    // ------------------------------------------------------------
    // 카카오 응답 DTO
    // ------------------------------------------------------------

    /** 카카오 토큰 응답 (필요한 필드만 매핑, 원본 JSON은 snake_case) */
    private record KakaoTokenResponse(
            @JsonProperty("token_type") String tokenType,
            @JsonProperty("access_token") String accessToken,
            @JsonProperty("refresh_token") String refreshToken,
            @JsonProperty("expires_in") Integer expiresIn
    ) {}

    /** 카카오 사용자 정보 응답 (필요한 필드만 매핑, 원본 JSON은 snake_case) */
    private record KakaoUserResponse(
            Long id,
            @JsonProperty("kakao_account") KakaoAccount kakaoAccount
    ) {
        private record KakaoAccount(String email, Profile profile) {
            private record Profile(String nickname) {}
        }
    }
}
