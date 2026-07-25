package com.dive.backend.notification.domain;

import jakarta.persistence.*;
import lombok.*;

/**
 * 회원별 알림 수신 설정. 발송 시 해당 유형의 토글이 꺼져 있으면 알림을 보내지 않는다.
 * 기본값: 공구/정책 ON, 마케팅 OFF.
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "notification_setting")
public class NotificationSetting {

    @Id
    @Column(name = "member_id")
    private Long memberId;

    @Column(nullable = false)
    private boolean gonggu;

    @Column(nullable = false)
    private boolean policy;

    @Column(nullable = false)
    private boolean marketing;

    public static NotificationSetting defaultsFor(Long memberId) {
        return NotificationSetting.builder()
                .memberId(memberId)
                .gonggu(true)
                .policy(true)
                .marketing(false)
                .build();
    }

    /** null인 항목은 변경하지 않는다(부분 업데이트). */
    public void update(Boolean gonggu, Boolean policy, Boolean marketing) {
        if (gonggu != null) this.gonggu = gonggu;
        if (policy != null) this.policy = policy;
        if (marketing != null) this.marketing = marketing;
    }
}
