package com.dive.backend.gonggu.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.global.file.FileStorageService;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import com.dive.backend.gonggu.domain.Gonggu;
import com.dive.backend.gonggu.domain.GongguLike;
import com.dive.backend.gonggu.dto.GongguDetailResponse;
import com.dive.backend.gonggu.dto.GongguRequest;
import com.dive.backend.gonggu.dto.GongguResponse;
import com.dive.backend.gonggu.repository.GongguLikeRepository;
import com.dive.backend.gonggu.repository.GongguRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class GongguService {

    private final GongguRepository gongguRepository;
    private final GongguLikeRepository gongguLikeRepository;
    private final MemberRepository memberRepository;
    private final FileStorageService fileStorageService;

    @Transactional
    public Long create(Long memberId, GongguRequest request, MultipartFile image) {
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        Gonggu gonggu = Gonggu.builder()
                .member(member)
                .title(request.title())
                .content(request.content())
                .price(request.price())
                .targetCount(request.targetCount())
                .startDate(request.startDate())
                .endDate(request.endDate())
                .imageUrl(fileStorageService.store(image))
                .productUrl(blankToNull(request.productUrl()))
                .build();

        return gongguRepository.save(gonggu).getId();
    }

    public List<GongguResponse> getAll() {
        return gongguRepository.findAllByOrderByCreatedAtDesc().stream()
                .map(this::toResponse)
                .toList();
    }

    public GongguDetailResponse getDetail(Long gongguId) {
        Gonggu gonggu = gongguRepository.findById(gongguId)
                .orElseThrow(() -> new BusinessException(ErrorCode.GONGGU_NOT_FOUND));
        return toDetailResponse(gonggu);
    }

    /** 좋아요 토글: 이미 눌렀으면 취소, 안 눌렀으면 등록 */
    @Transactional
    public void likeThisGonggu(Long gongguId, Long memberId) {
        var existing = gongguLikeRepository.findByMemberIdAndGongguId(memberId, gongguId);
        if (existing.isPresent()) {
            gongguLikeRepository.delete(existing.get());
            return;
        }

        Gonggu gonggu = gongguRepository.findById(gongguId)
                .orElseThrow(() -> new BusinessException(ErrorCode.GONGGU_NOT_FOUND));
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        gongguLikeRepository.save(GongguLike.builder()
                .member(member)
                .gonggu(gonggu)
                .build());
    }

    public List<GongguResponse> getMyLike(Long memberId) {
        return gongguLikeRepository.findByMemberId(memberId).stream()
                .map(GongguLike::getGonggu)
                .map(this::toResponse)
                .toList();
    }

    private GongguResponse toResponse(Gonggu gonggu) {
        return new GongguResponse(
                gonggu.getId(),
                gonggu.getMember().getNickname(),
                gonggu.getTitle(),
                gonggu.getPrice(),
                gonggu.getTargetCount(),
                gonggu.getCurrentCount(),
                gonggu.getStatus(),
                gonggu.getStartDate(),
                gonggu.getEndDate(),
                gonggu.getImageUrl(),
                gonggu.getProductUrl()
        );
    }

    private GongguDetailResponse toDetailResponse(Gonggu gonggu) {
        return new GongguDetailResponse(
                gonggu.getId(),
                gonggu.getMember().getNickname(),
                gonggu.getTitle(),
                gonggu.getContent(),
                gonggu.getPrice(),
                gonggu.getTargetCount(),
                gonggu.getCurrentCount(),
                gonggu.getStatus(),
                gonggu.getStartDate(),
                gonggu.getEndDate(),
                gonggu.getImageUrl(),
                gonggu.getProductUrl(),
                gonggu.getCreatedAt()
        );
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
