package com.dive.backend.notification.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 인앱 알림함에 표시되는 알림 레코드. 푸시 발송 시 함께 저장되어,
 * 앱의 알림 패널이 이 데이터를 조회해 보여준다(푸시 미수신/웹에서도 확인 가능).
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "notification", indexes = @Index(name = "idx_notification_member", columnList = "member_id, created_at"))
public class Notification {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "notification_id")
    private Long id;

    @Column(name = "member_id", nullable = false)
    private Long memberId;

    @Column(nullable = false)
    private String title;

    @Column(nullable = false, length = 500)
    private String body;

    @Column(length = 30)
    private String type; // gonggu | policy | test | general

    @Column(name = "is_read", nullable = false)
    private boolean read;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    public void markRead() {
        this.read = true;
    }
}
