package com.dive.backend.gonggu.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.gonggu.client.KakaoPayApproveRequest;
import com.dive.backend.gonggu.client.KakaoPayApproveResponse;
import com.dive.backend.gonggu.client.KakaoPayCancelRequest;
import com.dive.backend.gonggu.client.KakaoPayClient;
import com.dive.backend.gonggu.client.KakaoPayReadyRequest;
import com.dive.backend.gonggu.client.KakaoPayReadyResponse;
import com.dive.backend.gonggu.domain.Gonggu;
import com.dive.backend.gonggu.domain.GongguPayment;
import com.dive.backend.gonggu.domain.PaymentStatus;
import com.dive.backend.gonggu.domain.Status;
import com.dive.backend.gonggu.dto.KakaoPayReadyResult;
import com.dive.backend.gonggu.repository.GongguPaymentRepository;
import com.dive.backend.gonggu.repository.GongguRepository;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class GongguPaymentService {

    private final GongguRepository gongguRepository;
    private final GongguPaymentRepository gongguPaymentRepository;
    private final MemberRepository memberRepository;
    private final KakaoPayClient kakaoPayClient;

    @Value("${kakaopay.cid}")
    private String cid;

    @Value("${kakaopay.approval-url}")
    private String approvalUrlBase;

    @Value("${kakaopay.cancel-url}")
    private String cancelUrlBase;

    @Value("${kakaopay.fail-url}")
    private String failUrlBase;

    @Transactional
    public KakaoPayReadyResult ready(Long gongguId, Long memberId) {
        Gonggu gonggu = gongguRepository.findById(gongguId)
                .orElseThrow(() -> new BusinessException(ErrorCode.GONGGU_NOT_FOUND));

        if (gonggu.getStatus() != Status.RECRUITING) {
            throw new BusinessException(ErrorCode.GONGGU_NOT_RECRUITING);
        }

        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        gongguPaymentRepository.findByGongguIdAndMemberIdAndPaymentStatus(gongguId, memberId, PaymentStatus.PAID)
                .ifPresent(p -> { throw new BusinessException(ErrorCode.GONGGU_ALREADY_PAID); });

        GongguPayment payment = gongguPaymentRepository.save(GongguPayment.builder()
                .gonggu(gonggu)
                .member(member)
                .amount(gonggu.getPrice())
                .build());

        KakaoPayReadyResponse response = kakaoPayClient.ready(new KakaoPayReadyRequest(
                cid,
                String.valueOf(payment.getId()),
                String.valueOf(memberId),
                gonggu.getTitle(),
                1,
                gonggu.getPrice(),
                0,
                approvalUrlBase + "?paymentId=" + payment.getId(),
                cancelUrlBase + "?paymentId=" + payment.getId(),
                failUrlBase + "?paymentId=" + payment.getId()
        ));

        payment.assignTid(response.tid());

        return new KakaoPayReadyResult(payment.getId(), response.nextRedirectPcUrl(), response.nextRedirectMobileUrl());
    }

    @Transactional
    public void approve(Long paymentId, String pgToken) {
        GongguPayment payment = gongguPaymentRepository.findById(paymentId)
                .orElseThrow(() -> new BusinessException(ErrorCode.GONGGU_PAYMENT_NOT_FOUND));

        KakaoPayApproveResponse response = kakaoPayClient.approve(new KakaoPayApproveRequest(
                cid,
                payment.getPgTid(),
                String.valueOf(payment.getId()),
                String.valueOf(payment.getMember().getId()),
                pgToken
        ));

        payment.approve(response.paymentMethodType());

        Gonggu gonggu = payment.getGonggu();
        gonggu.increaseCurrentCount();
        if (gonggu.getCurrentCount() >= gonggu.getTargetCount()) {
            gonggu.completeFunding();
        }
    }

    @Transactional
    public void cancel(Long paymentId) {
        gongguPaymentRepository.findById(paymentId)
                .orElseThrow(() -> new BusinessException(ErrorCode.GONGGU_PAYMENT_NOT_FOUND))
                .cancel();
    }

    @Transactional
    public void fail(Long paymentId) {
        gongguPaymentRepository.findById(paymentId)
                .orElseThrow(() -> new BusinessException(ErrorCode.GONGGU_PAYMENT_NOT_FOUND))
                .cancel();
    }

    /** 마감일이 지났는데 목표 인원을 못 채운 공구를 찾아 펀딩 실패 처리하고, 이미 결제된 건은 환불한다 */
    @Transactional
    public void processExpiredFundings() {
        List<Gonggu> expired = gongguRepository.findAllByStatusAndEndDateBefore(Status.RECRUITING, LocalDateTime.now());

        for (Gonggu gonggu : expired) {
            if (gonggu.getCurrentCount() >= gonggu.getTargetCount()) {
                continue;
            }

            gonggu.failFunding();

            List<GongguPayment> paidPayments = gongguPaymentRepository.findAllByGongguIdAndPaymentStatus(gonggu.getId(), PaymentStatus.PAID);
            for (GongguPayment payment : paidPayments) {
                refund(payment);
            }
        }
    }

    private void refund(GongguPayment payment) {
        try {
            kakaoPayClient.cancel(new KakaoPayCancelRequest(cid, payment.getPgTid(), payment.getAmount(), 0));
            payment.refund();
        } catch (Exception e) {
            log.error("공구 환불 실패: gongguId={}, paymentId={}", payment.getGonggu().getId(), payment.getId(), e);
        }
    }
}
