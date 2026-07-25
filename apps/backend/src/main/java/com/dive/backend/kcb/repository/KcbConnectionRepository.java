package com.dive.backend.kcb.repository;
import com.dive.backend.kcb.domain.KcbConnection;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
public interface KcbConnectionRepository extends JpaRepository<KcbConnection, Long> {
    Optional<KcbConnection> findTopByMember_IdOrderByCreatedAtDesc(Long memberId);
}
