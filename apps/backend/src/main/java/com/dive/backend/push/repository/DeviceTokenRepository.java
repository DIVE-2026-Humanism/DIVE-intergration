package com.dive.backend.push.repository;

import com.dive.backend.push.domain.DeviceToken;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DeviceTokenRepository extends JpaRepository<DeviceToken, Long> {

    Optional<DeviceToken> findByToken(String token);

    List<DeviceToken> findByMemberId(Long memberId);

    void deleteByToken(String token);
}
