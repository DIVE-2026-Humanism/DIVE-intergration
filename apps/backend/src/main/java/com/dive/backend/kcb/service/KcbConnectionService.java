package com.dive.backend.kcb.service;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import com.dive.backend.kcb.domain.KcbConnection;
import com.dive.backend.kcb.repository.KcbConnectionRepository;
import com.dive.backend.member.domain.Member;
import com.dive.backend.member.repository.MemberRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class KcbConnectionService {
    private final MemberRepository memberRepository;
    private final KcbConnectionRepository kcbConnectionRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public KcbConnection connectDummy(Long memberId) {
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        try {
            return kcbConnectionRepository.save(KcbConnection.builder()
                    .member(member).kcbRecordJson(objectMapper.writeValueAsString(dummyRecord()))
                    .dummy(true).build());
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("더미 KCB 데이터를 만들지 못했습니다.", exception);
        }
    }

    private Map<String, Object> dummyRecord() {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("성별", 1); r.put("연령대", 25); r.put("직업군", 420); r.put("거주지 시군구 코드", 26110); r.put("근무지 시군구 코드", 26110);
        r.put("추정월소득", 2500); r.put("증빙연소득", 20000); r.put("추정 연소득", 30000); r.put("2년전 추정 연소득 금액", 28000);
        r.put("총자산평가금액(주택)", 0); r.put("순자산평가금액(주택)", 0); r.put("자가거주여부", 0); r.put("현 거주지의 아파트여부", 0); r.put("현 거주지의 매매가(국토부 실거래가) 또는 공시가격", 0); r.put("차량보유(국산/수입)", 0); r.put("추정 LTV", 0); r.put("추정DTI", 0); r.put("신용평점", 850);
        r.put("총대출건수", 1); r.put("신용대출-총대출약정액", 10000); r.put("신용대출-총대출잔액", 10000); r.put("주택담보대출-총대출약정액", 0); r.put("주택담보대출-총대출잔액", 0); r.put("정책자금대출-총대출약정액", 0); r.put("정책자금대출-총대출잔액", 0); r.put("총 대출 상환금액 (최근 12개월)", 1200);
        r.put("최근 12개월 신용카드소비금액", 12000); r.put("최근 12개월 체크카드소비금액", 6000); r.put("최근 12개월 일시불이용금액", 10000); r.put("최근 12개월 할부이용금액", 2000); r.put("최근 12개월 현금서비스이용금액", 0); r.put("대출연체건수", 0); r.put("카드연체건수", 0); r.put("연체일수", 0); r.put("대출연체금액", 0); r.put("카드연체금액", 0); r.put("Thin Filer 여부", 0); r.put("파산, 개인회생 신청 여부", 0); r.put("2년내 현거주지평균실거래가", -99999999); r.put("2년내 현거주지평균전세거래가", -99999999); r.put("2년내 직장명이력건수", 1); r.put("2년내 이직후 소득 증감액", 2000);
        return r;
    }
}
