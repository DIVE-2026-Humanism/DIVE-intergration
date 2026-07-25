package com.dive.backend.gonggu.repository;

import com.dive.backend.gonggu.domain.GongguLike;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface GongguLikeRepository extends JpaRepository<GongguLike, Long> {

    Optional<GongguLike> findByMemberIdAndGongguId(Long memberId, Long gongguId);

    List<GongguLike> findByMemberId(Long memberId);
}
