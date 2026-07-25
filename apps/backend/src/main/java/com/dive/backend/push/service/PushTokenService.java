package com.dive.backend.push.service;

import com.dive.backend.push.domain.DeviceToken;
import com.dive.backend.push.repository.DeviceTokenRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class PushTokenService {

    private final DeviceTokenRepository deviceTokenRepository;

    /**
     * 디바이스 토큰 upsert. 같은 토큰이 이미 있으면 소유 회원/플랫폼만 갱신한다
     * (기기 공유·재로그인 대응).
     */
    @Transactional
    public void register(Long memberId, String token, String platform) {
        deviceTokenRepository.findByToken(token)
                .ifPresentOrElse(
                        existing -> existing.touch(memberId, platform),
                        () -> deviceTokenRepository.save(DeviceToken.builder()
                                .memberId(memberId)
                                .token(token)
                                .platform(platform)
                                .updatedAt(LocalDateTime.now())
                                .build())
                );
    }

    @Transactional
    public void unregister(String token) {
        deviceTokenRepository.deleteByToken(token);
    }
}
