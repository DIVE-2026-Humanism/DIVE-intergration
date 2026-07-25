package com.dive.backend.push.service;

import com.dive.backend.push.domain.DeviceToken;
import com.dive.backend.push.repository.DeviceTokenRepository;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

/**
 * FCM 발송 서비스. 회원의 모든 디바이스 토큰으로 알림을 보낸다.
 * 만료/무효 토큰(UNREGISTERED, INVALID_ARGUMENT)은 자동으로 정리한다.
 *
 * 사용 예: 공구 신규 참여 발생 시 등록자에게, 정책 마감 임박 시 관심 회원에게.
 *   fcmService.sendToMember(memberId, "추가 구매 알림",
 *       "등록하신 무선 사무의자 공구에 새로운 참여자가 생겼어요", Map.of("type", "gonggu"));
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FcmService {

    private final DeviceTokenRepository deviceTokenRepository;

    /** 특정 회원의 모든 기기로 발송. 반환값은 성공 건수. */
    @Transactional
    public int sendToMember(Long memberId, String title, String body, Map<String, String> data) {
        if (FirebaseApp.getApps().isEmpty()) {
            log.warn("[FCM] Firebase 미초기화 — 발송 건너뜀 (memberId={})", memberId);
            return 0;
        }
        List<DeviceToken> tokens = deviceTokenRepository.findByMemberId(memberId);
        int sent = 0;
        for (DeviceToken dt : tokens) {
            if (sendToToken(dt.getToken(), title, body, data)) sent++;
        }
        return sent;
    }

    /** 단일 토큰 발송. 성공 여부 반환. 무효 토큰이면 삭제. */
    @Transactional
    public boolean sendToToken(String token, String title, String body, Map<String, String> data) {
        if (FirebaseApp.getApps().isEmpty()) return false;

        Message.Builder builder = Message.builder()
                .setToken(token)
                .setNotification(Notification.builder().setTitle(title).setBody(body).build());
        if (data != null && !data.isEmpty()) builder.putAllData(data);

        try {
            FirebaseMessaging.getInstance().send(builder.build());
            return true;
        } catch (FirebaseMessagingException e) {
            MessagingErrorCode code = e.getMessagingErrorCode();
            if (code == MessagingErrorCode.UNREGISTERED || code == MessagingErrorCode.INVALID_ARGUMENT) {
                log.info("[FCM] 무효 토큰 삭제: {}", code);
                deviceTokenRepository.deleteByToken(token);
            } else {
                log.error("[FCM] 발송 실패 (code={})", code, e);
            }
            return false;
        }
    }
}
