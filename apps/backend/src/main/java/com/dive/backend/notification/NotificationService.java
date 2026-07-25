package com.dive.backend.notification;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.notification.domain.Notification;
import com.dive.backend.notification.dto.NotificationResponse;
import com.dive.backend.notification.repository.NotificationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 인앱 알림함 저장/조회 서비스.
 */
@Service
@RequiredArgsConstructor
public class NotificationService {

    private static final int MAX_LIST = 50;

    private final NotificationRepository notificationRepository;

    /** 알림 저장 (이벤트 리스너에서 호출) */
    @Transactional
    public void record(Long memberId, String title, String body, String type) {
        notificationRepository.save(Notification.builder()
                .memberId(memberId)
                .title(title)
                .body(body)
                .type(type)
                .read(false)
                .createdAt(LocalDateTime.now())
                .build());
    }

    @Transactional(readOnly = true)
    public List<NotificationResponse> list(Long memberId) {
        return notificationRepository
                .findByMemberIdOrderByCreatedAtDesc(memberId, PageRequest.of(0, MAX_LIST))
                .stream().map(NotificationResponse::from).toList();
    }

    @Transactional(readOnly = true)
    public long unreadCount(Long memberId) {
        return notificationRepository.countByMemberIdAndReadFalse(memberId);
    }

    @Transactional
    public void markRead(Long memberId, Long notificationId) {
        Notification n = notificationRepository.findById(notificationId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOTIFICATION_NOT_FOUND));
        if (!n.getMemberId().equals(memberId)) {
            throw new BusinessException(ErrorCode.ACCESS_DENIED);
        }
        n.markRead();
    }

    @Transactional
    public void markAllRead(Long memberId) {
        notificationRepository.findByMemberIdOrderByCreatedAtDesc(memberId, PageRequest.of(0, MAX_LIST))
                .forEach(Notification::markRead);
    }
}
