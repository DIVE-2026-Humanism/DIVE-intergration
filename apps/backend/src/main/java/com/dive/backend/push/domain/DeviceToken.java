package com.dive.backend.push.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 회원의 FCM 디바이스 토큰. 한 회원이 여러 기기를 가질 수 있어 1:N.
 * 토큰은 기기별 고유하므로 unique. 앱 재설치/토큰 갱신 시 upsert 한다.
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "device_token")
public class DeviceToken {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "device_token_id")
    private Long id;

    @Column(name = "member_id", nullable = false)
    private Long memberId;

    @Column(nullable = false, unique = true, length = 512)
    private String token;

    @Column(length = 20)
    private String platform; // ios | android | web

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public void touch(Long memberId, String platform) {
        this.memberId = memberId;
        this.platform = platform;
        this.updatedAt = LocalDateTime.now();
    }
}
