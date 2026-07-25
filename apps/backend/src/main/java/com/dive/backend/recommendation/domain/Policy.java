package com.dive.backend.recommendation.domain;

import jakarta.persistence.*;
import lombok.Getter;

@Entity
@Getter
@Table(name = "policy")
public class Policy {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "plcy_no") private String plcyNo;
    @Column(name = "policy_type_id") private Integer policyTypeId;
    @Column(name = "plcy_nm") private String plcyNm;
    @Column(name = "lclsf_nm") private String lclsfNm;
    @Column(name = "plcy_expln_cn", columnDefinition = "TEXT") private String plcyExplnCn;
    @Column(name = "plcy_sprt_cn", columnDefinition = "TEXT") private String plcySprtCn;
    @Column(name = "add_aply_qlfc_cnd_cn", columnDefinition = "TEXT") private String addAplyQlfcCndCn;
    @Column(name = "ptcp_prp_trgt_cn", columnDefinition = "TEXT") private String ptcpPrpTrgtCn;
    @Column(name = "plcy_aprv_stts_cd") private String plcyAprvSttsCd;
    @Column(name = "sprt_trgt_min_age") private Integer minAge;
    @Column(name = "sprt_trgt_max_age") private Integer maxAge;
    @Column(name = "earn_min_amt") private String earnMinAmt;
    @Column(name = "earn_max_amt") private String earnMaxAmt;
    @Column(name = "zip_cd", columnDefinition = "TEXT") private String zipCd;
    @Column(name = "mrg_stts_cd") private String mrgSttsCd;
    @Column(name = "job_cd") private String jobCd;
    @Column(name = "school_cd") private String schoolCd;
}
