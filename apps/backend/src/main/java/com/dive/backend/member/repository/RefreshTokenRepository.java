package com.dive.backend.member.repository;

import com.dive.backend.global.security.RefreshToken;
import org.springframework.data.repository.CrudRepository;

public interface RefreshTokenRepository extends CrudRepository<RefreshToken, String> {

    void deleteByKey(String key);
}
