package com.dive.backend.notification;

import com.dive.backend.notification.domain.NotificationSetting;
import com.dive.backend.notification.dto.NotificationSettingRequest;
import com.dive.backend.notification.dto.NotificationSettingResponse;
import com.dive.backend.notification.repository.NotificationSettingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class NotificationSettingService {

    private final NotificationSettingRepository repository;

    @Transactional
    public NotificationSettingResponse get(Long memberId) {
        return NotificationSettingResponse.from(getOrCreate(memberId));
    }

    @Transactional
    public NotificationSettingResponse update(Long memberId, NotificationSettingRequest req) {
        NotificationSetting setting = getOrCreate(memberId);
        setting.update(req.gonggu(), req.policy(), req.marketing());
        return NotificationSettingResponse.from(setting);
    }

    /**
     * 발송 판단용. 설정이 없으면 기본값(공구/정책 ON, 마케팅 OFF)으로 간주하며 row는 만들지 않는다.
     * test/general 등 알 수 없는 유형은 항상 허용한다.
     */
    @Transactional(readOnly = true)
    public boolean isEnabled(Long memberId, String type) {
        return repository.findByMemberId(memberId)
                .map(s -> switch (type) {
                    case "gonggu" -> s.isGonggu();
                    case "policy" -> s.isPolicy();
                    case "marketing" -> s.isMarketing();
                    default -> true;
                })
                .orElseGet(() -> !"marketing".equals(type)); // 기본: 마케팅만 OFF
    }

    private NotificationSetting getOrCreate(Long memberId) {
        return repository.findByMemberId(memberId)
                .orElseGet(() -> repository.save(NotificationSetting.defaultsFor(memberId)));
    }
}
