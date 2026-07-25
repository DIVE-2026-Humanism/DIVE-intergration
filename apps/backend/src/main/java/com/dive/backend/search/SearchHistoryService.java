package com.dive.backend.search;

import com.dive.backend.search.domain.SearchHistory;
import com.dive.backend.search.repository.SearchHistoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class SearchHistoryService {

    private static final int MAX = 10;

    private final SearchHistoryRepository repository;

    /** 검색어 기록. 중복이면 맨 위로 올리고, 10개 초과분은 오래된 것부터 삭제. */
    @Transactional
    public void add(Long memberId, String keyword) {
        if (keyword == null) return;
        String k = keyword.trim();
        if (k.isEmpty()) return;

        repository.findByMemberIdAndKeyword(memberId, k).ifPresent(repository::delete);
        repository.save(SearchHistory.builder()
                .memberId(memberId)
                .keyword(k)
                .createdAt(LocalDateTime.now())
                .build());

        List<SearchHistory> all = repository.findByMemberIdOrderByCreatedAtDesc(memberId);
        if (all.size() > MAX) {
            all.subList(MAX, all.size()).forEach(repository::delete);
        }
    }

    @Transactional(readOnly = true)
    public List<String> list(Long memberId) {
        return repository.findByMemberIdOrderByCreatedAtDesc(memberId, PageRequest.of(0, MAX))
                .stream().map(SearchHistory::getKeyword).toList();
    }

    @Transactional
    public void remove(Long memberId, String keyword) {
        repository.deleteByMemberIdAndKeyword(memberId, keyword);
    }

    @Transactional
    public void clear(Long memberId) {
        repository.deleteByMemberId(memberId);
    }
}
