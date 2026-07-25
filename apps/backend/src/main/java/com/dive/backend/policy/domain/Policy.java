package com.dive.backend.policy.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

/**
 * 온통청년 정책 원본 데이터. camelCase 필드명은 원본 API 필드명(plcyNo, plcyNm 등)을 그대로 따른다.
 * plcyNo가 API 재동기화 시 upsert 기준키.
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
@Table(name = "policy")
public class Policy {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 정책번호(원본 plcyNo) - API 재동기화 upsert 기준키 */
    @Column(nullable = false, unique = true, length = 30)
    private String plcyNo;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "policy_type_id", nullable = false)
    private PolicyType policyType;

    @Column(nullable = false, length = 200)
    private String plcyNm;

    @Column(length = 200)
    private String plcyKywdNm;

    @Column(columnDefinition = "TEXT")
    private String plcyExplnCn;

    /** 정책 대분류명 - 온통청년 공식 카테고리 */
    @Column(length = 50)
    private String lclsfNm;

    @Column(length = 50)
    private String mclsfNm;

    @Column(columnDefinition = "TEXT")
    private String plcySprtCn;

    /** 정책승인상태코드 - 승인건만 노출 */
    @Column(length = 20)
    private String plcyAprvSttsCd;

    @Column(length = 100)
    private String sprvsnInstNm;

    /** 신청기간구분코드 - 상시/기간 */
    @Column(length = 20)
    private String aplyPrdSeCd;

    @Column(length = 50)
    private String aplyYmd;

    @Column(columnDefinition = "TEXT")
    private String plcyAplyMthdCn;

    @Column(columnDefinition = "TEXT")
    private String srngMthdCn;

    @Column(length = 500)
    private String aplyUrlAddr;

    @Column(columnDefinition = "TEXT")
    private String sbmsnDcmntCn;

    @Column(length = 20)
    private String sprtSclCnt;

    private Integer sprtTrgtMinAge;

    private Integer sprtTrgtMaxAge;

    /** 연령제한여부 Y/N */
    @Column(length = 1)
    private String sprtTrgtAgeLmtYn;

    /** 혼인상태 조건코드 */
    @Column(length = 20)
    private String mrgSttsCd;

    /** 소득조건구분코드 */
    @Column(length = 20)
    private String earnCndSeCd;

    @Column(length = 20)
    private String earnMinAmt;

    @Column(length = 20)
    private String earnMaxAmt;

    @Column(length = 500)
    private String earnEtcCn;

    @Column(columnDefinition = "TEXT")
    private String addAplyQlfcCndCn;

    /** 참여제한대상내용 */
    @Column(columnDefinition = "TEXT")
    private String ptcpPrpTrgtCn;

    /** 거주지역코드 - 지역 필터링. 정책 하나에 수십~수백개 코드가 콤마로 붙어 올 수 있어 TEXT로 저장 */
    @Column(columnDefinition = "TEXT")
    private String zipCd;

    /** 학력요건코드 - zipCd와 같은 이유로 TEXT */
    @Column(columnDefinition = "TEXT")
    private String schoolCd;

    /** 취업요건코드 - zipCd와 같은 이유로 TEXT */
    @Column(columnDefinition = "TEXT")
    private String jobCd;

    /** 전공요건코드 - zipCd와 같은 이유로 TEXT */
    @Column(columnDefinition = "TEXT")
    private String plcyMajorCd;

    @Column(nullable = false)
    @Builder.Default
    private Integer viewCount = 0;

    /** 원본 최초등록일시(frstRegDt) */
    private LocalDateTime srcRegDt;

    /** 원본 최종수정일시(lastMdfcnDt) */
    private LocalDateTime srcMdfcnDt;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    public void increaseViewCount() {
        this.viewCount++;
    }
}
