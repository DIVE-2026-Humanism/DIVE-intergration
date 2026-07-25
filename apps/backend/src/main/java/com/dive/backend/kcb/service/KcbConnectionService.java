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
import java.util.concurrent.ThreadLocalRandom;

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
            throw new IllegalStateException("KCB 연동 데이터를 만들지 못했습니다.", exception);
        }
    }

    /** 연동 직후 앱에 노출할 최소 요약값이다. KCB 원문 전체는 응답하지 않는다. */
    public DemoSummary summary(KcbConnection connection) {
        try {
            int score = objectMapper.readTree(connection.getKcbRecordJson()).path("신용평점").asInt();
            return new DemoSummary(score, scoreGrade(score));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("KCB 연동 요약을 읽지 못했습니다.", exception);
        }
    }

    private Map<String, Object> dummyRecord() {
        ThreadLocalRandom random = ThreadLocalRandom.current();
        DemoProfile profile = DemoProfile.random(random);

        // 금액 단위는 AI 서버 KCB 계약과 동일하게 천원이다. 프로필별로 연관된 값만 생성한다.
        int monthlyIncome = random.nextInt(profile.monthlyIncomeMin(), profile.monthlyIncomeMax() + 1);
        int estimatedAnnualIncome = monthlyIncome * random.nextInt(11, 13);
        int verifiedAnnualIncome = (int) Math.round(estimatedAnnualIncome * randomRatio(profile.verifiedIncomeMinRatio(), 0.98));
        int previousAnnualIncome = Math.max(6_000, estimatedAnnualIncome + random.nextInt(profile.incomeChangeMin(), profile.incomeChangeMax() + 1));

        boolean homeowner = random.nextInt(100) < profile.homeownerChance();
        int houseValue = homeowner ? random.nextInt(120_000, 550_001) : 0;
        int mortgageBalance = homeowner ? (int) Math.round(houseValue * randomRatio(profile.mortgageMinRatio(), profile.mortgageMaxRatio())) : 0;
        int unsecuredBalance = random.nextInt(100) < profile.unsecuredLoanChance()
                ? random.nextInt(profile.unsecuredLoanMin(), Math.max(profile.unsecuredLoanMin() + 1, profile.unsecuredLoanMax(estimatedAnnualIncome)) + 1)
                : 0;
        int policyLoanBalance = random.nextInt(100) < profile.policyLoanChance() ? random.nextInt(300, 5_001) : 0;
        int loanCount = (mortgageBalance > 0 ? 1 : 0) + (unsecuredBalance > 0 ? 1 : 0) + (policyLoanBalance > 0 ? 1 : 0);
        int annualRepayment = Math.min(estimatedAnnualIncome * profile.maxDti() / 100,
                Math.max(0, (int) Math.round((mortgageBalance + unsecuredBalance + policyLoanBalance)
                        * randomRatio(profile.repaymentMinRatio(), profile.repaymentMaxRatio()))));
        int dti = estimatedAnnualIncome == 0 ? 0 : Math.round(annualRepayment * 100f / estimatedAnnualIncome);
        int ltv = houseValue == 0 ? 0 : Math.round(mortgageBalance * 100f / houseValue);

        int cardSpend = (int) Math.round(estimatedAnnualIncome * randomRatio(profile.cardSpendMinRatio(), profile.cardSpendMaxRatio()));
        int creditCardSpend = (int) Math.round(cardSpend * randomRatio(0.55, 0.80));
        int installmentSpend = (int) Math.round(creditCardSpend * randomRatio(0.05, 0.22));
        int oneTimeSpend = creditCardSpend - installmentSpend;
        int checkCardSpend = cardSpend - creditCardSpend;
        boolean hasDelinquency = random.nextInt(100) < profile.delinquencyChance();
        int delinquencyDays = hasDelinquency ? random.nextInt(5, 61) : 0;
        int loanDelinquencyCount = hasDelinquency && random.nextBoolean() ? random.nextInt(1, 3) : 0;
        int cardDelinquencyCount = hasDelinquency && loanDelinquencyCount == 0 ? random.nextInt(1, 3) : 0;
        int loanDelinquencyAmount = loanDelinquencyCount == 0 ? 0 : random.nextInt(50, 501);
        int cardDelinquencyAmount = cardDelinquencyCount == 0 ? 0 : random.nextInt(30, 301);
        int creditScore = clamp(profile.creditScoreBase() - dti * profile.dtiPenalty() - (hasDelinquency ? profile.delinquencyPenalty() : 0)
                - loanCount * profile.loanCountPenalty() + random.nextInt(-25, 26), profile.creditScoreMin(), profile.creditScoreMax());

        Map<String, Object> r = new LinkedHashMap<>();
        r.put("성별", random.nextInt(1, 3)); r.put("연령대", random.nextInt(19, 40)); r.put("직업군", 420); r.put("거주지 시군구 코드", 26110); r.put("근무지 시군구 코드", 26110);
        r.put("추정월소득", monthlyIncome); r.put("증빙연소득", verifiedAnnualIncome); r.put("추정 연소득", estimatedAnnualIncome); r.put("2년전 추정 연소득 금액", previousAnnualIncome);
        r.put("총자산평가금액(주택)", houseValue); r.put("순자산평가금액(주택)", houseValue - mortgageBalance); r.put("자가거주여부", homeowner ? 1 : 0); r.put("현 거주지의 아파트여부", homeowner && random.nextBoolean() ? 1 : 0); r.put("현 거주지의 매매가(국토부 실거래가) 또는 공시가격", houseValue); r.put("차량보유(국산/수입)", random.nextInt(100) < 45 ? random.nextInt(1, 3) : 0); r.put("추정 LTV", ltv); r.put("추정DTI", dti); r.put("신용평점", creditScore);
        r.put("총대출건수", loanCount); r.put("신용대출-총대출약정액", unsecuredBalance); r.put("신용대출-총대출잔액", unsecuredBalance); r.put("주택담보대출-총대출약정액", mortgageBalance); r.put("주택담보대출-총대출잔액", mortgageBalance); r.put("정책자금대출-총대출약정액", policyLoanBalance); r.put("정책자금대출-총대출잔액", policyLoanBalance); r.put("총 대출 상환금액 (최근 12개월)", annualRepayment);
        r.put("최근 12개월 신용카드소비금액", creditCardSpend); r.put("최근 12개월 체크카드소비금액", checkCardSpend); r.put("최근 12개월 일시불이용금액", oneTimeSpend); r.put("최근 12개월 할부이용금액", installmentSpend); r.put("최근 12개월 현금서비스이용금액", hasDelinquency ? random.nextInt(50, 801) : 0); r.put("대출연체건수", loanDelinquencyCount); r.put("카드연체건수", cardDelinquencyCount); r.put("연체일수", delinquencyDays); r.put("대출연체금액", loanDelinquencyAmount); r.put("카드연체금액", cardDelinquencyAmount); r.put("Thin Filer 여부", profile.thinFiler() ? 1 : 0); r.put("파산, 개인회생 신청 여부", profile == DemoProfile.FINANCIAL_CRISIS && random.nextInt(100) < 12 ? 1 : 0); r.put("2년내 현거주지평균실거래가", houseValue == 0 ? -99999999 : Math.round(houseValue * randomRatio(0.92, 1.08))); r.put("2년내 현거주지평균전세거래가", houseValue == 0 ? -99999999 : Math.round(houseValue * randomRatio(0.45, 0.65))); r.put("2년내 직장명이력건수", random.nextInt(1, 4)); r.put("2년내 이직후 소득 증감액", estimatedAnnualIncome - previousAnnualIncome);
        return r;
    }

    /**
     * 매 연동마다 하나를 뽑아 KCB 연동 값의 분포를 만든다. 점수만 무작위로 바꾸지 않고
     * 소득·부채·소비·연체를 함께 움직여 AI 서버가 해석 가능한 레코드를 보장한다.
     */
    private enum DemoProfile {
        FINANCIALLY_COMFORTABLE(22, 2_800, 5_000, .88, 1_500, 6_000, 35, 60, .12, .35, 25, 25, .04, .18, 55, 860, 1, 10, 800, 950, false, -2_000, 6_000),
        HIGH_INCOME_WITH_LOANS(18, 3_500, 5_500, .86, 6_000, 16_000, 48, 72, .08, .22, 42, 45, .06, .17, 65, 820, 2, 12, 680, 900, false, -3_000, 7_000),
        STABLE_STANDARD(25, 1_800, 3_800, .82, 1_000, 8_000, 35, 62, .10, .25, 35, 35, .05, .16, 55, 790, 2, 12, 650, 880, false, -3_000, 5_000),
        THIN_FILE(15, 900, 2_300, .75, 300, 2_500, 0, 25, .00, .08, 20, 20, .05, .14, 50, 690, 2, 12, 560, 760, true, -4_000, 4_000),
        DEBT_BURDENED(13, 1_400, 3_400, .78, 12_000, 32_000, 0, 30, .00, .12, 80, 70, .10, .25, 70, 700, 3, 16, 480, 700, false, -5_000, 3_000),
        FINANCIAL_CRISIS(7, 800, 2_200, .70, 5_000, 18_000, 0, 20, .00, .08, 95, 75, .12, .28, 75, 610, 4, 25, 430, 620, false, -6_000, 1_500);

        private final int weight, monthlyIncomeMin, monthlyIncomeMax, unsecuredLoanMin, homeownerChance, unsecuredLoanChance, policyLoanChance, maxDti, creditScoreBase, dtiPenalty, loanCountPenalty, creditScoreMin, creditScoreMax, incomeChangeMin, incomeChangeMax;
        private final double verifiedIncomeMinRatio, mortgageMinRatio, mortgageMaxRatio, repaymentMinRatio, repaymentMaxRatio, cardSpendMinRatio, cardSpendMaxRatio;
        private final boolean thinFiler;

        DemoProfile(int weight, int monthlyIncomeMin, int monthlyIncomeMax, double verifiedIncomeMinRatio, int unsecuredLoanMin, int unsecuredLoanMaxUnused,
                    int homeownerChance, int unsecuredLoanChance, double mortgageMinRatio, double mortgageMaxRatio, int policyLoanChance, int maxDti,
                    double repaymentMinRatio, double repaymentMaxRatio, int cardSpendMaxPercent, int creditScoreBase, int dtiPenalty, int loanCountPenalty,
                    int creditScoreMin, int creditScoreMax, boolean thinFiler, int incomeChangeMin, int incomeChangeMax) {
            this.weight = weight; this.monthlyIncomeMin = monthlyIncomeMin; this.monthlyIncomeMax = monthlyIncomeMax; this.verifiedIncomeMinRatio = verifiedIncomeMinRatio;
            this.unsecuredLoanMin = unsecuredLoanMin; this.homeownerChance = homeownerChance; this.unsecuredLoanChance = unsecuredLoanChance;
            this.mortgageMinRatio = mortgageMinRatio; this.mortgageMaxRatio = mortgageMaxRatio; this.policyLoanChance = policyLoanChance; this.maxDti = maxDti;
            this.repaymentMinRatio = repaymentMinRatio; this.repaymentMaxRatio = repaymentMaxRatio; this.cardSpendMinRatio = .18; this.cardSpendMaxRatio = cardSpendMaxPercent / 100d;
            this.creditScoreBase = creditScoreBase; this.dtiPenalty = dtiPenalty; this.loanCountPenalty = loanCountPenalty;
            this.creditScoreMin = creditScoreMin; this.creditScoreMax = creditScoreMax; this.thinFiler = thinFiler; this.incomeChangeMin = incomeChangeMin; this.incomeChangeMax = incomeChangeMax;
        }

        static DemoProfile random(ThreadLocalRandom random) {
            int pick = random.nextInt(100);
            int cumulative = 0;
            for (DemoProfile profile : values()) { cumulative += profile.weight; if (pick < cumulative) return profile; }
            return STABLE_STANDARD;
        }
        int unsecuredLoanMax(int annualIncome) { return Math.max(unsecuredLoanMin, Math.min(32_000, annualIncome * (this == DEBT_BURDENED ? 2 : 1))); }
        int delinquencyChance() { return this == FINANCIAL_CRISIS ? 70 : this == DEBT_BURDENED ? 28 : this == THIN_FILE ? 8 : 3; }
        int delinquencyPenalty() { return this == FINANCIAL_CRISIS ? 130 : 100; }
        int monthlyIncomeMin() { return monthlyIncomeMin; } int monthlyIncomeMax() { return monthlyIncomeMax; } double verifiedIncomeMinRatio() { return verifiedIncomeMinRatio; }
        int unsecuredLoanMin() { return unsecuredLoanMin; } int homeownerChance() { return homeownerChance; } int unsecuredLoanChance() { return unsecuredLoanChance; }
        int policyLoanChance() { return policyLoanChance; } double mortgageMinRatio() { return mortgageMinRatio; } double mortgageMaxRatio() { return mortgageMaxRatio; }
        int maxDti() { return maxDti; } double repaymentMinRatio() { return repaymentMinRatio; } double repaymentMaxRatio() { return repaymentMaxRatio; }
        double cardSpendMinRatio() { return cardSpendMinRatio; } double cardSpendMaxRatio() { return cardSpendMaxRatio; } int creditScoreBase() { return creditScoreBase; }
        int dtiPenalty() { return dtiPenalty; } int loanCountPenalty() { return loanCountPenalty; } int creditScoreMin() { return creditScoreMin; } int creditScoreMax() { return creditScoreMax; }
        boolean thinFiler() { return thinFiler; } int incomeChangeMin() { return incomeChangeMin; } int incomeChangeMax() { return incomeChangeMax; }
    }

    private double randomRatio(double min, double max) { return ThreadLocalRandom.current().nextDouble(min, max); }
    private int clamp(int value, int min, int max) { return Math.max(min, Math.min(max, value)); }
    private String scoreGrade(int score) {
        if (score >= 850) return "최우수";
        if (score >= 750) return "우수";
        if (score >= 650) return "양호";
        if (score >= 550) return "관리 필요";
        return "주의";
    }

    public record DemoSummary(int creditScore, String creditGrade) { }
}
