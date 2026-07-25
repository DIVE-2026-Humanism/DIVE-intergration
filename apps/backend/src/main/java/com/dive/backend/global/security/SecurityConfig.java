package com.dive.backend.global.security;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * Security 총괄 설정. runApp의 MonitoringPasswordFilter(actuator/prometheus 보호용,
 * 러닝 앱 배포 환경 전용)는 범용 보일러플레이트라 제외했다 — 필요하면 원본
 * (github.com/proteinJ/runApp global/security/MonitoringPasswordFilter.java) 참고해서 추가.
 */
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtProvider jwtProvider;
    private final RedisTemplate<String, Object> redisTemplate;
    private final CustomAuthenticationEntryPoint authenticationEntryPoint;

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .csrf(AbstractHttpConfigurer::disable)
            .formLogin(AbstractHttpConfigurer::disable)
            .httpBasic(AbstractHttpConfigurer::disable)

            // JWT 사용하므로 세션 생성하지 않음 (STATELESS)
            .sessionManagement(session ->
                    session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

            .exceptionHandling(exception -> exception
                    .authenticationEntryPoint(authenticationEntryPoint)
            )

            // 새 프로젝트에서 도메인 늘어나면 이 목록에 공개 엔드포인트 추가
            .authorizeHttpRequests(auth -> auth
                    .requestMatchers(
                            "/api/v1/auth/signup", "/api/v1/auth/login", "/api/v1/auth/refresh",
                            "/api/auth/kakao", "/api/auth/kakao/callback",
                            "/api/v1/policy/all", "/api/v1/policy/categories",
                            "/api/auth/kakao",
                            "/images/**",
                            "/api/v1/gonggu/payment/approve", "/api/v1/gonggu/payment/cancel", "/api/v1/gonggu/payment/fail",
                            "/swagger-ui/**", "/swagger-ui.html", "/v3/api-docs/**",
                            "/actuator/health", "/actuator/info"
                    ).permitAll()
                    .anyRequest().authenticated()
            )

            // 일반 로그인 필터(UsernamePasswordAuthenticationFilter) 작동 전에 JWT 필터가 먼저 실행되도록
            .addFilterBefore(new JwtAuthenticationFilter(jwtProvider, redisTemplate),
                    UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration authenticationConfiguration) throws Exception {
        return authenticationConfiguration.getAuthenticationManager();
    }

    /**
     * CORS 설정. Expo 웹(dev)은 포트가 유동적(8081/8082/8090/19006 등)이라 localhost/127.0.0.1의
     * 모든 포트를 패턴으로 허용한다. 운영 배포 시에는 실제 도메인으로 좁힐 것.
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOriginPatterns(List.of("http://localhost:*", "http://127.0.0.1:*"));
        config.setAllowedMethods(List.of("GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setExposedHeaders(List.of("Authorization"));
        config.setAllowCredentials(true);
        config.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
