package com.dive.backend.member.domain;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "member")
public class Member {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "member_id")
    private Long id;

    @Column(unique = true, length = 100)
    private String email; // 카카오 계정이 이메일 동의를 안 하면 null일 수 있어 unique=true만 유지

    @Column
    private String password; // 소셜 로그인 전용 계정이면 null 허용

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role;

    @Column(name = "kakao_id", unique = true)
    private String kakaoId;

    private String nickname;

    @Column(nullable = false)
    private String career;

    @Column(nullable = false)
    private String finalEducation;

    public void updatePassword(String password) {
        this.password = password;
    }

    public void updateProfile(String nickname, String email) {
        this.nickname = nickname;
        this.email = email;
    }

    public static Member createFromKakao(String kakaoId, String nickname, String email) {
        return Member.builder()
                .kakaoId(kakaoId)
                .nickname(nickname)
                .email(email)
                .role(Role.USER)
                .career("미입력") // 온보딩에서 실제 값 입력받으면 교체
                .finalEducation("미입력")
                .build();
    }

    public void updateOnboarding(String career, String finalEducation) {
        this.career = career;
        this.finalEducation = finalEducation;
    }

    public void updateMyProfile(String nickname, String career, String finalEducation) {
        this.nickname = nickname;
        this.career = career;
        this.finalEducation = finalEducation;
    }
}
