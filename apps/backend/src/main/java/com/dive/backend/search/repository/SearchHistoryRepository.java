package com.dive.backend.search.repository;

import com.dive.backend.search.domain.SearchHistory;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SearchHistoryRepository extends JpaRepository<SearchHistory, Long> {

    List<SearchHistory> findByMemberIdOrderByCreatedAtDesc(Long memberId);

    List<SearchHistory> findByMemberIdOrderByCreatedAtDesc(Long memberId, Pageable pageable);

    Optional<SearchHistory> findByMemberIdAndKeyword(Long memberId, String keyword);

    void deleteByMemberIdAndKeyword(Long memberId, String keyword);

    void deleteByMemberId(Long memberId);
}
