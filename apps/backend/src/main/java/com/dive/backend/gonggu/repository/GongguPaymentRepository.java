package com.dive.backend.gonggu.repository;

import com.dive.backend.gonggu.domain.GongguPayment;
import com.dive.backend.gonggu.domain.PaymentStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface GongguPaymentRepository extends JpaRepository<GongguPayment, Long> {

    Optional<GongguPayment> findByGongguIdAndMemberIdAndPaymentStatus(Long gongguId, Long memberId, PaymentStatus paymentStatus);
}
